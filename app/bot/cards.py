"""Hotel card deck — Tinder-style group decision engine.

Flow (PROJECT step 6-ish, demoed standalone for now):
  1. Basecamp is confirmed (TEMP: someone types "map" in chat; later the
     Phoebe agent calls `ensure_session` when the group converges).
  2. Everyone opens the Mini App and swipes right/left on ≤5 real hotels.
  3. When every participant has swiped every active card, the round resolves:
       - a hotel every participant liked → instant winner (needs ≥2 people)
       - otherwise the bottom half is eliminated (5 → 3 → 2 → 1)
     and survivors go to the next round, until one hotel remains.
  4. The winner card links out through Stay22 for booking.

State lives in memory (source of truth, same process as the bot) and is
mirrored to MongoDB on every mutation — sessions survive restarts via
`db.load_session`. All entry points take a lock: FastAPI card endpoints are
sync (threadpool) while the bot loop calls in from asyncio.
"""
from __future__ import annotations
import copy
import logging
import math
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from app.integrations import db
from app.integrations import green
from app.integrations import hotels

log = logging.getLogger("trippet.cards")

MAX_CARDS = 5

_SESSIONS: dict[int, dict] = {}
_LOCK = threading.Lock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Session lifecycle ───────────────────────────────────────────────────────
def ensure_session(chat_id: int, force: bool = False) -> dict:
    """Get-or-create the deck session for a group. BLOCKING (Stay22 + Mongo):
    call via asyncio.to_thread from the bot loop; FastAPI sync handlers are
    already off the event loop."""
    with _LOCK:
        s = _SESSIONS.get(chat_id)
        if s and not force:
            return s
        if not force:
            persisted = db.load_session(chat_id)
            if persisted:
                _SESSIONS[chat_id] = persisted
                log.info("session restored from Mongo (chat=%s)", chat_id)
                return persisted

    # Build the deck from the trip data we've extracted (Mongo-backed): group
    # size drives the green scoring (rooms the party needs), and the group's own
    # dates drive check-in/out when we have them (else fetch_hotel_cards falls
    # back to its default window).
    from app.core import state  # late import: state imports db, not cards
    trip = state.get_or_create(chat_id).trip
    group_size = int(trip.group_size or 4)
    ci = co = None
    try:
        if trip.dates and trip.dates.start and trip.dates.end:
            ci, co = trip.dates.start.isoformat(), trip.dates.end.isoformat()
    except Exception:
        ci = co = None
    deck = hotels.fetch_hotel_cards(max_cards=MAX_CARDS,  # network — outside lock
                                    guests=group_size,
                                    checkin=ci, checkout=co,
                                    chat_id=chat_id)  # per-group Stay22 attribution
    with _LOCK:
        s = {
            "chat_id": chat_id,
            "status": "swiping",            # swiping | decided
            "basecamp": deck["basecamp"],
            "checkin": deck["checkin"],
            "checkout": deck["checkout"],
            "source": deck["source"],
            "round": 1,
            "hotels": {c["id"]: c for c in deck["cards"]},
            "active": [c["id"] for c in deck["cards"]],
            "participants": {},             # user_id -> {name, joined_at}
            "swipes": [],                   # {user_id, hotel_id, dir, round, ts, meta}
            "history": [],                  # per-round tally + eliminations
            "winner": None,
            "created_at": _utcnow(),
        }
        _SESSIONS[chat_id] = s
    db.save_session(s)
    log.info("session started (chat=%s, %d cards, source=%s)",
             chat_id, len(deck["cards"]), deck["source"])
    return s


def get_session(chat_id: int) -> Optional[dict]:
    with _LOCK:
        return _SESSIONS.get(chat_id)


def forget(chat_id: int) -> None:
    """/reset: drop the in-memory session (Mongo nuke handles persistence)."""
    with _LOCK:
        _SESSIONS.pop(chat_id, None)


# ─── Views (what the UI polls) ───────────────────────────────────────────────
def view_for(chat_id: int, user_id: str, name: str) -> dict:
    """Deck state for one user. Registers them as a participant — opening the
    deck means your swipes are expected before the round can resolve."""
    s = ensure_session(chat_id)
    user_id = str(user_id)
    with _LOCK:
        if user_id not in s["participants"]:
            s["participants"][user_id] = {"name": name or "guest", "joined_at": _utcnow()}
            snapshot = copy.deepcopy(s)
        else:
            s["participants"][user_id]["name"] = name or s["participants"][user_id]["name"]
            snapshot = None
        view = _build_view(s, user_id)
    if snapshot:
        db.save_session(snapshot)
    return view


