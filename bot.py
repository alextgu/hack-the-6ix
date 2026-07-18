"""Telegram bot — the render + command layer only.

Run steps:
  1. pip install -r requirements.txt
  2. Put TELEGRAM_BOT_TOKEN into .env (it's already picked up by dotenv).
     Get one from @BotFather → /newbot.
  3. python bot.py

BotFather setup (do this once, otherwise the bot only sees /commands in groups):
  /mybots → pick your bot → Bot Settings → Group Privacy → **Turn off**
  Add the bot to a test group, then /start in the group.

Commands (once running):
  /start           hatch the pet, post its image
  /health          post the current pet image + numbers
  /scrub <0..6>    dev: jump the simulated timeline; watch the bars move
  /commit          both bars full — celebrated 'graduated' pet

TODO seams (later lanes plug in here without changing the shape):
  - Read layer: parse `update.message.text` into TripState via LLM/Freesolo.
    The pipeline lands in `state.get_or_create(chat_id).trip`.
  - Nudge layer: an engagement counter fed by `log_message()` drives mental
    delta calls into `health.apply_mental_delta`.
  - Phoebe agent: subscribe to mood transitions and DM the identified blocker.
  - ElevenLabs voice: send_voice on `mood` → 'dying' with cooldown.
"""
from __future__ import annotations
import logging
import os
from io import BytesIO

from dotenv import load_dotenv
from telegram import (
    Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

import asyncio

import state
import health
import pet
import wire
import stay22
import booking


def _webapp_url_for(chat_id: int) -> str | None:
    """Public HTTPS URL for the Mini App, with ?group=<chat_id> appended.
    Returns None if PUBLIC_WEBAPP_URL isn't set (Mini App button then skipped)."""
    base = os.environ.get("PUBLIC_WEBAPP_URL", "").strip()
    if not base:
        return None
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}group={chat_id}"


def _webapp_keyboard(chat_id: int, label: str = "🐾 open pet") -> InlineKeyboardMarkup | None:
    url = _webapp_url_for(chat_id)
    if not url:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, web_app=WebAppInfo(url=url))]])


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("trippet")


