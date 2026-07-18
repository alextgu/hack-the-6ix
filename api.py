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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import state
import health


ROOT = Path(__file__).parent
WEBAPP_DIR = ROOT / "webapp"


app = FastAPI(title="trippet-face", docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Telegram webview loads over any origin
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

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
