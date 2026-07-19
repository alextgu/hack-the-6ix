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
  /start           hatch the pet, post its image (also wakes a /stop'd pet)
  /health          post the current pet image + numbers
  /scrub <0..6>    dev: jump the simulated timeline; watch the bars move
  /commit          both bars full — celebrated 'graduated' pet
  /saved           green ledger: CO2e avoided so far, in human units
  /itinerary       green-routed day-by-day plan (rail > car, savings counted)
  /stop            full mute: no reads, no Gemini calls, heartbeat skips the chat
  /resume          un-pause; /start also clears it

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
from datetime import date
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
from app.integrations import elevenlabs
from app.integrations import telegram_avatar
from app.integrations import green
from app.agents import supervisor
from app.agents import greenplanner
from app.agents import face


def _encode_start_param(chat_id: int) -> str:
    """Telegram's start_param only allows [A-Za-z0-9_-]; group chat_ids are
    negative, so stash the sign in a prefix letter instead of a leading '-'."""
    return f"n{-chat_id}" if chat_id < 0 else f"p{chat_id}"


def _fmt_date(d: date | str | None) -> str:
    """User-facing dates: 'July 18, 2026' (API/Stay22 stay ISO)."""
    if d is None or d == "":
        return ""
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d[:10])
        except ValueError:
            return str(d)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _fmt_date_range(start: date | str | None, end: date | str | None) -> str:
    a, b = _fmt_date(start), _fmt_date(end)
    if a and b:
        return f"{a} → {b}"
    return a or b


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
        f"({_fmt_date_range(session['checkin'], session['checkout'])})\n"
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


