"""Gamification engine: applies heals + decay to TripState, logs to time-series,
and emits events for the pet visual, voice service, and bot broadcaster."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from ..config import GAMIFY, pet_state
from ..models.schemas import TripState, HealthTick, PriceTick
from ..storage.repo import Repo
from .events import bus, T_HEALTH_CHANGED, T_PHASE_CHANGED, T_VOICE_ESCALATE, T_MARKET_PRESSURE


def _clamp(v: int) -> int:
    return max(0, min(GAMIFY.MAX_HEALTH, v))


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def apply_delta(repo: Repo, trip: TripState, delta: int, trigger: str) -> TripState:
    """Apply a health delta to a trip; persist, log to time-series, emit events."""
    prev = trip.current_health
    prev_state = pet_state(prev)
    prev_phase = trip.current_phase
    trip.current_health = _clamp(prev + delta)
    trip.last_activity_at = _now()

    # Phase progression
    if trip.current_phase == "planning" and trip.current_health >= GAMIFY.PHASE_STABLE_HEALTH:
        trip.current_phase = "swiping"
    if trip.current_phase == "swiping" and trigger == "unanimous_match":
        trip.current_phase = "matched"
    if trigger == "verified_booking":
        trip.current_phase = "booked"
        trip.current_health = GAMIFY.MAX_HEALTH

    await repo.upsert_trip(trip)
    await repo.append_health_tick(HealthTick(
        chat_id=trip.chat_id, health=trip.current_health, trigger=trigger
    ))

    new_state = pet_state(trip.current_health)
    await bus.emit(T_HEALTH_CHANGED, {
        "chat_id": trip.chat_id,
        "prev_health": prev,
        "health": trip.current_health,
        "delta": trip.current_health - prev,
        "prev_state": prev_state,
        "state": new_state,
        "trigger": trigger,
    })
    if trip.current_phase != prev_phase:
        await bus.emit(T_PHASE_CHANGED, {
            "chat_id": trip.chat_id,
            "phase": trip.current_phase,
            "health": trip.current_health,
        })
    if trip.current_health <= GAMIFY.VOICE_THRESHOLD_HEALTH and delta < 0:
        await bus.emit(T_VOICE_ESCALATE, {
            "chat_id": trip.chat_id,
            "health": trip.current_health,
            "reason": trigger,
        })
    return trip


# ─── Heal helpers (called by the consensus engine when it locks a constraint) ─
async def heal_constraints_locked(repo: Repo, trip: TripState) -> TripState:
    return await apply_delta(repo, trip, GAMIFY.HEAL_CONSTRAINTS_LOCKED, "heal_constraints_locked")

async def heal_cities_resolved(repo: Repo, trip: TripState) -> TripState:
    return await apply_delta(repo, trip, GAMIFY.HEAL_CITIES_RESOLVED, "heal_cities_resolved")

async def heal_dates_mapped(repo: Repo, trip: TripState) -> TripState:
    return await apply_delta(repo, trip, GAMIFY.HEAL_DATES_MAPPED, "heal_dates_mapped")

async def heal_swipe(repo: Repo, trip: TripState) -> TripState:
    return await apply_delta(repo, trip, GAMIFY.HEAL_PER_SWIPE, "heal_swipe")

async def heal_unanimous_match(repo: Repo, trip: TripState) -> TripState:
    return await apply_delta(repo, trip, GAMIFY.HEAL_UNANIMOUS_MATCH, "unanimous_match")

async def heal_verified_booking(repo: Repo, trip: TripState) -> TripState:
    return await apply_delta(repo, trip, GAMIFY.HEAL_VERIFIED_BOOKING, "verified_booking")


# ─── Market pressure (Stay22 poller feeds this) ──────────────────────────────
async def evaluate_market_delta(
    repo: Repo,
    trip: TripState,
    city: str,
    latest_price: float,
    latest_availability_pct: float,
) -> Optional[int]:
    """Compare latest Stay22 tick to previous; return applied delta or None."""
    tick = PriceTick(
        chat_id=trip.chat_id, city=city,
        avg_nightly_price=latest_price, availability_pct=latest_availability_pct,
    )
    prev = await repo.latest_price_tick(trip.chat_id, city)
    await repo.append_price_tick(tick)
    if not prev:
        return None

    price_delta = latest_price - prev.avg_nightly_price
    avail_delta = prev.availability_pct - latest_availability_pct  # positive = getting worse

    total = 0
    triggers: list[str] = []
    if price_delta >= GAMIFY.MARKET_PRICE_THRESHOLD_USD:
        total += GAMIFY.DECAY_PRICE_SPIKE
        triggers.append(f"price+${price_delta:.0f}")
    if avail_delta >= GAMIFY.MARKET_AVAILABILITY_THRESHOLD_PCT:
        total += GAMIFY.DECAY_AVAILABILITY_DROP
        triggers.append(f"avail-{avail_delta:.1f}%")

    if total == 0:
        return None

    total = max(total, GAMIFY.DECAY_MAX_PER_CYCLE)  # cap the damage
    trigger = f"market:{city}:" + ",".join(triggers)
    await bus.emit(T_MARKET_PRESSURE, {
        "chat_id": trip.chat_id, "city": city,
        "price_delta": price_delta, "avail_delta": avail_delta,
        "damage": total,
    })
    await apply_delta(repo, trip, total, trigger)
    return total


# ─── Inactivity decay (background job) ───────────────────────────────────────
async def evaluate_inactivity(repo: Repo, trip: TripState) -> Optional[int]:
    hours = (_now() - trip.last_activity_at).total_seconds() / 3600.0
    if hours < 24:
        return None
    await apply_delta(repo, trip, GAMIFY.DECAY_INACTIVITY_24H, "inactivity_24h")
    return GAMIFY.DECAY_INACTIVITY_24H


# ─── Consensus reconciliation → auto-heal ────────────────────────────────────
async def reconcile_and_heal(repo: Repo, trip: TripState, prev: TripState) -> TripState:
    """Compare prev vs new trip; emit heals for newly-locked constraints."""
    if (trip.max_budget and trip.group_size) and not (prev.max_budget and prev.group_size):
        trip = await heal_constraints_locked(repo, trip)
    if len(trip.itinerary) > 0 and len(prev.itinerary) == 0:
        trip = await heal_cities_resolved(repo, trip)
    prev_dated = sum(1 for l in prev.itinerary if l.arrival_date and l.departure_date)
    new_dated = sum(1 for l in trip.itinerary if l.arrival_date and l.departure_date)
    if new_dated > prev_dated and new_dated == len(trip.itinerary) and trip.itinerary:
        trip = await heal_dates_mapped(repo, trip)
    return trip
