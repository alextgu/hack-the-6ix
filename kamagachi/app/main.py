"""FastAPI entry point. Wires webhook, mini-app APIs, and background pollers."""
from __future__ import annotations
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, PUBLIC_BASE_URL,
    GAMIFY, pet_state,
)
from .models.schemas import (
    TripState, SwipeRequest, SwipeResponse, DeckResponse, SwipeRecord,
)
from .storage.repo import get_repo
from .services import consensus, health, deck as deck_svc, stay22 as stay22_mod
from .services.stay22 import stay22
from .services.telegram_auth import parse_and_verify
from .services.pet_render import render_pet_svg_for_state, status_line
from .services.preferences import rank_deck, preference_vector_from_chat, hotel_embedding
from .services.events import bus, T_UNANIMOUS_MATCH, T_BOOKING_VERIFIED


APP_ROOT = Path(__file__).parent


# ─── Background jobs ─────────────────────────────────────────────────────────
async def market_poller() -> None:
    """Periodically poll Stay22 market for each active trip's cities.
    Health decays if price/availability moves adversely."""
    while True:
        try:
            repo = await get_repo()
            # naive scan: get all trips currently tracked
            trips_iter = (repo._trips.values() if hasattr(repo, "_trips") else None)
            trips: list[TripState] = []
            if trips_iter is not None:
                trips = list(trips_iter)
            else:
                docs = await repo.db.trips.find({}).to_list(length=200)  # type: ignore[attr-defined]
                trips = [TripState(**d) for d in docs]
            for trip in trips:
                if trip.current_phase == "booked":
                    continue
                for leg in trip.itinerary:
                    if not (leg.arrival_date and leg.departure_date):
                        continue
                    ci = leg.arrival_date.date().isoformat()
                    co = leg.departure_date.date().isoformat()
                    price, avail = await stay22.market_snapshot(f"{leg.city}, Japan", ci, co)
                    if price or avail:
                        await health.evaluate_market_delta(repo, trip, leg.city, price, avail)
        except Exception as e:
            print(f"[poller] market cycle failed: {e}")
        await asyncio.sleep(GAMIFY.MARKET_POLL_SECONDS)


async def inactivity_poller() -> None:
    while True:
        try:
            repo = await get_repo()
            trips: list[TripState] = []
            if hasattr(repo, "_trips"):
                trips = list(repo._trips.values())
            else:
                docs = await repo.db.trips.find({}).to_list(length=200)  # type: ignore[attr-defined]
                trips = [TripState(**d) for d in docs]
            for trip in trips:
                if trip.current_phase == "booked":
                    continue
                await health.evaluate_inactivity(repo, trip)
        except Exception as e:
            print(f"[poller] inactivity cycle failed: {e}")
        await asyncio.sleep(GAMIFY.INACTIVITY_CHECK_SECONDS)


async def booking_verify_poller() -> None:
    """Every 5 min: query Stay22 reporting API and mark bookings verified."""
    while True:
        try:
            repo = await get_repo()
            trips: list[TripState] = []
            if hasattr(repo, "_trips"):
                trips = list(repo._trips.values())
            else:
                docs = await repo.db.trips.find({"current_phase": {"$ne": "booked"}}).to_list(length=100)  # type: ignore[attr-defined]
                trips = [TripState(**d) for d in docs]
            end = datetime.now(timezone.utc).date().isoformat()
            start = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
            for trip in trips:
                if trip.current_phase != "matched":
                    continue
                # Stay22 requires `thirdParty`; use affiliate id as best-effort.
                count = await stay22.bookings_count(
                    third_party=stay22.aid,
                    campaign=f"kamagachi_{trip.chat_id}",
                    start_date=start, end_date=end,
                )
                if count > trip.stay22_conversion_count:
                    trip.stay22_conversion_count = count
                    await repo.upsert_trip(trip)
                    await health.heal_verified_booking(repo, trip)
                    await bus.emit(T_BOOKING_VERIFIED, {"chat_id": trip.chat_id, "count": count})
        except Exception as e:
            print(f"[poller] booking verify failed: {e}")
        await asyncio.sleep(300)


# ─── FastAPI lifecycle ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_repo()  # initialise
    # wire event handlers
    if TELEGRAM_BOT_TOKEN:
        from .bot import telegram as tg
        from .services import voice
        tg.subscribe()
        try:
            voice.attach_bot(tg.get_bot())
            voice.attach_repo(await get_repo())
            voice.subscribe()
        except Exception as e:
            print(f"[boot] voice subscribe failed: {e}")
        # register webhook if PUBLIC_BASE_URL looks reachable
        try:
            hook_url = f"{PUBLIC_BASE_URL}/webhook/telegram"
            await tg.get_bot().set_webhook(url=hook_url, secret_token=TELEGRAM_WEBHOOK_SECRET, drop_pending_updates=True)
            print(f"[boot] telegram webhook registered: {hook_url}")
        except Exception as e:
            print(f"[boot] webhook registration failed (dev mode ok): {e}")
    else:
        print("[boot] TELEGRAM_BOT_TOKEN missing — API-only mode")

    tasks = [
        asyncio.create_task(market_poller()),
        asyncio.create_task(inactivity_poller()),
        asyncio.create_task(booking_verify_poller()),
    ]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await stay22.close()


