"""
Kamagachi voice module — ElevenLabs TTS bridge for Phoebe the guilt-tripping pet.

Graceful degradation:
    - If ELEVENLABS_API_KEY is missing or the TTS call fails, we log the issue
      and fall back to sending the guilt-trip line as a plain text message so
      the demo keeps flowing.

Demo tool-call:
    - `onboard_prompt(chat_id, user_id, user_display)` is the target the LLM
      tool-router hits when someone hasn't onboarded. It drops a voice note
      addressing the user by name plus an inline WebApp button that opens the
      miniapp onboarding page.

Public API:
    attach_bot(bot), attach_repo(repo), subscribe(),
    synthesize(text, voice_id), pick_voice(health), phoebe_line(context),
    escalate_voice(chat_id, context), onboard_prompt(chat_id, user_id, name).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from kamagachi.app import config
from kamagachi.app.services import events

log = logging.getLogger("kamagachi.voice")

_ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
_MODEL_ID = "eleven_turbo_v2_5"
_VOICE_SETTINGS = {
    "stability": 0.45,
    "similarity_boost": 0.75,
    "style": 0.55,
    "use_speaker_boost": True,
}

_bot: Any = None
_repo: Any = None


def attach_bot(bot: Any) -> None:
    """Wire in the aiogram Bot instance (called once at startup)."""
    global _bot
    _bot = bot


def attach_repo(repo: Any) -> None:
    """Wire in the storage repo (called once at startup)."""
    global _repo
    _repo = repo


async def synthesize(text: str, voice_id: str) -> Optional[bytes]:
    """POST to ElevenLabs and return raw MP3 bytes, or None on failure."""
    api_key = getattr(config, "ELEVENLABS_API_KEY", None)
    if not api_key:
        log.warning("ELEVENLABS_API_KEY missing — skipping TTS, will fall back to text.")
        return None
    url = _ELEVEN_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    body = {"text": text, "model_id": _MODEL_ID, "voice_settings": _VOICE_SETTINGS}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                log.error("ElevenLabs TTS failed %s: %s", resp.status_code, resp.text[:200])
                return None
            return resp.content
    except Exception as exc:  # noqa: BLE001
        log.exception("ElevenLabs request errored: %s", exc)
        return None


def pick_voice(health: int) -> str:
    """Dying/sick states get the faint voice; everyone else gets the bright one."""
    state = config.pet_state(health)
    if state in ("dying", "sick"):
        return config.ELEVENLABS_VOICE_DYING
    return config.ELEVENLABS_VOICE_ALIVE


def phoebe_line(context: dict) -> str:
    """Rules-based guilt-trip line generator. Short, in-character, <200 chars."""
    state = context.get("state") or config.pet_state(context.get("health", 100))
    trigger = context.get("trigger", "") or ""
    stallers = context.get("stallers") or []
    city = context.get("city")
    price_delta = context.get("price_delta")

    if trigger.startswith("market:") and price_delta and price_delta > 15 and city:
        return (
            f"Rooms in {city} just jumped ${int(price_delta)} while you were arguing. "
            "This is exactly what I was warning you about."
        )
    if trigger == "phase:matched":
        return "You matched. I can breathe again. Don't stop now — lock the dates."
    if trigger == "phase:booked":
        return "It's booked. I'm literally glowing. Thank you. See you on the trip."
    if stallers:
        names = ", ".join(f"@{n.lstrip('@')}" for n in stallers[:3])
        return f"{names} — hi. I know you can see this. The pet is dying and it's kind of your fault right now."
    if state == "dying":
        return (
            "It's... cold. Nobody's talking. If you don't book something in the next hour "
            "I'm... going to sleep for a very long time."
        )
    if state == "sick":
        return "I don't feel great. Someone swipe a destination. Please. I'm asking nicely."
    if state in ("happy", "golden"):
        return "Update from the trip: things are actually happening. Keep swiping."
    return "Hey. Still here. Still waiting. Pick a city."


async def _cooldown_ok(chat_id: str) -> tuple[bool, Any]:
    """Return (ok_to_send, trip_state). trip_state may be None if repo is dumb."""
    if _repo is None:
        return True, None
    try:
        trip = await _repo.get_trip(chat_id)
    except Exception:  # noqa: BLE001
        log.exception("repo.get_trip failed for %s", chat_id)
        return True, None
    if trip is None:
        return True, None
    last = getattr(trip, "last_voice_call_at", None)
    if last is None:
        return True, trip
    min_minutes = getattr(config.GAMIFY, "VOICE_ESCALATION_MIN_MINUTES", 30)
    if datetime.now(timezone.utc) - last < timedelta(minutes=min_minutes):
        return False, trip
    return True, trip


async def _persist_voice_stamp(chat_id: str, trip: Any) -> None:
    if _repo is None or trip is None:
        return
    try:
        trip.last_voice_call_at = datetime.now(timezone.utc)
        await _repo.save_trip(trip)
    except Exception:  # noqa: BLE001
        log.exception("failed to persist last_voice_call_at for %s", chat_id)


async def _send_voice_or_text(chat_id: str, line: str, voice_id: str, reply_markup=None) -> None:
    if _bot is None:
        log.error("voice._bot not attached — cannot deliver to %s", chat_id)
        return
    mp3 = await synthesize(line, voice_id)
    if mp3:
        try:
            from aiogram.types import BufferedInputFile
            await _bot.send_voice(
                chat_id=chat_id,
                voice=BufferedInputFile(mp3, filename="phoebe.mp3"),
                caption=line[:1024],
                reply_markup=reply_markup,
            )
            return
        except Exception:  # noqa: BLE001
            log.exception("send_voice failed, falling back to text for %s", chat_id)
    try:
        await _bot.send_message(chat_id=chat_id, text=line, reply_markup=reply_markup)
    except Exception:  # noqa: BLE001
        log.exception("send_message fallback also failed for %s", chat_id)


async def escalate_voice(chat_id: str, context: dict) -> None:
    """Main entry point: drop a guilt-trip voice note into the chat."""
    ok, trip = await _cooldown_ok(chat_id)
    if not ok:
        log.info("voice escalate skipped for %s (cooldown active)", chat_id)
        return
    health = context.get("health")
    if health is None and trip is not None:
        health = getattr(trip, "health", 50)
    health = int(health if health is not None else 50)
    context.setdefault("health", health)
    context.setdefault("state", config.pet_state(health))
    line = phoebe_line(context)
    voice_id = pick_voice(health)
    await _send_voice_or_text(chat_id, line, voice_id)
    await _persist_voice_stamp(chat_id, trip)


async def onboard_prompt(chat_id: str, user_id: str, user_display: str) -> None:
    """Tool-call target: nudge an un-onboarded user with a voice note + WebApp button."""
    name = (user_display or "friend").lstrip("@")
    line = (
        f"@{name} — hi. I'm the pet. I live here now. "
        "Tap the button to tell the group your budget and dates so I stop dying."
    )
    reply_markup = None
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
        base = getattr(config, "PUBLIC_BASE_URL", "").rstrip("/")
        url = f"{base}/miniapp/onboard?chat_id={chat_id}&user_id={user_id}"
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Onboard me", web_app=WebAppInfo(url=url))
            ]]
        )
    except Exception:  # noqa: BLE001
        log.exception("failed to build onboard InlineKeyboardMarkup")
    voice_id = config.ELEVENLABS_VOICE_ALIVE
    await _send_voice_or_text(chat_id, line, voice_id, reply_markup=reply_markup)


async def _on_phase_changed(payload: dict) -> None:
    phase = payload.get("phase")
    chat_id = payload.get("chat_id")
    if not chat_id or phase not in ("matched", "booked"):
        return
    context = {
        "health": payload.get("health", 90),
        "state": "golden" if phase == "booked" else "happy",
        "trigger": f"phase:{phase}",
    }
    line = phoebe_line(context)
    voice_id = config.ELEVENLABS_VOICE_ALIVE
    await _send_voice_or_text(chat_id, line, voice_id)


def subscribe() -> None:
    """Wire event-bus handlers. Call once at app startup."""
    async def _on_escalate(p: dict) -> None:
        await escalate_voice(p["chat_id"], p)

    async def _on_onboard(p: dict) -> None:
        await onboard_prompt(p["chat_id"], p["user_id"], p.get("user_display", ""))

    events.bus.on(events.T_VOICE_ESCALATE, _on_escalate)
    events.bus.on(events.T_ONBOARD_REQUEST, _on_onboard)
    events.bus.on(events.T_PHASE_CHANGED, _on_phase_changed)
    log.info("voice module subscribed to bus topics.")
