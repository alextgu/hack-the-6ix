"""Green itinerary sub-agent — plans how the group MOVES, then counts it.

Runs when the plan reaches BOOK (flight locked + hotel decided) or on
/itinerary. Gemini drafts a short day-by-day plan where every leg has a
transport mode; code (not the model) then does the carbon math per leg —
chosen mode vs the drive/taxi baseline — with DEFRA/JR factors from
green.py, and credits the delta to the ledger.

Model seam stays swappable (same _llm_json as the supervisor; Freesolo can
replace it later). If Gemini is down/slow the canned Tokyo plan below ships
instead — the demo never blocks on the model.

BLOCKING (one model call) — call via asyncio.to_thread from the bot.
"""
from __future__ import annotations
import logging
from typing import Optional

from app.core import state
from app.integrations import green

log = logging.getLogger("trippet.greenplanner")

MODES = set(green.MODE_KG_PER_PKM)

# Canned fallback: a real, sane Tokyo long-weekend (distances ~real).
_FALLBACK_LEGS = [
    {"day": 1, "desc": "Narita airport → Shinjuku", "mode": "train", "km": 66},
    {"day": 1, "desc": "Shinjuku → Shibuya crossing + dinner", "mode": "metro", "km": 5},
    {"day": 2, "desc": "Shinjuku → Asakusa (Senso-ji)", "mode": "metro", "km": 12},
    {"day": 2, "desc": "Asakusa → teamLab Planets", "mode": "metro", "km": 9},
    {"day": 3, "desc": "Tokyo → Kyoto day trip", "mode": "shinkansen", "km": 476},
    {"day": 3, "desc": "Kyoto → Tokyo return", "mode": "shinkansen", "km": 476},
    {"day": 4, "desc": "Shinjuku → Narita airport", "mode": "train", "km": 66},
]


def _llm_legs(city: str, vibe: Optional[str], nights: int) -> Optional[list[dict]]:
    try:
        from app.agents.supervisor import _llm_json
        out = _llm_json(
            f"Plan a realistic {max(2, nights + 1)}-day {city}, Japan itinerary for a "
            f"friend group (vibe: {vibe or 'first-timers'}). Each movement is a leg "
            "with a LOW-CARBON transport mode where sensible. Return ONLY JSON: "
            '{"legs": [{"day": int, "desc": str, "mode": str, "km": number}]} '
            f"with mode one of {sorted(MODES)} and km a realistic distance. "
            "6-10 legs total, include airport transfers, and if the trip is 3+ "
            "days include one intercity day trip by shinkansen (the way most "
            "groups actually do Japan) with its real distance."
        )
        legs = []
        for l in (out or {}).get("legs", []):
            mode = str(l.get("mode", "")).lower()
            km = float(l.get("km", 0))
            if l.get("desc") and mode in MODES and 0 < km <= 800:
                legs.append({"day": int(l.get("day", 1)), "desc": l["desc"],
                             "mode": mode, "km": round(km, 1)})
        return legs[:10] if len(legs) >= 4 else None
    except Exception as e:
        log.warning("itinerary LLM failed (%s) — using canned plan", e)
        return None


def build_itinerary(chat_id: int) -> str:
    """Generate (or fall back), credit transit savings once, render the text."""
    g = state.get_or_create(chat_id)
    city = (g.trip.city or "Tokyo").split(",")[0]
    nights = 3
    if g.trip.dates and g.trip.dates.start and g.trip.dates.end:
        nights = max(1, (g.trip.dates.end - g.trip.dates.start).days)
    people = int(g.trip.group_size or 4)

    legs = _llm_legs(city, g.trip.vibe, nights) or _FALLBACK_LEGS
    per_person = sum(green.transit_saving_vs_car_kg(l["mode"], l["km"]) for l in legs)
    total = round(per_person * people, 1)

    from app.integrations import db
    if not db.get_plan(chat_id).get("itinerary_credited"):
        green.record_saving(chat_id, "transit", total,
                            "rail + transit over cars, whole group",
                            {"legs": legs, "people": people,
                             "per_person_kg": round(per_person, 1)})
        db.update_plan(chat_id, {"itinerary_credited": True, "itinerary_legs": legs})

    mode_icon = {"shinkansen": "🚄", "train": "🚆", "metro": "🚇", "bus": "🚌",
                 "coach": "🚌", "ferry": "⛴️", "walk": "🚶", "bike": "🚲",
                 "car": "🚗", "taxi": "🚕"}
    lines = [f"🗾 how we get around {city} (green-routed):"]
    cur_day = None
    for l in legs:
        if l["day"] != cur_day:
            cur_day = l["day"]
            lines.append(f"day {cur_day}:")
        lines.append(f"  {mode_icon.get(l['mode'], '🚆')} {l['desc']} — "
                     f"{l['mode']}, {l['km']:.0f} km")
    lines.append(f"🌱 rail over road saves your group of {people} "
                 f"~{total:,.0f} kg CO2e vs doing this by car/taxi. "
                 "it all counts — /saved for the running total.")
    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(build_itinerary(0))
