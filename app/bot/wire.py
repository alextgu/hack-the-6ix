"""Live loop: chat → constraints → Stay22 → health → pet.

Sits between the bot and the rest of the modules. Owns the debounce
timers, message buffer per chat, blocker tracking, and Stay22 rate
guard. Does NOT rewrite brain/state/health/pet/stay22 — just glues.

Blockers (city TIE, no date overlap) are stashed here for Phoebe to
consume later without needing to re-parse notes strings.
"""
from __future__ import annotations
import asyncio
import logging
import re
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from typing import Optional

from app.agents import brain
from app.integrations import stay22
from app.core import state
from app.core import health


log = logging.getLogger("trippet.wire")


# ─── Tuning ─────────────────────────────────────────────────────────────────
CONSENSUS_MIN_MESSAGES = 3     # need this many new msgs AND ↓
CONSENSUS_MIN_INTERVAL = 10.0  # this many seconds since last consensus run
STAY22_MIN_INTERVAL    = 60.0  # per-chat guard on top of stay22.py's global 12s throttle
BUFFER_MAX = 40                # keep last N messages per chat for the model


# ─── Per-chat wire-up state (kept OUT of state.py to stay additive) ─────────
_messages:            dict[int, deque] = defaultdict(lambda: deque(maxlen=BUFFER_MAX))
_new_msg_count:       dict[int, int]   = defaultdict(int)
_last_consensus_at:   dict[int, float] = {}
_last_stay22_at:      dict[int, float] = {}
_blockers:            dict[int, list[str]] = defaultdict(list)
_last_reconciled:     dict[int, dict]  = {}
_signal_pending:      set[int]         = set()   # chats with an unextracted answer


# ─── Public: called by the bot's message handler ────────────────────────────
# A message that plausibly carries a trip constraint must not sit in the buffer
# waiting for two more messages to show up. Live failure: Kaamil answered the
# pet's "name one city" with exactly "tokyo" — one message, so consensus never
# ran, trip.city stayed None, and five minutes later the pet nagged for the
# city it had just been given ("tokyo is still just a rumor"). The model even
# said so in its own reasoning: "Even though Tokyo was mentioned, the system
# still lists 'city' as missing".
#
# Deliberately loose: a false positive costs one extraction call, a false
# negative makes the pet look like it wasn't listening.
_SIGNAL_RE = re.compile(
    r"\b(tokyo|kyoto|osaka|sapporo|fukuoka|nagoya|okinawa|hiroshima|nara|kobe"
    r"|yokohama|hakone|nikko|kanazawa|sendai|niseko|hakodate|shibuya|shinjuku"
    r"|japan)\b"
    r"|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
    r"|\b(spring|summer|autumn|fall|winter|weekend|week|month|new year)\b"
    r"|\$\s?\d|\d\s?k\b|\b\d{3,}\b"                      # money
    r"|\bi'?m in\b|\bcount me in\b|\bi'?m down\b|\bdown for\b|\bworks for me\b"
    r"|\byes\b|\byeah\b|\bsure\b|\bok(ay)?\b",           # agreement
    re.IGNORECASE)


def carries_signal(text: str) -> bool:
    """Does this message plausibly contain a city/date/budget/commitment?"""
    return bool(_SIGNAL_RE.search(text or ""))


def note_message(chat_id: int, sender: str, text: str) -> None:
    """Buffer one incoming message. Cheap — safe on every message."""
    _messages[chat_id].append({"sender": sender, "text": text})
    _new_msg_count[chat_id] += 1
    if carries_signal(text):
        # Count it as enough on its own so the next maybe_process extracts.
        _signal_pending.add(chat_id)


def reset_chat(chat_id: int) -> None:
    """/reset: drop every buffer/timer this module holds for a chat."""
    for store in (_messages, _new_msg_count, _last_consensus_at,
                  _last_stay22_at, _blockers, _last_reconciled):
        store.pop(chat_id, None)
    _signal_pending.discard(chat_id)


def get_blockers(chat_id: int) -> list[str]:
    return list(_blockers.get(chat_id, []))


def get_last_reconciled(chat_id: int) -> Optional[dict]:
    return _last_reconciled.get(chat_id)


async def maybe_process(chat_id: int) -> Optional[dict]:
    """Run consensus + optional Stay22 poll if debounce says we should.
    Returns the reconciled trip dict (with `notes`), or None if we skipped."""
    if not _should_run_consensus(chat_id):
        return None
    _last_consensus_at[chat_id] = _now()
    _new_msg_count[chat_id] = 0
    _signal_pending.discard(chat_id)

    msgs = list(_messages[chat_id])
    if not msgs:
        return None

    # brain.extract() is blocking (network call to Gemini) → off-thread it
    try:
        extraction = await asyncio.to_thread(brain.extract, msgs)
    except Exception as e:
        log.warning("brain.extract failed: %s", e)
        return None

    reconciled = brain.aggregate(extraction)
    _last_reconciled[chat_id] = reconciled

    _write_trip_to_state(chat_id, reconciled)
    _refresh_blockers(chat_id, reconciled)

    await _maybe_query_stay22(chat_id, reconciled)
    return reconciled


