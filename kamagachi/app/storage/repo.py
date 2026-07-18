"""Storage layer. Motor-backed when MONGODB_URI is set, otherwise in-memory.

The in-memory fallback lets the app boot on a laptop with zero infra so we can
demo the loop even before Atlas is provisioned. Same async interface either way.
"""
from __future__ import annotations
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from ..config import MONGODB_URI, MONGODB_DB
from ..models.schemas import (
    TripState,
    DeckDoc,
    DeckHotel,
    SwipeRecord,
    EventRecord,
    HealthTick,
    PriceTick,
)


class Repo:
    """Async repository interface. Both Mongo and in-memory implementations follow this."""

    # trips
    async def get_trip(self, chat_id: str) -> Optional[TripState]: ...
    async def upsert_trip(self, trip: TripState) -> None: ...

    # decks
    async def get_deck(self, chat_id: str, city: str) -> Optional[DeckDoc]: ...
    async def upsert_deck(self, deck: DeckDoc) -> None: ...

    # swipes
    async def record_swipe(self, swipe: SwipeRecord) -> None: ...
    async def list_swipes(self, chat_id: str, city: Optional[str] = None) -> list[SwipeRecord]: ...
    async def user_swiped_ids(self, chat_id: str, user_id: str, city: str) -> set[str]: ...

    # events
    async def add_event(self, event: EventRecord) -> None: ...
    async def list_events(self, chat_id: str) -> list[EventRecord]: ...

    # time series
    async def append_health_tick(self, tick: HealthTick) -> None: ...
    async def list_health_ticks(self, chat_id: str, limit: int = 500) -> list[HealthTick]: ...
    async def append_price_tick(self, tick: PriceTick) -> None: ...
    async def latest_price_tick(self, chat_id: str, city: str) -> Optional[PriceTick]: ...
    async def list_price_ticks(self, chat_id: str, city: str, limit: int = 500) -> list[PriceTick]: ...


# ─── In-memory implementation ────────────────────────────────────────────────
class MemoryRepo(Repo):
    def __init__(self) -> None:
        self._trips: dict[str, TripState] = {}
        self._decks: dict[tuple[str, str], DeckDoc] = {}
        self._swipes: list[SwipeRecord] = []
        self._events: list[EventRecord] = []
        self._health: list[HealthTick] = []
        self._prices: list[PriceTick] = []
        self._lock = asyncio.Lock()

    async def get_trip(self, chat_id):
        return self._trips.get(chat_id)

    async def upsert_trip(self, trip):
        async with self._lock:
            self._trips[trip.chat_id] = trip

    async def get_deck(self, chat_id, city):
        return self._decks.get((chat_id, city))

    async def upsert_deck(self, deck):
        async with self._lock:
            self._decks[(deck.chat_id, deck.city)] = deck

    async def record_swipe(self, swipe):
        async with self._lock:
            self._swipes.append(swipe)

    async def list_swipes(self, chat_id, city=None):
        return [s for s in self._swipes if s.chat_id == chat_id and (city is None or s.city == city)]

    async def user_swiped_ids(self, chat_id, user_id, city):
        return {s.hotel_id for s in self._swipes if s.chat_id == chat_id and s.user_id == user_id and s.city == city}

    async def add_event(self, event):
        async with self._lock:
            self._events.append(event)

    async def list_events(self, chat_id):
        return [e for e in self._events if e.chat_id == chat_id]

    async def append_health_tick(self, tick):
        async with self._lock:
            self._health.append(tick)

    async def list_health_ticks(self, chat_id, limit=500):
        return [t for t in self._health if t.chat_id == chat_id][-limit:]

    async def append_price_tick(self, tick):
        async with self._lock:
            self._prices.append(tick)

    async def latest_price_tick(self, chat_id, city):
        rel = [t for t in self._prices if t.chat_id == chat_id and t.city == city]
        return rel[-1] if rel else None

    async def list_price_ticks(self, chat_id, city, limit=500):
        return [t for t in self._prices if t.chat_id == chat_id and t.city == city][-limit:]


