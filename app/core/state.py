"""Shared state seam.

One in-memory object per Telegram group chat. Matches the shape in PROJECT.md
so future lanes (Stay22 → physical, engagement → mental, LLM → trip) plug in
without reshaping the store.

TODO seams:
  - Swap `_GROUPS` for a MongoDB-Atlas-backed store (PROJECT.md §3, §4).
  - Wire the LLM/Freesolo Read layer into `TripState.confidence` and populate
    trip fields incrementally as messages come in.
  - Attach per-user `PerPerson` records as onboarding lands (PROJECT.md §2).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ─── Trip state (PROJECT.md §1, §3 — the constraints extracted from chat) ───
@dataclass
class DateWindow:
    start: date
    end: date


@dataclass
class PerPerson:
    """Per-user onboarding output (PROJECT.md §2). Populated later."""
    user_id: int
    display_name: str
    budget_per_person: Optional[int] = None
    date_window: Optional[DateWindow] = None
    vibe_tags: list[str] = field(default_factory=list)
    swiped_spots: list[str] = field(default_factory=list)


@dataclass
class TripState:
    city: Optional[str] = None
    dates: Optional[DateWindow] = None
    budget_per_person: Optional[int] = None
    group_size: Optional[int] = None
    vibe: Optional[str] = None
    per_person: dict[int, PerPerson] = field(default_factory=dict)
    confidence: float = 0.0  # how sure we are of the reconciled plan (0..1)


# ─── Pet state (PROJECT.md §1, §5 — two health bars) ─────────────────────────
Mood = str  # "happy" | "worried" | "sick" | "dying" | "graduated"


@dataclass
class PetState:
    physical: int = 100
    mental: int = 100
    mood: Mood = "happy"

    def refresh_mood(self) -> None:
        self.mood = derive_mood(self.physical, self.mental)


def derive_mood(physical: int, mental: int) -> Mood:
    avg = (physical + mental) / 2
    if avg > 70: return "happy"
    if avg > 45: return "worried"
    if avg > 20: return "sick"
    return "dying"


# ─── Per-group container ─────────────────────────────────────────────────────
@dataclass
class GroupState:
    chat_id: int
    trip: TripState = field(default_factory=TripState)
    pet: PetState = field(default_factory=PetState)

    # Demo scrubber cursor (0..6). Real deploys drive deltas off live snapshots.
    sim_week: int = 0

    # Last snapshots used to compute market/engagement deltas.
    # In prod these come from Stay22 + Telegram engagement counters.
    last_market: Optional["MarketSnapshot"] = None
    last_engagement_hint: Optional[float] = None


@dataclass
class MarketSnapshot:
    """Latest Stay22-style tick — feeds the physical bar's delta formula."""
    avg_price_usd: float
    rooms_available: float  # arbitrary units; only ratios matter


# ─── Registry (in-memory; MongoDB later) ─────────────────────────────────────
_GROUPS: dict[int, GroupState] = {}


def get_or_create(chat_id: int) -> GroupState:
    if chat_id not in _GROUPS:
        _GROUPS[chat_id] = GroupState(chat_id=chat_id)
    return _GROUPS[chat_id]


def reset(chat_id: int) -> GroupState:
    _GROUPS[chat_id] = GroupState(chat_id=chat_id)
    return _GROUPS[chat_id]