def _swiped_ids(s: dict, user_id: str) -> set[str]:
    return {sw["hotel_id"] for sw in s["swipes"]
            if sw["user_id"] == user_id and sw["round"] == s["round"]}


def _build_view(s: dict, user_id: str) -> dict:
    """Caller holds _LOCK."""
    done = _swiped_ids(s, user_id)
    remaining = [s["hotels"][hid] for hid in s["active"] if hid not in done]
    return {
        "status": s["status"],
        "basecamp": s["basecamp"],
        "checkin": s["checkin"],
        "checkout": s["checkout"],
        "round": s["round"],
        "total_rounds_hint": max(1, math.ceil(math.log2(max(2, MAX_CARDS)))),
        "active_count": len(s["active"]),
        "cards": remaining,
        "active_cards": [s["hotels"][hid] for hid in s["active"]],
        "you_done": not remaining and s["status"] == "swiping",
        "participants": [
            {"name": p["name"],
             "done": not any(hid not in _swiped_ids(s, uid) for hid in s["active"])}
            for uid, p in s["participants"].items()
        ],
        "tally": _tally(s),
        "winner": s["hotels"].get(s["winner"]) if s["winner"] else None,
        "history": s["history"],
    }


def _tally(s: dict) -> dict:
    """Per-active-hotel like/dislike counts for the current round."""
    t = {hid: {"likes": 0, "dislikes": 0} for hid in s["active"]}
    for sw in s["swipes"]:
        if sw["round"] == s["round"] and sw["hotel_id"] in t:
            key = "likes" if sw["dir"] == "right" else "dislikes"
            t[sw["hotel_id"]][key] += 1
    return t


# ─── Swipes + decision algorithm ─────────────────────────────────────────────
def record_swipe(chat_id: int, user_id: str, name: str, hotel_id: str,
                 direction: str, meta: Optional[dict[str, Any]] = None) -> dict:
    """One swipe. Dedupes per (user, hotel, round), logs analytics to Mongo,
    resolves the round if this was the last outstanding swipe. Returns the
    user's fresh view so the UI needs no second request."""
    s = ensure_session(chat_id)
    user_id = str(user_id)
    direction = "right" if direction == "right" else "left"

    with _LOCK:
        if user_id not in s["participants"]:
            s["participants"][user_id] = {"name": name or "guest", "joined_at": _utcnow()}
        already = any(sw["user_id"] == user_id and sw["hotel_id"] == hotel_id
                      and sw["round"] == s["round"] for sw in s["swipes"])
        valid = s["status"] == "swiping" and hotel_id in s["active"] and not already
        swipe_round = s["round"]
        if valid:
            s["swipes"].append({
                "user_id": user_id, "name": name or "guest", "hotel_id": hotel_id,
                "dir": direction, "round": swipe_round, "ts": _utcnow(),
                "meta": meta or {},
            })
            _maybe_resolve_round(s)
        decided_now = valid and s["status"] == "decided" and not s.get("green_credited")
        if decided_now:
            s["green_credited"] = True
        view = _build_view(s, user_id)
        snapshot = copy.deepcopy(s) if valid else None

    if snapshot:
        db.save_session(snapshot)
        db.log_event(chat_id, user_id, "swipe", hotel_id,
                     {**(meta or {}), "direction": direction, "round": swipe_round})
    if decided_now:
        _credit_green_winner(snapshot)
        _persist_deck_winner(snapshot)
    return view


def _credit_green_winner(s: dict) -> None:
    """Credit the ledger when the group's winning stay beats the deck average
    footprint — the counterfactual being "any of these five, at random".
    Outside the lock on purpose: Mongo writes must never stall a swipe."""
    try:
        winner = s["hotels"][s["winner"]]
        deck = list(s["hotels"].values())
        group_size = max(2, len(s["participants"]))
        stays = [c.get("est_stay_kg") or green.stay_footprint_kg(
            c, group_size, c.get("nights") or 2) for c in deck]
        winner_kg = winner.get("est_stay_kg") or green.stay_footprint_kg(
            winner, group_size, winner.get("nights") or 2)
        avg = sum(stays) / max(1, len(stays))
        if winner_kg >= avg:
            log.info("green: winner %s is not below deck average (%.0f vs %.0f) — no credit",
                     winner["name"][:30], winner_kg, avg)
            return
        green.record_saving(s["chat_id"], "hotel", avg - winner_kg,
                            f"picked the low-carbon stay: {winner['name']}",
                            {"winner_stay_kg": winner_kg,
                             "deck_avg_stay_kg": round(avg, 1),
                             "group_size": group_size,
                             "nights": winner.get("nights")})
    except Exception as e:
        log.warning("green winner credit failed: %s", e)


