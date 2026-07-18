"""Telegram bot — the render + command layer only.

Run steps:
  1. pip install -r requirements.txt
  2. Put TELEGRAM_BOT_TOKEN into .env (it's already picked up by dotenv).
     Get one from @BotFather → /newbot.
  3. python bot.py

BotFather setup (do this once, otherwise the bot only sees /commands in groups):
  /mybots → pick your bot → Bot Settings → Group Privacy → **Turn off**
  Add the bot to a test group, then /start in the group.

Mini App button (also one-time, in BotFather):
  /mybots → pick your bot → Bot Settings → Configure Mini App → set it to
  your PUBLIC_WEBAPP_URL. Required for the "open live pet" button — web_app=
  inline buttons only work in private chats, so group buttons use a
  t.me/<bot>?startapp=... deep link instead (see _miniapp_url_for), which
  only opens as a real Mini App once BotFather has this registered.

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
import asyncio
import logging
import os
import re
from io import BytesIO

from dotenv import load_dotenv
from telegram import (
    Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

from app.core import state
from app.core import health
from app.render import pet
from app.bot import wire
from app.bot import cards
from app.integrations import stay22
from app.integrations import booking
from app.integrations import db
from app.integrations import flights
from app.agents import supervisor


def _encode_start_param(chat_id: int) -> str:
    """Telegram's start_param only allows [A-Za-z0-9_-]; group chat_ids are
    negative, so stash the sign in a prefix letter instead of a leading '-'."""
    return f"n{-chat_id}" if chat_id < 0 else f"p{chat_id}"


def _miniapp_url_for(chat_id: int, bot_username: str) -> str:
    """t.me deep link that opens the bot's BotFather-registered Mini App,
    passing chat_id via start_param.

    NOT a web_app= inline button: those are only valid in private chats with
    the bot (Telegram rejects them with Button_type_invalid in groups). A
    plain url= button pointing at a t.me Mini App deep link works from
    anywhere, including groups, and Telegram still opens it as a full Mini
    App (SDK/initData/theme) rather than a browser tab — but only once the
    Mini App is registered via BotFather (Bot Settings → Configure Mini App)."""
    return f"https://t.me/{bot_username}?startapp={_encode_start_param(chat_id)}"


def _webapp_keyboard(chat_id: int, bot_username: str, label: str = "🐾 open pet") -> InlineKeyboardMarkup:
    url = _miniapp_url_for(chat_id, bot_username)
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, url=url)]])


def _cards_keyboard(chat_id: int, bot_username: str) -> InlineKeyboardMarkup:
    """Deep-link button for the hotel swipe deck. Same t.me?startapp trick as
    _miniapp_url_for (web_app= buttons are invalid in groups) with a '-cards'
    suffix on the start_param; webapp/app.js sees the suffix and forwards the
    webview to /cards."""
    url = (f"https://t.me/{bot_username}"
           f"?startapp={_encode_start_param(chat_id)}-cards")
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏨 swipe on hotels", url=url)]])


async def open_hotel_cards(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Basecamp is confirmed → deal the hotel deck to the group.

    This is THE seam the agent flow will call once the pet has walked the
    group to a confirmed basecamp (gather → propose → react → resolve).
    For now the temporary "map" chat trigger below invokes it directly."""
    session = await asyncio.to_thread(cards.ensure_session, chat_id)
    n = len(session["active"])
    kb = _cards_keyboard(chat_id, ctx.bot.username)
    text = (
        f"🏨 basecamp locked: {session['basecamp']} "
        f"({session['checkin']} → {session['checkout']})\n"
        f"i found {n} real places. everyone swipe — "
        "i'll keep cutting until we all land on one."
    )
    await ctx.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)


async def _say(chat_id: int, text: str, ctx: ContextTypes.DEFAULT_TYPE,
               reply_to: int | None = None) -> None:
    """Send with Markdown so [name](tg://user?id=...) mentions ping people;
    fall back to plain text if Tabi's prose breaks Markdown parsing, and drop
    the reply threading if the target message is gone."""
    for parse_mode in (ParseMode.MARKDOWN, None):
        for rt in (reply_to, None) if reply_to else (None,):
            try:
                await ctx.bot.send_message(chat_id=chat_id, text=text,
                                           parse_mode=parse_mode,
                                           reply_to_message_id=rt)
                return
            except Exception:
                continue