app = FastAPI(title="Kamagachi", lifespan=lifespan)

# Static mounts
app.mount("/miniapp", StaticFiles(directory=str(APP_ROOT / "miniapp"), html=True), name="miniapp")
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")


# ─── Health / root ───────────────────────────────────────────────────────────
@app.get("/", response_class=PlainTextResponse)
async def root() -> str:
    return "kamagachi is alive (barely)"


@app.get("/api/config")
async def api_config() -> dict:
    return {"has_stay22": bool(stay22.api_key), "aid": stay22.aid, "public_base_url": PUBLIC_BASE_URL}


# ─── Telegram webhook ────────────────────────────────────────────────────────
@app.post("/webhook/telegram")
async def telegram_webhook(
    req: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
) -> dict:
    if x_telegram_bot_api_secret_token != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="bad secret")
    from .bot import telegram as tg
    data = await req.json()
    await tg.process_update_dict(data)
    return {"ok": True}


# ─── Mini App auth helper ────────────────────────────────────────────────────
def _require_user(init_data: Optional[str]) -> tuple[str, str]:
    """Verify initData; return (user_id, display_name).
    In DEMO_MODE we accept a missing/invalid initData and synthesise a user."""
    if init_data and TELEGRAM_BOT_TOKEN:
        parsed = parse_and_verify(init_data, TELEGRAM_BOT_TOKEN)
        if parsed and parsed.user:
            display = parsed.user.first_name or parsed.user.username or f"u{parsed.user.id}"
            return str(parsed.user.id), display
    from .config import DEMO_MODE
    if DEMO_MODE:
        return "demo-user", "demo"
    raise HTTPException(status_code=401, detail="invalid initData")


# ─── Deck ────────────────────────────────────────────────────────────────────
@app.get("/api/deck", response_model=DeckResponse)
async def api_deck(
    chat_id: str = Query(...),
    city: Optional[str] = None,
    x_telegram_init_data: Optional[str] = Header(None),
) -> DeckResponse:
    user_id, _ = _require_user(x_telegram_init_data)
    repo = await get_repo()
    trip = await repo.get_trip(chat_id)
    if not trip or not trip.itinerary:
        raise HTTPException(status_code=404, detail="no trip yet")

    # respect sequential-city unlock unless caller specified a city already unlocked
    unlocked = await deck_svc.next_unlocked_city(repo, trip)
    target_city = city or unlocked or trip.itinerary[0].city
    idx = next((i for i, l in enumerate(trip.itinerary) if l.city == target_city), 0)
    deck = await deck_svc.ensure_deck(repo, trip, idx)
    if not deck:
        raise HTTPException(status_code=404, detail="deck missing")

    # semantic ranking to the group's aggregated preference vector
    chat_context = " ".join(
        [f"{trip.max_budget or ''} {trip.group_size or ''} " + " ".join(l.city for l in trip.itinerary)]
    )
    pref = preference_vector_from_chat(chat_context)
    ranked = rank_deck(deck.hotels, pref)

    swiped = await repo.user_swiped_ids(chat_id, user_id, target_city)
    remaining = [h for h in ranked if h.hotel_id not in swiped]

    return DeckResponse(
        city=target_city,
        deck=remaining,
        user_progress={"swiped_hotel_ids": list(swiped)},
        group_progress={
            "total_active_users": len(trip.active_user_ids),
            "unanimous_hotel_id_if_any": None,
        },
    )