def _persist_deck_winner(s: dict) -> None:
    """Store the agreed hotel into trip state (trip_plans.deck_winner) so
    /commit can book the hotel the group actually chose, not a fresh best-rated
    pick. This is data we already hold on the winning card — the Allez URL is
    saved VERBATIM as Stay22 returned it, never constructed. Fail-open like the
    green credit above: any error logs and returns, the deck flow never breaks."""
    try:
        w = s["hotels"][s["winner"]]
        from app.core import state  # late import: state imports db, not cards
        try:
            city = state.get_or_create(s["chat_id"]).trip.city or s.get("basecamp")
        except Exception:
            city = s.get("basecamp")
        dw = {
            "hotel_id": str(w.get("id") or ""),
            "name": w.get("name") or "",
            "price_total": w.get("price_total"),
            "rating": w.get("rating"),
            "book_url": w.get("url") or "",   # verbatim Allez URL from Stay22
            "city": city,
        }
        db.update_plan(s["chat_id"], {"deck_winner": dw})
        log.info("deck_winner persisted (chat=%s): %s @id=%s",
                 s["chat_id"], (dw["name"] or "?")[:40], dw["hotel_id"] or "?")
    except Exception as e:
        log.warning("deck_winner persist failed: %s", e)


def _maybe_resolve_round(s: dict) -> None:
    """Caller holds _LOCK. Round resolves only when EVERY participant has
    swiped EVERY active hotel — that's the 'whole group decides' rule."""
    for uid in s["participants"]:
        done = {sw["hotel_id"] for sw in s["swipes"]
                if sw["user_id"] == uid and sw["round"] == s["round"]}
        if any(hid not in done for hid in s["active"]):
            return

    tally = _tally(s)
    n_people = len(s["participants"])

    def score(hid: str) -> tuple:
        t, h = tally[hid], s["hotels"][hid]
        return (t["likes"] - t["dislikes"], t["likes"],
                h["rating"] or 0, -h["price_total"])

    ranked = sorted(s["active"], key=score, reverse=True)

    # Unanimous like → instant winner (only meaningful with 2+ people).
    unanimous = [hid for hid in ranked if tally[hid]["likes"] == n_people]
    if unanimous and n_people >= 2:
        _decide(s, unanimous[0], tally, reason="unanimous")
        return

    keep = max(1, math.ceil(len(s["active"]) / 2))  # 5→3→2→1
    survivors, eliminated = ranked[:keep], ranked[keep:]
    s["history"].append({
        "round": s["round"],
        "tally": tally,
        "eliminated": [{"id": hid, "name": s["hotels"][hid]["name"]} for hid in eliminated],
    })
    if len(survivors) == 1:
        _decide(s, survivors[0], tally, reason="last_standing", already_logged=True)
        return

    s["active"] = survivors
    s["round"] += 1
    log.info("round %d begins (chat=%s): %d hotels left",
             s["round"], s["chat_id"], len(survivors))


def _decide(s: dict, winner_id: str, tally: dict, reason: str,
            already_logged: bool = False) -> None:
    """Caller holds _LOCK."""
    if not already_logged:
        s["history"].append({"round": s["round"], "tally": tally, "eliminated": []})
    s["status"] = "decided"
    s["winner"] = winner_id
    s["decided_reason"] = reason
    s["decided_at"] = _utcnow()
    log.info("DECIDED (chat=%s): %s — %s", s["chat_id"],
             s["hotels"][winner_id]["name"], reason)


def results(chat_id: int) -> dict:
    """Tally + winner + Mongo analytics rollup (for /results and the bot)."""
    s = get_session(chat_id) or db.load_session(chat_id)
    if not s:
        return {"status": "none"}
    with _LOCK:
        base = {
            "status": s["status"],
            "basecamp": s["basecamp"],
            "round": s["round"],
            "winner": s["hotels"].get(s["winner"]) if s.get("winner") else None,
            "decided_reason": s.get("decided_reason"),
            "participants": [p["name"] for p in s["participants"].values()],
            "tally": _tally(s),
            "history": s["history"],
            "total_swipes": len(s["swipes"]),
        }
    base["analytics"] = db.analytics_summary(chat_id)
    return base
