"""FastAPI face-layer API.

Reads the same in-memory `state` module the bot writes to (shared asyncio loop
via `run.py`). Serves the Mini App and a single JSON state endpoint.

TODO seams:
  - Swap the in-memory `state._GROUPS` lookup for MongoDB Atlas when persistence
    lands (PROJECT.md §3 — state store).
  - Add auth via Telegram Mini App initData HMAC when we care about writes.
    Currently read-only, so unauth'd polling is fine.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core import state
from app.core import health
from app.bot import cards
from app.integrations import db
from app.integrations import elevenlabs


ROOT = Path(__file__).resolve().parents[2]   # app/api/api.py -> repo root
WEBAPP_DIR = ROOT / "webapp"


app = FastAPI(title="trippet-face", docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Telegram webview loads over any origin
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _no_cache(request, call_next):
    """Telegram's in-app WebView caches the Mini App aggressively across
    launches from the same URL — without this, UI edits silently keep
    showing the old version until the client's cache happens to expire."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response

# Static asset routes: /webapp/animations/{mood}.json, /webapp/app.js, etc.
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")


def _iso_or_none(d) -> Optional[str]:
    return d.isoformat() if d else None


@app.get("/")
async def root() -> FileResponse:
    index = WEBAPP_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="webapp/index.html not built yet")
    return FileResponse(str(index))


@app.get("/api/health")
async def api_ping() -> dict:
    return {"ok": True, "service": "trippet-face"}


# ─── Hotel cards (Tinder-style basecamp decision) ────────────────────────────
# NOTE: card endpoints are sync `def` on purpose — FastAPI runs them in a
# threadpool, so blocking Stay22/Mongo calls never stall the shared event loop
# that also drives the Telegram bot.

def _chat_id(group_id: str) -> int:
    try:
        return int(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="group_id must be an int chat id")


class SwipeBody(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    name: str = Field(default="guest", max_length=64)
    hotel_id: str = Field(min_length=1, max_length=80)
    direction: str = Field(pattern="^(left|right)$")
    analytics: dict = Field(default_factory=dict)


class EventBody(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=40)
    hotel_id: str | None = Field(default=None, max_length=80)
    meta: dict = Field(default_factory=dict)


@app.get("/cards")
def cards_page() -> FileResponse:
    page = WEBAPP_DIR / "cards.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="webapp/cards.html missing")
    return FileResponse(str(page))


@app.get("/api/cards/{group_id}")
def api_cards_view(group_id: str, user_id: str, name: str = "guest") -> JSONResponse:
    """Deck for one user. Creates the session on first call (so the page works
    in a plain browser for testing), registers the caller as a participant."""
    return JSONResponse(cards.view_for(_chat_id(group_id), user_id, name))


@app.post("/api/cards/{group_id}/swipe")
def api_cards_swipe(group_id: str, body: SwipeBody) -> JSONResponse:
    """One swipe + its interaction analytics. Returns the fresh view (round
    may have resolved — the UI re-renders straight from this response)."""
    view = cards.record_swipe(_chat_id(group_id), body.user_id, body.name,
                              body.hotel_id, body.direction, body.analytics)
    return JSONResponse(view)


@app.post("/api/cards/{group_id}/event")
def api_cards_event(group_id: str, body: EventBody) -> JSONResponse:
    """Fire-and-forget UI analytics: deck_open, card_view, detail_open, link_out."""
    db.log_event(_chat_id(group_id), body.user_id, body.type, body.hotel_id, body.meta)
    return JSONResponse({"ok": True})


@app.get("/api/cards/{group_id}/results")
def api_cards_results(group_id: str) -> JSONResponse:
    """Tally, winner, per-round history + Mongo analytics rollup."""
    return JSONResponse(cards.results(_chat_id(group_id)))


# NOTE: sync `def` on purpose — see cards endpoints above, same reasoning
# (blocking ElevenLabs call runs in FastAPI's threadpool, not the event loop).
@app.get("/api/speak")
def api_speak(text: str, mood: str = "", physical: Optional[int] = None) -> Response:
    """One-shot TTS for the pet's mood caption. `mood`/`physical` pick the
    voice (dying vs alive) so tap-to-speak carries the right inflection."""
    text = text.strip()[:200]
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    audio = elevenlabs.text_to_speech(text, mood=mood or None, physical=physical)
    if audio is None:
        raise HTTPException(status_code=502, detail="tts failed")
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/api/state/{group_id}")
async def api_state(group_id: str) -> JSONResponse:
    """Live pet state for the given Telegram group.

    Auto-creates the group on first read so the Mini App can be opened before
    /start is sent — the pet renders at 100/100 happy until the bot writes."""
    try:
        chat_id = int(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="group_id must be an int chat id")

    g = state.get_or_create(chat_id)
    g.pet.refresh_mood()

    dates = g.trip.dates
    trip_dates = {
        "start": _iso_or_none(dates.start if dates else None),
        "end":   _iso_or_none(dates.end if dates else None),
    }

    return JSONResponse({
        "group_id": str(chat_id),
        "pet": {
            "physical": g.pet.physical,
            "mental":   g.pet.mental,
            "mood":     g.pet.mood,
        },
        "trip": {
            "city":              g.trip.city,
            "dates":             trip_dates,
            "budget_per_person": g.trip.budget_per_person,
            "group_size":        g.trip.group_size,
            "vibe":              g.trip.vibe,
        },
        "sim_week":     g.sim_week,
        "max_sim_week": health.MAX_WEEK,
    })
