"""Telegram bot layer. aiogram v3, Privacy Mode expected OFF at BotFather.

The bot:
  - ingests every message → forwards to consensus engine
  - broadcasts pet status updates after health changes
  - handles /start (seed the trip), /health (poke status), /pet (pet snapshot)
  - Phoebe personality lines woven into replies
"""
from __future__ import annotations
import asyncio
import io
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, BufferedInputFile,
    InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo,
)

from ..config import (
    TELEGRAM_BOT_TOKEN, PUBLIC_BASE_URL, GAMIFY, pet_state,
)
from ..models.schemas import TripState
from ..storage.repo import Repo, get_repo
from ..services import consensus, health, deck as deck_svc
from ..services.events import bus, T_HEALTH_CHANGED, T_PHASE_CHANGED, T_UNANIMOUS_MATCH
from ..services.pet_render import status_line, render_pet_svg_for_state


bot: Optional[Bot] = None
dp = Dispatcher()

# Per-chat rolling window of recent messages for consensus (dumb + fast)
_chat_buffers: dict[str, list[str]] = {}
_BUFFER_SIZE = 20


def get_bot() -> Bot:
    global bot
    if bot is None:
        if not TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
        bot = Bot(TELEGRAM_BOT_TOKEN)
    return bot


# ─── Phoebe personality helpers ──────────────────────────────────────────────
def phoebe_intro() -> str:
    return (
        "hi. i'm phoebe. i'm the pet. i live here now.\n"
        "i'm dying because none of you have committed to anything. "
        "start talking about the trip and i'll get better. "
        "the longer you stall the more i die. this is not a threat, "
        "it's biology."
    )


def phoebe_heal(trigger: str) -> str:
    return {
        "heal_constraints_locked": "budget locked in. i can feel my legs again.",
        "heal_cities_resolved": "cities! i have a shape now. keep going.",
        "heal_dates_mapped": "dates!! we have a REAL trip. i'm almost stable.",
        "unanimous_match": "you all picked the same one. THAT is love. mustache growing.",
        "verified_booking": "IT'S BOOKED. golden mustache. packed suitcase. i'm cured. thank you.",
    }.get(trigger, "something good happened. i felt it.")


def phoebe_decay(trigger: str) -> str:
    if trigger.startswith("market:"):
        return "prices just moved against you. this is what i've been warning about. do something."
    if trigger == "inactivity_24h":
        return "24 hours of nothing. i am extremely disappointed. also cold."
    return "i lost some health. i don't know why. probably you."


# ─── Handlers ────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(m: Message) -> None:
    repo = await get_repo()
    chat_id = str(m.chat.id)
    trip = await repo.get_trip(chat_id) or TripState(chat_id=chat_id)
    if m.from_user and str(m.from_user.id) not in trip.active_user_ids:
        trip.active_user_ids.append(str(m.from_user.id))
    await repo.upsert_trip(trip)
    await m.answer(phoebe_intro())
    await _send_pet_snapshot(chat_id, trip)


@dp.message(Command("pet"))
async def cmd_pet(m: Message) -> None:
    repo = await get_repo()
    trip = await repo.get_trip(str(m.chat.id))
    if trip:
        await _send_pet_snapshot(str(m.chat.id), trip)


@dp.message(Command("health"))
async def cmd_health(m: Message) -> None:
    repo = await get_repo()
    trip = await repo.get_trip(str(m.chat.id))
    if trip:
        await m.answer(status_line(trip.current_health, trip.current_phase))


@dp.message(Command("swipe"))
async def cmd_swipe(m: Message) -> None:
    """Manually surface the mini app link (also happens automatically at 50%)."""
    await _send_miniapp_link(str(m.chat.id))


@dp.message(F.text)
async def on_message(m: Message) -> None:
    if not m.text or m.text.startswith("/"):
        return
    repo = await get_repo()
    chat_id = str(m.chat.id)
    trip = await repo.get_trip(chat_id) or TripState(chat_id=chat_id)
    # register the user if new
    if m.from_user and str(m.from_user.id) not in trip.active_user_ids:
        trip.active_user_ids.append(str(m.from_user.id))
    prev = trip.model_copy(deep=True)

    # accumulate rolling context
    buf = _chat_buffers.setdefault(chat_id, [])
    speaker = (m.from_user.first_name if m.from_user else "someone") or "someone"
    buf.append(f"{speaker}: {m.text}")
    if len(buf) > _BUFFER_SIZE:
        del buf[: len(buf) - _BUFFER_SIZE]

    trip = await consensus.extract_and_merge(trip, "\n".join(buf))
    trip = await health.reconcile_and_heal(repo, trip, prev)
    await repo.upsert_trip(trip)

    # auto-surface mini app when we cross into swiping
    if prev.current_phase != "swiping" and trip.current_phase == "swiping":
        await _send_miniapp_link(chat_id)


# ─── Broadcast helpers ───────────────────────────────────────────────────────
async def _send_pet_snapshot(chat_id: str, trip: TripState) -> None:
    b = get_bot()
    state = pet_state(trip.current_health)
    svg = render_pet_svg_for_state(state).encode("utf-8")
    caption = status_line(trip.current_health, trip.current_phase)
    try:
        # Telegram doesn't render SVG; fall back to text-only if photo path fails.
        # Best path is rendering to PNG server-side, but for the hackathon: text ok.
        await b.send_message(chat_id=int(chat_id), text=caption)
    except Exception as e:
        print(f"[bot] pet snapshot send failed: {e}")


async def _send_miniapp_link(chat_id: str) -> None:
    b = get_bot()
    url = f"{PUBLIC_BASE_URL}/miniapp/?chat_id={chat_id}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏨 Swipe hotels", web_app=WebAppInfo(url=url))
    ]])
    await b.send_message(
        chat_id=int(chat_id),
        text="🐾 pet stabilized. deck's up — swipe and let's see if you agree on anything:",
        reply_markup=kb,
    )


# ─── Event bus subscriptions ─────────────────────────────────────────────────
async def _on_health_changed(payload: dict) -> None:
    b = get_bot()
    chat_id = int(payload["chat_id"])
    delta = payload["delta"]
    trigger = payload["trigger"]
    if delta >= 5:
        line = phoebe_heal(trigger)
    elif delta <= -5:
        line = phoebe_decay(trigger)
    else:
        return
    await b.send_message(chat_id=chat_id, text=f"{line}\n\n{status_line(payload['health'], 'in flight', trigger)}")


async def _on_phase_changed(payload: dict) -> None:
    b = get_bot()
    if payload["phase"] == "swiping":
        await _send_miniapp_link(str(payload["chat_id"]))
    elif payload["phase"] == "booked":
        await b.send_message(chat_id=int(payload["chat_id"]),
                             text="🌟 golden mustache achieved. the trip is REAL. thank you for keeping me alive.")


async def _on_unanimous_match(payload: dict) -> None:
    b = get_bot()
    await b.send_message(
        chat_id=int(payload["chat_id"]),
        text=f"🎉 UNANIMOUS on {payload['hotel_name']}. i'm delivering the booking link now."
    )


def subscribe() -> None:
    bus.on(T_HEALTH_CHANGED, _on_health_changed)
    bus.on(T_PHASE_CHANGED, _on_phase_changed)
    bus.on(T_UNANIMOUS_MATCH, _on_unanimous_match)


async def process_update_dict(update_data: dict) -> None:
    """Entry point from FastAPI webhook."""
    from aiogram.types import Update
    upd = Update.model_validate(update_data)
    await dp.feed_update(get_bot(), upd)