async def _sync_avatar(g: state.GroupState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Best-effort: swap the bot's own profile photo to match the exact tami
    sprite (size/mold/feeling) currently shown in-chat. Deduped inside
    telegram_avatar (no-ops if this sprite is already set), so it's safe to
    call on every render. Never raises — a Telegram hiccup here must not
    break the chat flow. NOTE: this is the bot ACCOUNT's avatar, shared
    across every chat it's in (see telegram_avatar.py)."""
    try:
        await asyncio.to_thread(telegram_avatar.set_avatar_for_state, ctx.bot.token,
                                g.pet.physical, g.pet.mental, g.pet.feeling)
    except Exception as e:
        log.warning("avatar sync failed (chat=%s): %s", g.chat_id, e)


async def send_pet_card(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, *,
                        message: str | None = None, reply_to: int | None = None) -> None:
    """Post the pet card PNG to a chat. Tabi's line (if any) rides as the
    photo's OWN caption — one Telegram message, not a text message followed
    by a separate photo. Falls back to the card's own mood caption when
    there's no Tabi line (plain /health-style checks). If every caption
    attempt fails (e.g. an unusually long line blowing past Telegram's
    1024-char photo-caption cap), degrades to a bare photo + a separate text
    send rather than silently dropping the turn."""
    g = state.get_or_create(chat_id)
    g.pet.refresh_mood()
    await asyncio.to_thread(state.persist_pet, g)
    asyncio.create_task(_sync_avatar(g, ctx))
    png_bytes = pet.render_pet_png(g)
    caption = message or pet.pet_caption(g)

    for parse_mode in (ParseMode.MARKDOWN, None):
        for rt in (reply_to, None) if reply_to else (None,):
            try:
                await ctx.bot.send_photo(
                    chat_id=chat_id,
                    photo=InputFile(BytesIO(png_bytes), filename="trippet.png"),
                    caption=caption, parse_mode=parse_mode, reply_to_message_id=rt,
                )
                return
            except Exception:
                continue

    await ctx.bot.send_photo(chat_id=chat_id,
                             photo=InputFile(BytesIO(png_bytes), filename="trippet.png"))
    if message:
        await _say(chat_id, message, ctx, reply_to=reply_to)


# ─── Voice (ElevenLabs) — gated: deathbed + graduation only ─────────────────
# The pet speaks aloud only at the two moments that earn it: crossing into
# critical health (the deathbed plea) and graduating. Never on a normal
# message. Deduped per chat so each fires at most once; re-armed on /start.
_spoke_deathbed: set[int] = set()
_spoke_graduated: set[int] = set()
_DEATHBED_PHYSICAL = 20  # physical at/below this counts as the deathbed moment


async def speak_pet(chat_id: int, text: str, ctx: ContextTypes.DEFAULT_TYPE,
                    mood: str | None = None, physical: int | None = None) -> None:
    """Post a mood-aware ElevenLabs voice note with `text` as the caption.
    Falls back to a plain-text message if synthesis, conversion, or the voice
    send fails. Never raises — a voice failure must not break the chat."""
    ogg = None
    try:
        ogg = await asyncio.to_thread(elevenlabs.synthesize_voice_note, text, mood, physical)
    except Exception as e:
        log.warning("voice synth raised (chat=%s): %s", chat_id, e)
    if ogg:
        try:
            await ctx.bot.send_voice(
                chat_id=chat_id,
                voice=InputFile(BytesIO(ogg), filename="pet.ogg"),
                caption=text,
            )
            return
        except Exception as e:
            log.warning("send_voice failed (chat=%s): %s — falling back to text", chat_id, e)
    # Fallback: plain text, best-effort.
    try:
        await ctx.bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        pass


async def maybe_speak_deathbed(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Speak the deathbed plea the first time the pet crosses into critical
    health for this chat. Gated + deduped — reads state only, changes nothing."""
    g = state.get_or_create(chat_id)
    g.pet.refresh_mood()
    critical = g.pet.mood == "dying" or g.pet.physical <= _DEATHBED_PHYSICAL
    if not critical or chat_id in _spoke_deathbed:
        return
    _spoke_deathbed.add(chat_id)
    await speak_pet(
        chat_id,
        "i'm fading here... the prices keep climbing and nobody's deciding. "
        "please — just book something.",
        ctx, mood="dying", physical=g.pet.physical,
    )


# ─── /stop mute state (memory cache over the persisted plan flag) ───────────
# One mechanism, checked everywhere the bot can act: message ingestion,
# execute_decision, and the run.py heartbeat. Persisted (trip_plans.muted) so
# a redeploy mid-demo doesn't quietly un-stop a chat that asked for silence.
_mute_cache: dict[int, bool] = {}


def is_muted(chat_id: int) -> bool:
    """BLOCKING on first check per chat (one Mongo read, then cached).
    Memory-only when Atlas is down — /stop still works for this process."""
    if chat_id not in _mute_cache:
        _mute_cache[chat_id] = bool(db.get_plan(chat_id).get("muted"))
    return _mute_cache[chat_id]


def set_muted(chat_id: int, muted: bool) -> None:
    """BLOCKING (Mongo write) — call via asyncio.to_thread."""
    _mute_cache[chat_id] = muted
    db.update_plan(chat_id, {"muted": muted})
    log.info("mute chat=%s → %s", chat_id, muted)


async def _green_react(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int,
                       message_id: int | None) -> None:
    """The subtle nudge: the pet reacts 🕊 to its own message whenever a green
    suggestion/saving just happened. Best-effort — reactions aren't allowed in
    every chat, and older setups may lack the API; never let it raise."""
    if not message_id:
        return
    try:
        from telegram.constants import ReactionEmoji
        emoji = ReactionEmoji.DOVE
    except Exception:
        emoji = "🕊"
    try:
        await ctx.bot.set_message_reaction(chat_id=chat_id,
                                           message_id=message_id,
                                           reaction=emoji)
    except Exception as e:
        log.info("green react skipped (chat=%s): %s", chat_id, e)


async def execute_decision(chat_id: int, d: "supervisor.Decision",
                           ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Carry out what the supervisor decided. The supervisor is the only
    place that decides; this just has hands."""
    if not d.send or _mute_cache.get(chat_id):
        return
    g = state.get_or_create(chat_id)
    if d.message:
        # Gemini reads the feeling of THIS message (isolated seam, always
        # Gemini even when the message itself came from Freesolo) so the
        # face/avatar match how the line actually reads.
        feeling = await asyncio.to_thread(face.classify_feeling, d.message)
        g.pet.set_feeling(feeling)
        await asyncio.to_thread(state.persist_pet, g)
        # Profile photo must track feeling on EVERY send, not just turns that
        # also show the health card — otherwise the avatar barely ever moves.
        asyncio.create_task(_sync_avatar(g, ctx))
    if d.action == "deal_cards":
        if d.message:
            await _say(chat_id, d.message, ctx)
        await open_hotel_cards(chat_id, ctx)
        supervisor.note_cards_dealt(chat_id)
        return
    if d.action == "post_flights":
        opts = await asyncio.to_thread(flights.get_options, chat_id,
                                       g.trip.city, g.trip.budget_per_person)
        text = (d.message + "\n\n" if d.message else "") + flights.render_options(opts)
        msg = await ctx.bot.send_message(chat_id=chat_id, text=text)
        supervisor.note_flights_posted(chat_id, opts)
        await _green_react(ctx, chat_id, msg.message_id)  # a 🌱 option is on the table
        return
    if d.action == "post_itinerary":
        text = await asyncio.to_thread(greenplanner.build_itinerary, chat_id)
        if d.message:
            await _say(chat_id, d.message, ctx)
        msg = await ctx.bot.send_message(chat_id=chat_id, text=text)
        supervisor.note_itinerary_posted(chat_id)
        await _green_react(ctx, chat_id, msg.message_id)
        return
    if d.show_health:
        # Tabi's line rides as the photo's caption — one message, not two.
        await send_pet_card(chat_id, ctx, message=d.message, reply_to=d.reply_to)
    elif d.message:
        await _say(chat_id, d.message, ctx, reply_to=d.reply_to)
    # Flywheel: after a messenger line goes out, watch the chat for a window and
    # back-fill the ground-truth outcome. Fire-and-forget; no-ops without Mongo.
    if d.harvest_id:
        _schedule_outcome(chat_id, d.harvest_id)


# Window to watch a chat after a messenger send before scoring the outcome.
OUTCOME_WINDOW_S = int(os.environ.get("OUTCOME_WINDOW_S", "600"))


def _schedule_outcome(chat_id: int, harvest_id: str) -> None:
    """Snapshot progress now + after OUTCOME_WINDOW_S, then back-fill the
    harvested record's ground-truth outcome. Best-effort background task."""
    async def _run() -> None:
        try:
            before = await asyncio.to_thread(supervisor.progress_snapshot, chat_id)
            await asyncio.sleep(OUTCOME_WINDOW_S)
            after = await asyncio.to_thread(supervisor.progress_snapshot, chat_id)
            outcome = supervisor.diff_progress(before, after)
            await asyncio.to_thread(db.backfill_messenger_outcome, harvest_id, outcome)
            log.info("outcome chat=%s record=%s progressed=%s reasons=%s", chat_id,
                     harvest_id, outcome.get("progressed"), outcome.get("reasons"))
        except Exception as e:
            log.info("outcome backfill skipped (chat=%s): %s", chat_id, e)
    try:
        asyncio.create_task(_run())
    except RuntimeError:
        pass  # no running loop — skip silently


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("trippet")


# ─── Rendering helper ────────────────────────────────────────────────────────
async def _send_pet(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_pet_card(update.effective_chat.id, ctx)


# Natural-language route into the green ledger. Deliberately narrow: it must
# mention the saving/carbon subject AND read as a question about it, so normal
# trip talk ("we saved money on flights") never hijacks the turn.
_ASK_SAVED_RE = re.compile(
    r"(how much|what'?s|whats|show|tell me).{0,30}"
    r"(saved|savings|carbon|co2|emissions|footprint|impact)"
    r"|(carbon|co2|emissions|green)\s+(ledger|total|so far|savings?)"
    r"|how green", re.IGNORECASE)


# ─── Handlers ────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    g = state.reset(update.effective_chat.id)
    _spoke_deathbed.discard(g.chat_id)   # re-arm voice moments for the fresh pet
    _spoke_graduated.discard(g.chat_id)
    await asyncio.to_thread(set_muted, g.chat_id, False)  # /start always wakes
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
    green.forget(chat_id)
    flights.forget(chat_id)
    _mute_cache.pop(chat_id, None)
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
    await maybe_speak_deathbed(update.effective_chat.id, ctx)


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
            f"no rooms{budget_note} for {trip.city} on "
            f"{_fmt_date_range(checkin, checkout)}. "
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
    # Graduation moment — the pet speaks its send-off (once per chat).
    if g.chat_id not in _spoke_graduated:
        _spoke_graduated.add(g.chat_id)
        await speak_pet(g.chat_id,
                        "we did it — i'm free! pack your bags, we're going to japan.",
                        ctx, mood="graduated", physical=g.pet.physical)


async def cmd_saved(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Green ledger: total CO2e avoided, EPA human units, scale-up line."""
    chat_id = update.effective_chat.id
    text = await asyncio.to_thread(green.render_saved, chat_id)
    try:
        await update.effective_chat.send_message(text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await update.effective_chat.send_message(text)


async def cmd_itinerary(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Green-routed day-by-day plan; transit savings counted once."""
    chat_id = update.effective_chat.id
    text = await asyncio.to_thread(greenplanner.build_itinerary, chat_id)
    msg = await update.effective_chat.send_message(text)
    supervisor.note_itinerary_posted(chat_id)
    await _green_react(ctx, chat_id, msg.message_id)


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Kill switch: the bot goes silent on this chat — no message logging,
    brain extraction, Stay22 polling, supervisor/Gemini turns, or heartbeat
    nudges. Nothing is deleted (unlike /reset), and the mute is persisted so a
    redeploy can't un-stop the chat. Explicit commands (/health, /scrub,
    /commit, /saved, /resume) still work. /resume or /start un-pauses."""
    chat_id = update.effective_chat.id
    await asyncio.to_thread(set_muted, chat_id, True)
    log.info("STOP chat=%s — automatic pipeline paused", chat_id)
    await update.effective_chat.send_message(
        "🛑 stopped. i'll stay quiet and stop reading messages until /resume or /start."
    )


async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not await asyncio.to_thread(is_muted, chat_id):
        await update.effective_chat.send_message("i wasn't stopped.")
        return
    await asyncio.to_thread(set_muted, chat_id, False)
    log.info("RESUME chat=%s", chat_id)
    await update.effective_chat.send_message("back. talk to me.")


async def log_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every non-command text message. Buffered by wire.py; consensus +
    Stay22 poll run behind a debounce so we don't burn the LLM / Stay22
    quota on every keystroke."""
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    if await asyncio.to_thread(is_muted, chat_id):
        return  # /stop means STOPPED: no logging, no brain, no supervisor
    speaker = (update.effective_user.first_name if update.effective_user else "someone") or "someone"
    log.info("msg chat_id=%s from=%s: %s", chat_id, speaker, update.message.text[:200])

    user_id = str(update.effective_user.id) if update.effective_user else "unknown"
    await asyncio.to_thread(db.log_chat_message, chat_id, user_id, speaker,
                            update.message.text, update.message.message_id)

    # Asking Tabi directly ("how much have we saved?", "carbon footprint?")
    # answers with the ledger — same card as /saved, no LLM round-trip needed.
    if _ASK_SAVED_RE.search(update.message.text):
        text = await asyncio.to_thread(green.render_saved, chat_id)
        try:
            await update.effective_chat.send_message(text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.effective_chat.send_message(text)
        return

    # TEMPORARY: "map" stays as a manual override for demos. The supervisor
    # now deals the deck itself when the stage reaches HOTELS.
    if re.search(r"\bmap\b", update.message.text, re.IGNORECASE):
        await open_hotel_cards(chat_id, ctx)
        supervisor.note_cards_dealt(chat_id)
        return

    # "flight 2" locks a flight option; picking the 🌱 one earns a dove
    locked = await asyncio.to_thread(supervisor.try_lock_flight, chat_id,
                                     update.message.text)
    if locked:
        lock_msg, was_greenest = locked
        msg = await update.effective_chat.send_message(lock_msg)
        if was_greenest:
            await _green_react(ctx, chat_id, msg.message_id)

    wire.note_message(chat_id, speaker, update.message.text)
    reconciled = await wire.maybe_process(chat_id)  # brain keeps its own debounce
    if reconciled is not None:
        g = state.get_or_create(chat_id)
        g.pet.refresh_mood()
        await asyncio.to_thread(state.persist_pet, g)
        asyncio.create_task(_sync_avatar(g, ctx))
        # If live prices just pushed the pet to death's door, let it speak once.
        await maybe_speak_deathbed(chat_id, ctx)

    # The supervisor gets a chance on EVERY message — its send-cooldown is
    # the pacing, not the reader's 3-message debounce. Skip the LLM turn
    # while the cooldown is hot, UNLESS someone sounds like they're backing
    # out — that's serious enough to always wake Tabi.
    urgent = supervisor.is_urgent(update.message.text)
    if supervisor.can_speak(chat_id) or urgent:
        decision = await asyncio.to_thread(supervisor.run_turn, chat_id,
                                           "message", urgent)
        await execute_decision(chat_id, decision, ctx)


# ─── Two-way voice: voice-in → transcribe → live loop → voice-out ───────────
async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """A group voice message: download it, transcribe with ElevenLabs Scribe,
    then feed the transcript into the SAME pipeline as a text message (wire +
    supervisor, same send-gate/cooldown). A plain-message reply is spoken back
    as a voice note (voice-in → voice-out); actions/decks go through the normal
    text path. Any STT/TTS failure degrades to text — never crashes the loop."""
    if not update.message or not update.message.voice:
        return
    chat_id = update.effective_chat.id
    if await asyncio.to_thread(is_muted, chat_id):
        return  # /stop means stopped — no reads, no reply
    speaker = (update.effective_user.first_name if update.effective_user else "someone") or "someone"
    user_id = str(update.effective_user.id) if update.effective_user else "unknown"

    # 1. Download the OGG/Opus voice note.
    try:
        tg_file = await update.message.voice.get_file()
        audio = bytes(await tg_file.download_as_bytearray())
    except Exception as e:
        log.warning("voice download failed (chat=%s): %s", chat_id, e)
        return

    # 2. Scribe STT. Failure → text fallback, never crash.
    transcript = await asyncio.to_thread(elevenlabs.transcribe, audio, "audio/ogg")
    if not transcript:
        try:
            await update.effective_chat.send_message("couldn't quite catch that — mind typing it?")
        except Exception:
            pass
        return
    log.info("voice chat=%s from=%s → %r", chat_id, speaker, transcript[:200])

    # 3. Feed the transcript in exactly like a text message.
    await asyncio.to_thread(db.log_chat_message, chat_id, user_id, speaker,
                            transcript, update.message.message_id)
    wire.note_message(chat_id, speaker, transcript)
    reconciled = await wire.maybe_process(chat_id)
    if reconciled is not None:
        g = state.get_or_create(chat_id)
        g.pet.refresh_mood()
        await asyncio.to_thread(state.persist_pet, g)
        asyncio.create_task(_sync_avatar(g, ctx))
        await maybe_speak_deathbed(chat_id, ctx)

    # 4. Same send-gate + cooldown as text. Speak the reply back as a voice note.
    urgent = supervisor.is_urgent(transcript)
    if not (supervisor.can_speak(chat_id) or urgent):
        return
    decision = await asyncio.to_thread(supervisor.run_turn, chat_id, "message", urgent)
    if decision.send and decision.message and decision.action == "none":
        g = state.get_or_create(chat_id)
        await speak_pet(chat_id, decision.message, ctx, mood=g.pet.mood, physical=g.pet.physical)
        if decision.harvest_id:  # keep the flywheel outcome parity with execute_decision
            _schedule_outcome(chat_id, decision.harvest_id)
    else:
        # actions (deck/flights/itinerary) or a swallowed send → normal path.
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
    app.add_handler(CommandHandler("saved", cmd_saved))
    app.add_handler(CommandHandler("itinerary", cmd_itinerary))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_error_handler(on_error)
    return app


def main() -> None:
    log.info("trippet online — polling. remember to disable BotFather group privacy.")
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