async def send_pet_card(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Post the pet health PNG to a chat (guilt-trip visual)."""
    g = state.get_or_create(chat_id)
    g.pet.refresh_mood()
    png_bytes = pet.render_pet_png(g)
    caption = f"physical {g.pet.physical}% · mental {g.pet.mental}% · {g.pet.mood}"
    await ctx.bot.send_photo(
        chat_id=chat_id,
        photo=InputFile(BytesIO(png_bytes), filename="trippet.png"),
        caption=caption,
    )


async def execute_decision(chat_id: int, d: "supervisor.Decision",
                           ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Carry out what the supervisor decided. The supervisor is the only
    place that decides; this just has hands."""
    if not d.send:
        return
    if d.action == "deal_cards":
        if d.message:
            await _say(chat_id, d.message, ctx)
        await open_hotel_cards(chat_id, ctx)
        supervisor.note_cards_dealt(chat_id)
        return
    if d.action == "post_flights":
        g = state.get_or_create(chat_id)
        opts = flights.mock_options(chat_id, g.trip.city, g.trip.budget_per_person)
        text = (d.message + "\n\n" if d.message else "") + flights.render_options(opts)
        await ctx.bot.send_message(chat_id=chat_id, text=text)
        supervisor.note_flights_posted(chat_id)
        return
    if d.message:
        await _say(chat_id, d.message, ctx, reply_to=d.reply_to)
    if d.show_health:
        await send_pet_card(chat_id, ctx)


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
    await asyncio.to_thread(state.persist_pet, g)
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
        reply_markup=_webapp_keyboard(g.chat_id, ctx.bot.username, label="🐾 open live pet"),
    )
    await _send_pet(update, ctx)
    # The pet is the +1 member: hatching immediately opens the planning
    # conversation (kickoff bypasses the cooldown, always sends).
    decision = await asyncio.to_thread(supervisor.run_turn, g.chat_id, "kickoff")
    await execute_decision(g.chat_id, decision, ctx)


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Nuke EVERYTHING for this group — Mongo docs, in-memory buffers, deck
    sessions, pacing caches — then hatch completely fresh."""
    chat_id = update.effective_chat.id
    removed = await asyncio.to_thread(db.nuke_chat, chat_id)
    wire.reset_chat(chat_id)
    cards.forget(chat_id)
    supervisor.reset_chat(chat_id)
    state.reset(chat_id)
    log.info("RESET chat=%s (%d docs wiped)", chat_id, removed)
    await update.effective_chat.send_message(
        f"🧹 wiped everything ({removed} records). fresh egg incoming…"
    )
    await cmd_start(update, ctx)


async def cmd_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Launch the animated Mini App (the Face layer)."""
    chat_id = update.effective_chat.id
    kb = _webapp_keyboard(chat_id, ctx.bot.username, label="🐾 open live pet")
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

    user_id = str(update.effective_user.id) if update.effective_user else "unknown"
    await asyncio.to_thread(db.log_chat_message, chat_id, user_id, speaker,
                            update.message.text, update.message.message_id)

    # TEMPORARY: "map" stays as a manual override for demos. The supervisor
    # now deals the deck itself when the stage reaches HOTELS.
    if re.search(r"\bmap\b", update.message.text, re.IGNORECASE):
        await open_hotel_cards(chat_id, ctx)
        supervisor.note_cards_dealt(chat_id)
        return

    # "flight 2" locks the mock flight stage
    lock_msg = await asyncio.to_thread(supervisor.try_lock_flight, chat_id,
                                       update.message.text)
    if lock_msg:
        await update.effective_chat.send_message(lock_msg)

    wire.note_message(chat_id, speaker, update.message.text)
    reconciled = await wire.maybe_process(chat_id)  # brain keeps its own debounce
    if reconciled is not None:
        g = state.get_or_create(chat_id)
        g.pet.refresh_mood()
        await asyncio.to_thread(state.persist_pet, g)

    # The supervisor gets a chance on EVERY message — its send-cooldown is
    # the pacing, not the reader's 3-message debounce. Skip the LLM turn
    # while the cooldown is hot, UNLESS someone sounds like they're backing
    # out — that's serious enough to always wake Tabi.
    urgent = supervisor.is_urgent(update.message.text)
    if supervisor.can_speak(chat_id) or urgent:
        decision = await asyncio.to_thread(supervisor.run_turn, chat_id,
                                           "message", urgent)
        await execute_decision(chat_id, decision, ctx)


# ─── Global error handler ────────────────────────────────────────────────────
async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all so one bad update (a raised handler, a Telegram/API hiccup)
    can never kill polling. Logs what failed; the updater keeps running.
    A user-visible reply is best-effort and itself swallowed on failure."""
    chat_id = getattr(getattr(update, "effective_chat", None), "id", None)
    log.error("handler error (chat_id=%s): %s", chat_id, ctx.error, exc_info=ctx.error)
    if chat_id is not None:
        try:
            await ctx.bot.send_message(chat_id=chat_id, text="hiccup on my end — try that again in a sec")
        except Exception:
            pass  # never let the error handler itself raise


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
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
    app.add_error_handler(on_error)
    return app


def main() -> None:
    log.info("trippet online — polling. remember to disable BotFather group privacy.")
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