# ─── Rendering helper ────────────────────────────────────────────────────────
async def _send_pet(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    g = state.get_or_create(chat_id)
    g.pet.refresh_mood()
    png_bytes = pet.render_pet_png(g)
    caption = f"physical {g.pet.physical}% · mental {g.pet.mental}% · {g.pet.mood}"
    await ctx.bot.send_photo(
        chat_id=chat_id,
        photo=InputFile(BytesIO(png_bytes), filename="trippet.png"),
        caption=caption,
    )


# ─── Handlers ────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    g = state.reset(update.effective_chat.id)
    log.info("hatch chat_id=%s", g.chat_id)
    await update.effective_chat.send_message(
        "hi. i'm the pet. i live here now.\n"
        "start talking about the japan trip. every real decision heals me. "
        "silence and rising prices kill me. try /health any time. "
        "dev: /scrub 0..6 to fast-forward, /commit to book.",
        reply_markup=_webapp_keyboard(g.chat_id, label="🐾 open live pet"),
    )
    await _send_pet(update, ctx)


async def cmd_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Launch the animated Mini App (the Face layer)."""
    chat_id = update.effective_chat.id
    kb = _webapp_keyboard(chat_id, label="🐾 open live pet")
    if not kb:
        await update.effective_chat.send_message(
            "PUBLIC_WEBAPP_URL isn't set — start a cloudflared/ngrok tunnel and "
            "put the HTTPS URL in .env, then restart."
        )
        return
    await update.effective_chat.send_message("tap to open the live pet:", reply_markup=kb)


async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_pet(update, ctx)


async def cmd_scrub(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.effective_chat.send_message(f"usage: /scrub 0..{health.MAX_WEEK}")
        return
    try:
        week = int(ctx.args[0])
    except ValueError:
        await update.effective_chat.send_message("gimme a number 0..6")
        return
    if not (0 <= week <= health.MAX_WEEK):
        await update.effective_chat.send_message(f"out of range. 0..{health.MAX_WEEK}")
        return
    g = state.get_or_create(update.effective_chat.id)
    health.scrub_to_week(g, week)
    log.info("scrub chat_id=%s week=%d → phys=%d ment=%d mood=%s",
             g.chat_id, week, g.pet.physical, g.pet.mental, g.pet.mood)
    await _send_pet(update, ctx)


async def cmd_commit(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Graduation path: query Stay22, pick a hotel, post the Allez book link.
    Falls back gracefully if the trip isn't locked or nothing fits the budget."""
    g = state.get_or_create(update.effective_chat.id)
    trip = g.trip

    if not (trip.city and trip.dates and trip.dates.start and trip.dates.end):
        await update.effective_chat.send_message(
            "still figuring out the trip — can't book yet. lock city + dates first, then /commit."
        )
        return

    guests = int(trip.group_size or 2)
    checkin = trip.dates.start.isoformat()
    checkout = trip.dates.end.isoformat()
    nights = max(1, (trip.dates.end - trip.dates.start).days)

    results = await asyncio.to_thread(
        stay22.search_raw, f"{trip.city}, Japan", checkin, checkout, guests
    )
    chosen = booking.pick_hotel(results or [], trip.budget_per_person, guests, nights) if results else None
    opts = booking.booking_options(chosen) if chosen else None

    if not opts or not opts.get("book_url"):
        budget_note = f" under ${trip.budget_per_person}/person" if trip.budget_per_person else ""
        await update.effective_chat.send_message(
            f"no rooms{budget_note} for {trip.city} on {checkin} → {checkout}. "
            "try raising budget or shifting dates, then /commit again."
        )
        return

    # graduate (existing pet logic)
    health.commit_trip(g)
    log.info("commit chat_id=%s → graduated (booked: %s @ $%.0f)",
             g.chat_id, opts["name"], opts["price_total"])

    rating_str = f" · {opts['rating']:.1f}/10" if opts.get("rating") else ""
    fallback_note = "\n(over budget — cheapest we could find)" if opts.get("fallback") else ""
    caption = (
        f"🎉 booked. graduating the pet.\n"
        f"{opts['name']}{rating_str}\n"
        f"${opts['price_total']:.0f} total · {guests} guests · {nights} night(s) in {trip.city}"
        f"{fallback_note}"
    )
    buttons: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🎉 Book your trip →", url=opts["book_url"])]
    ]
    for alt in (opts.get("alternates") or [])[:2]:
        buttons.append([InlineKeyboardButton(
            text=f"or: {alt['name']} — ${alt['price_total']:.0f}",
            url=alt["book_url"],
        )])
    await update.effective_chat.send_message(
        caption, reply_markup=InlineKeyboardMarkup(buttons)
    )
    await _send_pet(update, ctx)


async def log_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every non-command text message. Buffered by wire.py; consensus +
    Stay22 poll run behind a debounce so we don't burn the LLM / Stay22
    quota on every keystroke."""
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    speaker = (update.effective_user.first_name if update.effective_user else "someone") or "someone"
    log.info("msg chat_id=%s from=%s: %s", chat_id, speaker, update.message.text[:200])

    wire.note_message(chat_id, speaker, update.message.text)
    reconciled = await wire.maybe_process(chat_id)
    if reconciled is None:
        return

    # Announce meaningful changes in-chat. Cheap: no re-render unless the
    # pet visibly changed.
    g = state.get_or_create(chat_id)
    g.pet.refresh_mood()
    blockers = wire.get_blockers(chat_id)
    parts = []
    if reconciled.get("city"):     parts.append(f"city: {reconciled['city']}")
    dw = reconciled.get("dates") or {}
    if dw.get("start") and dw.get("end"): parts.append(f"dates: {dw['start']} → {dw['end']}")
    if reconciled.get("budget_per_person") is not None:
        parts.append(f"budget: ${reconciled['budget_per_person']}")
    if blockers:
        parts.append("blockers: " + " | ".join(blockers))
    if parts:
        await update.effective_chat.send_message("🧠 " + " · ".join(parts))


# ─── App factory (shared by standalone `main()` and `run.py`) ────────────────
def build_app() -> Application:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set. Put it in .env or export it.")

    app: Application = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("scrub", cmd_scrub))
    app.add_handler(CommandHandler("commit", cmd_commit))
    app.add_handler(CommandHandler("open", cmd_open))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
    return app


def main() -> None:
    log.info("trippet online — polling. remember to disable BotFather group privacy.")
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