# ─── Swipe ───────────────────────────────────────────────────────────────────
@app.post("/api/swipe", response_model=SwipeResponse)
async def api_swipe(
    body: SwipeRequest,
    x_telegram_init_data: Optional[str] = Header(None),
) -> SwipeResponse:
    user_id, _ = _require_user(x_telegram_init_data)
    repo = await get_repo()
    trip = await repo.get_trip(body.chat_id)
    if not trip:
        raise HTTPException(status_code=404, detail="no trip")

    # find city for this hotel
    city: Optional[str] = None
    for leg in trip.itinerary:
        deck = await repo.get_deck(body.chat_id, leg.city)
        if deck and any(h.hotel_id == body.hotel_id for h in deck.hotels):
            city = leg.city; break
    if not city:
        raise HTTPException(status_code=400, detail="hotel not in any deck")

    await repo.record_swipe(SwipeRecord(
        chat_id=body.chat_id, user_id=user_id,
        hotel_id=body.hotel_id, city=city, vote=body.vote,
    ))
    prev_health = trip.current_health
    trip = await health.heal_swipe(repo, trip)
    delta = trip.current_health - prev_health
    match_payload: Optional[dict] = None
    next_city: Optional[str] = None

    if body.vote == "RIGHT":
        matched = await deck_svc.unanimous_match(repo, trip, city, body.hotel_id)
        if matched:
            trip = await health.heal_unanimous_match(repo, trip)
            leg_for_city = next((l for l in trip.itinerary if l.city == city), None)
            allez = stay22.allez_url(
                provider="roam", link=matched.base_url or None,
                address=f"{matched.city}, Japan",
                checkin=(leg_for_city.arrival_date.date().isoformat() if leg_for_city and leg_for_city.arrival_date else None),
                checkout=(leg_for_city.departure_date.date().isoformat() if leg_for_city and leg_for_city.departure_date else None),
                adults=max(1, trip.group_size or 2),
                campaign=f"kamagachi_{trip.chat_id}",
            )
            match_payload = {"hotel_id": matched.hotel_id, "name": matched.name, "allez_url": allez}
            await bus.emit(T_UNANIMOUS_MATCH, {
                "chat_id": trip.chat_id, "city": city,
                "hotel_id": matched.hotel_id, "hotel_name": matched.name,
                "allez_url": allez,
            })
            next_city = await deck_svc.next_unlocked_city(repo, trip)

    return SwipeResponse(
        ok=True, health=trip.current_health, health_delta=delta,
        unanimous_match=match_payload, next_city=next_city,
    )


# ─── Allez URL ───────────────────────────────────────────────────────────────
@app.get("/api/allez")
async def api_allez(
    chat_id: str = Query(...), hotel_id: str = Query(...),
    x_telegram_init_data: Optional[str] = Header(None),
) -> dict:
    _require_user(x_telegram_init_data)
    repo = await get_repo()
    trip = await repo.get_trip(chat_id)
    if not trip:
        raise HTTPException(status_code=404, detail="no trip")
    for leg in trip.itinerary:
        deck = await repo.get_deck(chat_id, leg.city)
        if not deck:
            continue
        h = next((x for x in deck.hotels if x.hotel_id == hotel_id), None)
        if h:
            url = stay22.allez_url(
                provider="roam", link=h.base_url or None,
                address=f"{h.city}, Japan",
                checkin=(leg.arrival_date and leg.arrival_date.date().isoformat()),
                checkout=(leg.departure_date and leg.departure_date.date().isoformat()),
                adults=max(1, trip.group_size or 2),
                campaign=f"kamagachi_{trip.chat_id}",
            )
            return {"url": url}
    raise HTTPException(status_code=404, detail="hotel not found")


# ─── Pet SVG + health scrubber ───────────────────────────────────────────────
@app.get("/api/pet.svg")
async def api_pet_svg(chat_id: str = Query(...)) -> Response:
    repo = await get_repo()
    trip = await repo.get_trip(chat_id)
    health_val = trip.current_health if trip else 0
    svg = render_pet_svg_for_state(pet_state(health_val))
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/health-timeseries")
async def api_health_ts(chat_id: str = Query(...)) -> dict:
    repo = await get_repo()
    ticks = await repo.list_health_ticks(chat_id, limit=500)
    return {"ticks": [t.model_dump(mode="json") for t in ticks]}


@app.get("/api/price-timeseries")
async def api_price_ts(chat_id: str = Query(...), city: str = Query(...)) -> dict:
    repo = await get_repo()
    ticks = await repo.list_price_ticks(chat_id, city, limit=500)
    return {"ticks": [t.model_dump(mode="json") for t in ticks]}


# ─── Seed endpoint (demo) ────────────────────────────────────────────────────
@app.post("/api/seed")
async def api_seed(chat_id: str = Query("demo-chat")) -> dict:
    """Bootstrap a canned trip so the mini app is walkable without a chat."""
    repo = await get_repo()
    from .models.schemas import ItineraryLeg
    trip = TripState(
        chat_id=chat_id, max_budget=1800, group_size=4,
        active_user_ids=["demo-user"],
        itinerary=[
            ItineraryLeg(city="Tokyo",
                         arrival_date=datetime(2026, 5, 10, tzinfo=timezone.utc),
                         departure_date=datetime(2026, 5, 14, tzinfo=timezone.utc)),
            ItineraryLeg(city="Kyoto",
                         arrival_date=datetime(2026, 5, 14, tzinfo=timezone.utc),
                         departure_date=datetime(2026, 5, 18, tzinfo=timezone.utc)),
            ItineraryLeg(city="Osaka",
                         arrival_date=datetime(2026, 5, 18, tzinfo=timezone.utc),
                         departure_date=datetime(2026, 5, 21, tzinfo=timezone.utc)),
        ],
        current_health=55, current_phase="swiping",
    )
    await repo.upsert_trip(trip)
    # pre-source Tokyo deck so the first swipe is instant
    await deck_svc.ensure_deck(repo, trip, 0)
    return {"ok": True, "chat_id": chat_id, "phase": trip.current_phase}