# ─── Mongo implementation ────────────────────────────────────────────────────
class MongoRepo(Repo):
    def __init__(self, uri: str, db_name: str) -> None:
        from motor.motor_asyncio import AsyncIOMotorClient
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]

    async def ensure_indexes(self) -> None:
        await self.db.trips.create_index("chat_id", unique=True)
        await self.db.decks.create_index([("chat_id", 1), ("city", 1)], unique=True)
        await self.db.swipes.create_index([("chat_id", 1), ("city", 1), ("user_id", 1)])
        await self.db.swipes.create_index([("chat_id", 1), ("hotel_id", 1)])
        await self.db.events.create_index("chat_id")
        # Health + Price are time-series (best-effort create; ignore if exists)
        for name, meta_field in (("health_ts", "chat_id"), ("price_ts", "chat_id")):
            try:
                await self.db.create_collection(
                    name,
                    timeseries={"timeField": "timestamp", "metaField": meta_field, "granularity": "seconds"},
                )
            except Exception:
                pass

    async def get_trip(self, chat_id):
        doc = await self.db.trips.find_one({"chat_id": chat_id})
        return TripState(**doc) if doc else None

    async def upsert_trip(self, trip):
        data = trip.model_dump(mode="json")
        await self.db.trips.update_one({"chat_id": trip.chat_id}, {"$set": data}, upsert=True)

    async def get_deck(self, chat_id, city):
        doc = await self.db.decks.find_one({"chat_id": chat_id, "city": city})
        return DeckDoc(**doc) if doc else None

    async def upsert_deck(self, deck):
        data = deck.model_dump(mode="json")
        await self.db.decks.update_one(
            {"chat_id": deck.chat_id, "city": deck.city}, {"$set": data}, upsert=True
        )

    async def record_swipe(self, swipe):
        await self.db.swipes.insert_one(swipe.model_dump(mode="json"))

    async def list_swipes(self, chat_id, city=None):
        q: dict[str, Any] = {"chat_id": chat_id}
        if city:
            q["city"] = city
        docs = await self.db.swipes.find(q).to_list(length=10000)
        return [SwipeRecord(**d) for d in docs]

    async def user_swiped_ids(self, chat_id, user_id, city):
        cur = self.db.swipes.find(
            {"chat_id": chat_id, "user_id": user_id, "city": city}, {"hotel_id": 1}
        )
        return {d["hotel_id"] async for d in cur}

    async def add_event(self, event):
        await self.db.events.insert_one(event.model_dump(mode="json"))

    async def list_events(self, chat_id):
        docs = await self.db.events.find({"chat_id": chat_id}).to_list(length=1000)
        return [EventRecord(**d) for d in docs]

    async def append_health_tick(self, tick):
        await self.db.health_ts.insert_one(tick.model_dump(mode="json"))

    async def list_health_ticks(self, chat_id, limit=500):
        docs = await self.db.health_ts.find({"chat_id": chat_id}).sort("timestamp", 1).to_list(length=limit)
        return [HealthTick(**d) for d in docs]

    async def append_price_tick(self, tick):
        await self.db.price_ts.insert_one(tick.model_dump(mode="json"))

    async def latest_price_tick(self, chat_id, city):
        doc = await self.db.price_ts.find({"chat_id": chat_id, "city": city}).sort("timestamp", -1).limit(1).to_list(1)
        return PriceTick(**doc[0]) if doc else None

    async def list_price_ticks(self, chat_id, city, limit=500):
        docs = await self.db.price_ts.find({"chat_id": chat_id, "city": city}).sort("timestamp", 1).to_list(limit)
        return [PriceTick(**d) for d in docs]


# ─── Factory ─────────────────────────────────────────────────────────────────
_repo_singleton: Optional[Repo] = None


async def get_repo() -> Repo:
    global _repo_singleton
    if _repo_singleton is not None:
        return _repo_singleton
    if MONGODB_URI:
        try:
            repo = MongoRepo(MONGODB_URI, MONGODB_DB)
            await repo.ensure_indexes()
            _repo_singleton = repo
            print(f"[repo] using MongoDB at {MONGODB_DB}")
            return repo
        except Exception as e:
            print(f"[repo] mongo unavailable ({e}); falling back to memory")
    _repo_singleton = MemoryRepo()
    print("[repo] using in-memory store (no MONGODB_URI set)")
    return _repo_singleton
