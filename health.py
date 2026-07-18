"""Two-bar health engine — PROJECT.md §5.

Both bars are delta-based. Compare each poll to the last snapshot and apply
damage/heal from the change. Pure functions; no I/O. Weights + DAMAGE_CAP
sit at the top so the feel is tunable live.

TODO seams:
  - `market_at_week()` fakes a 6-week series so /scrub can be demoed today.
    Replace with a real Stay22 poll (`stay22.market_snapshot(...)`) — the
    return shape (`MarketSnapshot`) does not change.
  - `mental_at_week()` decays linearly on silence for the demo. Replace with
    an engagement counter fed by `bot.py`'s message handler.
"""
from __future__ import annotations
from dataclasses import replace

from state import GroupState, MarketSnapshot


# ─── Tune the feel here ──────────────────────────────────────────────────────
WEIGHT_AVAILABILITY = 200.0   # 5% drop (Δ=-0.05) → ~10 damage
WEIGHT_PRICE_USD = 0.7        # $15 jump         → ~10 damage
DAMAGE_CAP = 25               # max damage from any single poll
MENTAL_DECAY_PER_WEEK = 12    # points lost to silence per simulated week
MENTAL_ACTIVITY_HEAL = 8      # points regained per "group did a thing" tick


# ─── Delta-based physical formula (PROJECT.md §5 verbatim) ───────────────────
def apply_market_delta(physical: int, prev: MarketSnapshot, curr: MarketSnapshot) -> int:
    d_avail = (curr.rooms_available - prev.rooms_available) / max(1.0, prev.rooms_available)
    d_price = curr.avg_price_usd - prev.avg_price_usd

    damage = WEIGHT_AVAILABILITY * max(0.0, -d_avail) + WEIGHT_PRICE_USD * max(0.0, d_price)
    heal   = WEIGHT_AVAILABILITY * max(0.0,  d_avail) + WEIGHT_PRICE_USD * max(0.0, -d_price)

    new = physical - min(damage, DAMAGE_CAP) + heal
    return max(0, min(100, int(round(new))))


def apply_mental_delta(mental: int, engagement_delta: float) -> int:
    """Positive `engagement_delta` = decisions/activity; negative = silence.
    Same shape as physical: capped damage on the bad side, uncapped heal on the good."""
    if engagement_delta >= 0:
        new = mental + engagement_delta * MENTAL_ACTIVITY_HEAL
    else:
        new = mental + max(-DAMAGE_CAP, engagement_delta * MENTAL_DECAY_PER_WEEK)
    return max(0, min(100, int(round(new))))


# ─── Faked 6-week market series (drives /scrub demo) ─────────────────────────
# Prices trending up, availability trending down, with dips at week 2 & 4 so the
# pet visibly recovers on the "good weeks" and slides again after.
_MARKET_SERIES: list[MarketSnapshot] = [
    MarketSnapshot(avg_price_usd=200, rooms_available=100),  # week 0 baseline
    MarketSnapshot(avg_price_usd=214, rooms_available=88),   # week 1 rising, filling
    MarketSnapshot(avg_price_usd=206, rooms_available=92),   # week 2 GOOD WEEK
    MarketSnapshot(avg_price_usd=232, rooms_available=80),   # week 3 bad
    MarketSnapshot(avg_price_usd=227, rooms_available=84),   # week 4 small good week
    MarketSnapshot(avg_price_usd=248, rooms_available=72),   # week 5 rough
    MarketSnapshot(avg_price_usd=263, rooms_available=65),   # week 6 final squeeze
]
MAX_WEEK = len(_MARKET_SERIES) - 1


def market_at_week(week: int) -> MarketSnapshot:
    week = max(0, min(MAX_WEEK, week))
    return _MARKET_SERIES[week]


# ─── /scrub — jump the pet to a specific simulated week ──────────────────────
def scrub_to_week(g: GroupState, target_week: int) -> None:
    """Idempotent recompute: physical replays the market series from 0 → target,
    mental decays linearly with silence. `g` is mutated in place."""
    target_week = max(0, min(MAX_WEEK, target_week))

    physical = 100
    prev = _MARKET_SERIES[0]
    for w in range(1, target_week + 1):
        curr = _MARKET_SERIES[w]
        physical = apply_market_delta(physical, prev, curr)
        prev = curr

    mental = max(0, 100 - target_week * MENTAL_DECAY_PER_WEEK)

    g.sim_week = target_week
    g.last_market = _MARKET_SERIES[target_week]
    g.pet.physical = physical
    g.pet.mental = mental
    g.pet.refresh_mood()


def commit_trip(g: GroupState) -> None:
    """Both bars back to full — the graduated-pet celebration path."""
    g.pet.physical = 100
    g.pet.mental = 100
    g.pet.mood = "graduated"
