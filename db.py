"""MongoDB Atlas layer — card sessions, swipes, analytics.

Design rules:
  - NEVER raises to callers. Any Mongo failure logs a warning and the app
    keeps running on the in-memory state in `cards.py`. Mongo is the mirror
    + analytics sink, not the hot path.
  - Sync pymongo on purpose: the FastAPI card endpoints are plain `def`
    handlers (threadpool), and bot-loop callers go through asyncio.to_thread.

Env:
  MONGODB_URI  — Atlas SRV string (in .env, gitignored)
  MONGODB_DB   — database name (default: trippet)

Collections:
  card_sessions — one doc per group chat deck (upserted on every mutation)
  analytics     — append-only interaction events from the swipe UI
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()  # idempotent — covers `uvicorn api:app` runs that skip run.py

log = logging.getLogger("trippet.db")

_client = None          # lazy MongoClient
_next_retry_at = 0.0    # failed connects back off instead of disabling forever
_RETRY_COOLDOWN_S = 60.0


def _db():
    """Return the Database handle, or None if Mongo is unavailable.
    A failed connect (Atlas hiccup, IP-list propagation) backs off for
    _RETRY_COOLDOWN_S and then tries again — never permanently gives up."""
    global _client, _next_retry_at
    if _client is not None:
        return _client[os.environ.get("MONGODB_DB", "trippet")]

    import time
    if time.monotonic() < _next_retry_at:
        return None
    _next_retry_at = time.monotonic() + _RETRY_COOLDOWN_S

    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        log.warning("MONGODB_URI not set — running memory-only, no persistence")
        return None
    try:
        import certifi
        from pymongo import MongoClient
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=8000,
            tlsCAFile=certifi.where(),  # Windows/py3.14 needs an explicit CA bundle
            appName="trippet-cards",
        )
        # Atlas M0 intermittently throws TLS alerts on one shard host; a second
        # ping usually lands on a healthy one.
        try:
            client.admin.command("ping")
        except Exception:
            client.admin.command("ping")
    except Exception as e:
        log.warning("Mongo unavailable (%s: %s) — retrying in %.0fs, memory-only until then",
                    type(e).__name__, e, _RETRY_COOLDOWN_S)
        return None
    _client = client
    log.info("Mongo connected (db=%s)", os.environ.get("MONGODB_DB", "trippet"))
    return _client[os.environ.get("MONGODB_DB", "trippet")]


def available() -> bool:
    return _db() is not None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Card sessions ───────────────────────────────────────────────────────────
def save_session(doc: dict) -> None:
    """Upsert the full session doc keyed by chat_id. Small docs (≤5 hotels,
    a few hundred swipes max) — full replace is simplest and race-safe enough."""
    d = _db()
    if d is None:
        return
    try:
        body = {k: v for k, v in doc.items() if k != "_id"}
        body["updated_at"] = _utcnow()
        d.card_sessions.replace_one({"chat_id": doc["chat_id"]}, body, upsert=True)
    except Exception as e:
        log.warning("save_session failed: %s", e)


def load_session(chat_id: int) -> Optional[dict]:
    """Fetch a persisted session (used to survive process restarts)."""
    d = _db()
    if d is None:
        return None
    try:
        doc = d.card_sessions.find_one({"chat_id": chat_id})
        if doc:
            doc.pop("_id", None)
        return doc
    except Exception as e:
        log.warning("load_session failed: %s", e)
        return None


# ─── Analytics (append-only) ─────────────────────────────────────────────────
_pending_events: list[dict] = []   # buffered while Mongo is down; flushed on recovery
_PENDING_MAX = 500


def log_event(chat_id: int, user_id: str, event_type: str,
              hotel_id: Optional[str] = None, meta: Optional[dict[str, Any]] = None) -> None:
    """One interaction event from the card UI. `meta` carries the interesting
    bits: dwell_ms, drag stats, direction, viewport, round, etc.
    Events during a Mongo outage are buffered and flushed on recovery."""
    doc = {
        "chat_id": chat_id,
        "user_id": str(user_id),
        "type": event_type,          # deck_open | card_view | swipe | detail_open | link_out | decided
        "hotel_id": hotel_id,
        "meta": meta or {},
        "ts": _utcnow(),
    }
    d = _db()
    if d is None:
        _buffer(doc)
        return
    try:
        if _pending_events:
            backlog, _pending_events[:] = _pending_events[:], []
            d.analytics.insert_many(backlog, ordered=False)
            log.info("flushed %d buffered analytics events", len(backlog))
        d.analytics.insert_one(doc)
    except Exception as e:
        log.warning("log_event failed (%s) — buffering", e)
        _buffer(doc)


def _buffer(doc: dict) -> None:
    if len(_pending_events) < _PENDING_MAX:
        _pending_events.append(doc)


def analytics_summary(chat_id: int) -> dict:
    """Cheap rollup for the results endpoint / judges demo."""
    d = _db()
    if d is None:
        return {"available": False}
    try:
        pipeline = [
            {"$match": {"chat_id": chat_id}},
            {"$group": {"_id": "$type", "n": {"$sum": 1}}},
        ]
        counts = {row["_id"]: row["n"] for row in d.analytics.aggregate(pipeline)}
        dwell = list(d.analytics.aggregate([
            {"$match": {"chat_id": chat_id, "type": "swipe", "meta.dwell_ms": {"$gt": 0}}},
            {"$group": {"_id": "$hotel_id",
                        "avg_dwell_ms": {"$avg": "$meta.dwell_ms"},
                        "swipes": {"$sum": 1}}},
        ]))
        return {"available": True, "event_counts": counts,
                "per_hotel_dwell": {row["_id"]: {"avg_dwell_ms": round(row["avg_dwell_ms"]),
                                                 "swipes": row["swipes"]} for row in dwell}}
    except Exception as e:
        log.warning("analytics_summary failed: %s", e)
        return {"available": False}
