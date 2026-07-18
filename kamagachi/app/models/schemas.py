"""Pydantic v2 models for the Kamagachi state matrix.

Every top-level entity carries `custom_metadata: dict` — plugin vectors (flight
tracking, split-billing, event sources) attach here without touching the primary
schema. This is the extensibility contract the whole system rides on.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


def _now() -> datetime:
    return datetime.now(timezone.utc)


Vote = Literal["LEFT", "RIGHT"]
Phase = Literal["planning", "swiping", "matched", "booked"]
BookingStatus = Literal["found", "held", "booked"]


# ─── Itinerary components ────────────────────────────────────────────────────
class ItineraryLeg(BaseModel):
    model_config = ConfigDict(extra="allow")
    city: str
    arrival_date: Optional[datetime] = None
    departure_date: Optional[datetime] = None
    custom_metadata: dict = Field(default_factory=dict)


# ─── Trip state (root of the state matrix) ───────────────────────────────────
class TripState(BaseModel):
    model_config = ConfigDict(extra="allow")
    chat_id: str
    max_budget: Optional[int] = None
    group_size: Optional[int] = None
    active_user_ids: list[str] = Field(default_factory=list)
    itinerary: list[ItineraryLeg] = Field(default_factory=list)

    current_health: int = 0
    current_phase: Phase = "planning"
    current_city_index: int = 0  # which itinerary leg the swipe deck is on

    last_activity_at: datetime = Field(default_factory=_now)
    last_voice_call_at: Optional[datetime] = None
    stay22_conversion_count: int = 0

    custom_metadata: dict = Field(default_factory=dict)


# ─── Deck / hotel ────────────────────────────────────────────────────────────
class DeckHotel(BaseModel):
    model_config = ConfigDict(extra="allow")
    hotel_id: str
    city: str
    name: str
    image_url: str = ""
    base_url: str = ""              # raw booking.com/expedia URL, wrapped by Allez at click time
    price_per_night: float = 0.0
    rating: float = 0.0
    tags: list[str] = Field(default_factory=list)
    preference_embedding: Optional[list[float]] = None
    custom_metadata: dict = Field(default_factory=dict)


class DeckDoc(BaseModel):
    model_config = ConfigDict(extra="allow")
    chat_id: str
    city: str
    hotels: list[DeckHotel] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    custom_metadata: dict = Field(default_factory=dict)


# ─── Swipe log ───────────────────────────────────────────────────────────────
class SwipeRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    chat_id: str
    user_id: str
    hotel_id: str
    city: str
    vote: Vote
    timestamp: datetime = Field(default_factory=_now)
    custom_metadata: dict = Field(default_factory=dict)


# ─── Phoebe events ───────────────────────────────────────────────────────────
class EventRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    chat_id: str
    city: str
    event_name: str
    category: str  # "food" | "activity" | "ticket"
    booking_status: BookingStatus = "found"
    external_url: str = ""
    custom_metadata: dict = Field(default_factory=dict)


# ─── Time-series ─────────────────────────────────────────────────────────────
class HealthTick(BaseModel):
    model_config = ConfigDict(extra="allow")
    chat_id: str
    timestamp: datetime = Field(default_factory=_now)
    health: int
    trigger: str  # "heal_constraints", "decay_price_spike", etc.
    custom_metadata: dict = Field(default_factory=dict)


class PriceTick(BaseModel):
    model_config = ConfigDict(extra="allow")
    chat_id: str
    city: str
    timestamp: datetime = Field(default_factory=_now)
    avg_nightly_price: float
    availability_pct: float
    custom_metadata: dict = Field(default_factory=dict)


# ─── Telegram Mini App initData (auth payload) ───────────────────────────────
class TelegramWebAppUser(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    language_code: str = ""
    is_premium: Optional[bool] = None


class MiniAppInitData(BaseModel):
    """Parsed shape of Telegram.WebApp.initData after HMAC-SHA-256 verification."""
    model_config = ConfigDict(extra="allow")
    query_id: Optional[str] = None
    user: Optional[TelegramWebAppUser] = None
    auth_date: int
    hash: str
    raw: str = ""            # original querystring, for re-verification if needed
    chat_instance: Optional[str] = None
    chat_type: Optional[str] = None
    start_param: Optional[str] = None


# ─── API request/response models ─────────────────────────────────────────────
class SwipeRequest(BaseModel):
    chat_id: str
    hotel_id: str
    vote: Vote


class SwipeResponse(BaseModel):
    ok: bool = True
    health: int
    health_delta: int
    unanimous_match: Optional[dict] = None  # {"hotel_id":..., "name":..., "allez_url":...}
    next_city: Optional[str] = None


class DeckResponse(BaseModel):
    city: str
    deck: list[DeckHotel]
    user_progress: dict
    group_progress: dict