# ─── Debounce ───────────────────────────────────────────────────────────────
def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _should_run_consensus(chat_id: int) -> bool:
    """Chatter waits for CONSENSUS_MIN_MESSAGES; a message that looks like an
    actual answer jumps the queue. The interval guard still applies either way,
    so this can't turn into an extraction call per keystroke."""
    enough = _new_msg_count[chat_id] >= CONSENSUS_MIN_MESSAGES
    if not enough and chat_id not in _signal_pending:
        return False
    last = _last_consensus_at.get(chat_id)
    if last is not None and (_now() - last) < CONSENSUS_MIN_INTERVAL:
        return False
    return True


# ─── Write reconciled fields into state.py (only what's non-null) ───────────
def _parse_iso(s: object) -> Optional[date]:
    try:
        return date.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


def _write_trip_to_state(chat_id: int, r: dict) -> None:
    g = state.get_or_create(chat_id)
    trip = g.trip

    if r.get("city"):
        trip.city = r["city"]
    if r.get("budget_per_person") is not None:
        trip.budget_per_person = int(r["budget_per_person"])
    if r.get("group_size"):
        trip.group_size = int(r["group_size"])

    dw = r.get("dates") or {}
    start = _parse_iso(dw.get("start"))
    end   = _parse_iso(dw.get("end"))
    if start and end and start <= end:
        trip.dates = state.DateWindow(start=start, end=end)


# ─── Blockers (stashed here; Phoebe will read via get_blockers) ─────────────
def _refresh_blockers(chat_id: int, r: dict) -> None:
    notes = r.get("notes") or {}
    out: list[str] = []
    if r.get("city") is None and "TIE" in (notes.get("city") or ""):
        out.append(f"city_tie: {notes['city']}")
    dw = r.get("dates") or {}
    if not (dw.get("start") and dw.get("end")) and "no overlap" in (notes.get("dates") or ""):
        out.append(f"date_no_overlap: {notes['dates']}")
    if r.get("budget_per_person") is None:
        out.append(f"budget_missing: {notes.get('budget', 'no budget stated')}")
    _blockers[chat_id] = out


# ─── Stay22 → health (null-safe, rate-guarded) ──────────────────────────────
async def _maybe_query_stay22(chat_id: int, r: dict) -> None:
    city = r.get("city")
    dw = r.get("dates") or {}
    start, end = dw.get("start"), dw.get("end")
    if not (city and start and end):
        log.debug("stay22 skip (chat=%s): still figuring out the trip", chat_id)
        return
    now = _now()
    last = _last_stay22_at.get(chat_id)
    if last and (now - last) < STAY22_MIN_INTERVAL:
        log.debug("stay22 skip (chat=%s): per-chat rate guard", chat_id)
        return
    _last_stay22_at[chat_id] = now

    guests = int(r.get("group_size") or 2)
    try:
        snap = await asyncio.to_thread(stay22.get_stay, city, start, end, guests)
    except Exception as e:
        log.warning("stay22.get_stay raised (chat=%s): %s — keeping last-known market", chat_id, e)
        return
    if not snap:
        log.warning("stay22 returned None (chat=%s)", chat_id)
        return

    price = snap.get("price_median") or snap.get("price_cheapest")
    count = snap.get("result_count") or 0
    if not price or count == 0:
        log.info("stay22: no prices for %s %s→%s (results=%d)", city, start, end, count)
        return

    # Availability proxy: results / pageSize as a 0..100 %.
    availability_pct = min(100.0, (count / 30.0) * 100.0)
    curr = state.MarketSnapshot(avg_price_usd=float(price), rooms_available=availability_pct)

    g = state.get_or_create(chat_id)
    if g.last_market is not None:
        new_phys = health.apply_market_delta(g.pet.physical, g.last_market, curr)
        log.info("wire: physical %d → %d (Δprice %+.1f, avail %.0f%%)",
                 g.pet.physical, new_phys, price - g.last_market.avg_price_usd, availability_pct)
        g.pet.physical = new_phys
    else:
        log.info("wire: baseline market snapshot for %s at $%.0f, avail %.0f%%",
                 city, price, availability_pct)
    g.last_market = curr
    g.pet.refresh_mood()
    await asyncio.to_thread(state.persist_pet, g)
