"""Deck sourcing + unanimous-match detection. Sits on top of Stay22 client."""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from ..models.schemas import TripState, DeckDoc, DeckHotel, SwipeRecord
from ..storage.repo import Repo
from .stay22 import stay22


def _iso_date(dt: Optional[datetime]) -> Optional[str]:
    return dt.date().isoformat() if dt else None


async def ensure_deck(repo: Repo, trip: TripState, city_idx: int) -> Optional[DeckDoc]:
    """Idempotently source a deck for the given itinerary leg."""
    if city_idx >= len(trip.itinerary):
        return None
    leg = trip.itinerary[city_idx]
    existing = await repo.get_deck(trip.chat_id, leg.city)
    if existing and existing.hotels:
        return existing

    hotels = await stay22.search(
        address=f"{leg.city}, Japan",
        checkin=_iso_date(leg.arrival_date),
        checkout=_iso_date(leg.departure_date),
        adults=max(1, (trip.group_size or 2)),
        rooms=max(1, (trip.group_size or 2) // 2),
        max_price=trip.max_budget,
        page_size=30,
        campaign=f"kamagachi_{trip.chat_id}_{leg.city.lower()}",
    )
    deck = DeckDoc(chat_id=trip.chat_id, city=leg.city, hotels=hotels)
    await repo.upsert_deck(deck)
    return deck


async def unanimous_match(
    repo: Repo, trip: TripState, city: str, hotel_id: str,
) -> Optional[DeckHotel]:
    """Return the matched hotel if 100% of active members swiped RIGHT on it."""
    active = set(trip.active_user_ids)
    if not active:
        return None
    swipes = await repo.list_swipes(trip.chat_id, city=city)
    right_users = {s.user_id for s in swipes if s.hotel_id == hotel_id and s.vote == "RIGHT"}
    if not active.issubset(right_users):
        return None
    deck = await repo.get_deck(trip.chat_id, city)
    if not deck:
        return None
    return next((h for h in deck.hotels if h.hotel_id == hotel_id), None)


async def next_unlocked_city(repo: Repo, trip: TripState) -> Optional[str]:
    """Return the next city in the itinerary that hasn't reached a unanimous match."""
    for i, leg in enumerate(trip.itinerary):
        swipes = await repo.list_swipes(trip.chat_id, city=leg.city)
        hotel_ids_seen = {s.hotel_id for s in swipes if s.vote == "RIGHT"}
        matched = False
        for hid in hotel_ids_seen:
            if await unanimous_match(repo, trip, leg.city, hid):
                matched = True; break
        if not matched:
            return leg.city
    return None
