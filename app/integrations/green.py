"""Green engine — carbon math + savings ledger (Deloitte "AI for Green" track).

Design rules (same spirit as db.py):
  - ALL carbon math is local constants from published sources — no network
    call can ever break a /saved or a flight estimate mid-demo.
  - The ledger is memory-first and mirrored to Mongo (`green_ledger`); if
    Atlas flakes, /saved still answers from memory. Never raises.
  - Every estimate is traced through the `trippet.green` logger with the
    factors used, so judges can see the pipeline is real, not vibes.

Emission factor sources (constants below cite them inline):
  - Flights:        UK DEFRA/DESNZ 2024 GHG conversion factors, long-haul
                    economy incl. radiative forcing (~0.1495 kg CO2e/pax-km).
  - Ground:         DEFRA 2024 (coach, local bus, average car) + JR Central
                    sustainability report (Shinkansen ~17 g CO2e/pax-km).
  - Hotels:         Cornell Hotel Sustainability Benchmarking (CHSB) 2023,
                    Japan average ~31 kg CO2e/room-night, scaled by class.
  - Equivalencies:  US EPA GHG Equivalencies Calculator (miles driven,
                    smartphone charges, home electricity, tree seedlings).
"""
from __future__ import annotations
import logging
import math
import threading
from typing import Optional

from app.integrations import db

log = logging.getLogger("trippet.green")

# ─── Factors: flights ────────────────────────────────────────────────────────
FLIGHT_KG_PER_PKM = 0.1495     # DEFRA 2024 long-haul economy, incl. RF
STOP_PENALTY_KG = 50.0         # extra takeoff/landing cycle per connection (ICAO-style)
UNKNOWN_DETOUR_PER_STOP = 0.08 # +8% distance when the layover airport is unknown

# ─── Factors: ground transport, kg CO2e per passenger-km ────────────────────
MODE_KG_PER_PKM = {
    "shinkansen": 0.017,   # JR Central sustainability report
    "train": 0.028,        # DEFRA 2024 national/light rail
    "metro": 0.028,
    "bus": 0.102,          # DEFRA 2024 local bus
    "coach": 0.027,        # DEFRA 2024 intercity coach
    "car": 0.084,          # DEFRA 2024 average car 0.168/vehicle-km ÷ 2 occupants
    "taxi": 0.084,
    "ferry": 0.019,        # DEFRA 2024 foot passenger
    "walk": 0.0,
    "bike": 0.0,
}
CAR_BASELINE_KG_PER_PKM = MODE_KG_PER_PKM["car"]  # "what if they'd driven/taxied"

# ─── Factors: hotels, kg CO2e per room-night (CHSB 2023 Japan, by class) ────
HOTEL_KG_PER_ROOM_NIGHT = 31.0      # Japan average, all classes
HOTEL_CLASS_FACTORS = [
    # (keyword in type/name, kg CO2e per room-night)
    (("hostel", "capsule", "dorm"), 12.5),
    (("ryokan", "guesthouse", "guest house", "minshuku", "apartment", "apart"), 20.0),
    (("resort", "luxury", "grand", "imperial"), 45.0),
]
# CHSB: footprint per room-night rises steeply with service class (pools,
# restaurants, daily laundry, conditioned public space).
HOTEL_STAR_FACTORS = {5: 45.0, 4: 36.0, 3: 31.0, 2: 24.0, 1: 22.0}
# Rate is an amenity proxy within one market — applied as a bounded ±25% nudge
# so it refines the class estimate without overriding it.
HOTEL_PRICE_SWING = 0.25

# ─── EPA GHG equivalencies (per kg CO2e) ────────────────────────────────────
KG_PER_CAR_MILE = 0.394        # EPA: 3.94e-4 t CO2e per mile, avg gasoline car
KG_PER_PHONE_CHARGE = 0.00822  # EPA: 8.22e-6 t per smartphone charge
KG_PER_HOME_ELEC_DAY = 15.1    # EPA: ~5.5 t/yr electricity per avg US home ÷ 365
KG_PER_TREE_10YR = 60.5        # EPA: 0.0605 t per urban tree seedling grown 10 yrs
KG_PER_GAL_GASOLINE = 8.887    # EPA

SOURCES_LINE = "sources: DEFRA 2024 · EPA equivalencies · CHSB 2023 · JR Central"

# ─── Airport coordinates (for great-circle flight distances) ────────────────
_AIRPORTS = {
    # Canada / US hubs
    "YYZ": (43.6772, -79.6306), "YVR": (49.1947, -123.1792),
    "ORD": (41.9742, -87.9073), "SEA": (47.4502, -122.3088),
    "SFO": (37.6213, -122.3790), "LAX": (33.9416, -118.4085),
    "EWR": (40.6895, -74.1745), "DFW": (32.8998, -97.0403),
    "IAH": (29.9902, -95.3368), "DTW": (42.2162, -83.3554),
    "MSP": (44.8848, -93.2223), "HNL": (21.3245, -157.9251),
    # Japan
    "NRT": (35.7647, 140.3864), "HND": (35.5494, 139.7798),
    "KIX": (34.4342, 135.2440), "ITM": (34.7855, 135.4382),
    "CTS": (42.7752, 141.6923), "FUK": (33.5859, 130.4510),
    "NGO": (34.8584, 136.8054), "OKA": (26.1958, 127.6459),
    # Asian connection hubs
    "ICN": (37.4602, 126.4407), "TPE": (25.0777, 121.2328),
    "PVG": (31.1443, 121.8083), "HKG": (22.3080, 113.9185),
}

CITY_AIRPORT = {
    "tokyo": "NRT", "osaka": "KIX", "kyoto": "KIX", "sapporo": "CTS",
    "fukuoka": "FUK", "nagoya": "NGO", "okinawa": "OKA", "hiroshima": "KIX",
}


def airport_for_city(city: Optional[str]) -> str:
    key = (city or "tokyo").split(",")[0].strip().lower()
    return CITY_AIRPORT.get(key, "NRT")


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def leg_km(origin: str, dest: str) -> Optional[float]:
    a, b = _AIRPORTS.get(origin.upper()), _AIRPORTS.get(dest.upper())
    return _haversine_km(a, b) if a and b else None


# ─── Flight CO2 ──────────────────────────────────────────────────────────────
def flight_co2_kg(origin: str, dest: str, stops: int = 0,
                  via: Optional[list[str]] = None, roundtrip: bool = True) -> float:
    """kg CO2e per passenger. Distance is great-circle over the actual legs
    when the layover airports are known, else direct + a detour % per stop."""
    direct = leg_km(origin, dest) or 10300.0  # YYZ→NRT-ish default
    km = 0.0
    if via:
        hops = [origin, *via, dest]
        for i in range(len(hops) - 1):
            km += leg_km(hops[i], hops[i + 1]) or 0.0
    if km <= 0:
        km = direct * (1 + UNKNOWN_DETOUR_PER_STOP * max(0, stops))
    one_way = km * FLIGHT_KG_PER_PKM + max(0, stops) * STOP_PENALTY_KG
    total = one_way * (2 if roundtrip else 1)
    log.info("trace flight %s→%s via=%s stops=%d km=%.0f factor=%.4f rt=%s → %.0f kg",
             origin, dest, via, stops, km, FLIGHT_KG_PER_PKM, roundtrip, total)
    return round(total, 1)


# ─── Ground transport CO2 ────────────────────────────────────────────────────
def transit_co2_kg(mode: str, km: float) -> float:
    """kg CO2e per passenger for one ground leg."""
    factor = MODE_KG_PER_PKM.get((mode or "").lower(), MODE_KG_PER_PKM["train"])
    return round(factor * max(0.0, km), 2)


def transit_saving_vs_car_kg(mode: str, km: float) -> float:
    """How much one passenger avoids by taking `mode` instead of car/taxi."""
    return round(max(0.0, (CAR_BASELINE_KG_PER_PKM
                           - MODE_KG_PER_PKM.get((mode or "").lower(), 0.0)) * km), 2)


# ─── Hotel CO2 ───────────────────────────────────────────────────────────────
def hotel_kg_per_night(hotel_type: str = "", name: str = "",
                       stars: Optional[float] = None,
                       price_per_night: Optional[float] = None,
                       market_median_price: Optional[float] = None) -> float:
    """Estimated kg CO2e for ONE room-night, from property class.

    Signal order: an explicit property-type keyword beats a star rating beats
    the market average. Stay22 reports nearly everything as "Accommodation",
    so stars carry most of the weight in practice; the nightly rate then
    applies a bounded ±25% amenity nudge relative to the local market."""
    hay = f"{hotel_type} {name}".lower()
    base = None
    for keywords, kg in HOTEL_CLASS_FACTORS:
        if any(k in hay for k in keywords):
            base = kg
            break
    if base is None and stars:
        base = HOTEL_STAR_FACTORS.get(int(stars), HOTEL_KG_PER_ROOM_NIGHT)
    if base is None:
        base = HOTEL_KG_PER_ROOM_NIGHT

    if price_per_night and market_median_price and market_median_price > 0:
        ratio = price_per_night / market_median_price
        nudge = max(-HOTEL_PRICE_SWING, min(HOTEL_PRICE_SWING, (ratio - 1) * 0.5))
        base *= (1 + nudge)
    return round(base, 1)


def stay_footprint_kg(card: dict, group_size: int, nights: int,
                      market_median_price: Optional[float] = None) -> float:
    """Total kg CO2e for the WHOLE group's stay at one property.

    The honest driver is how many rooms the party actually needs: a unit
    sleeping 8 houses a group of 8 in one footprint, where a 2-guest room
    needs four. Capacity only helps to the extent the group fills it."""
    per_room = hotel_kg_per_night(card.get("type") or "", card.get("name") or "",
                                  card.get("stars"), card.get("price_per_night"),
                                  market_median_price)
    capacity = max(1, int(card.get("guests") or 2))
    rooms = math.ceil(max(1, group_size) / capacity)
    return round(per_room * rooms * max(1, nights), 1)


# ─── Savings ledger (memory-first, Mongo-mirrored) ──────────────────────────
_ledger: dict[int, list[dict]] = {}
_hydrated: set[int] = set()
_LEDGER_LOCK = threading.Lock()

KIND_LABEL = {"flight": "✈️ flights", "transit": "🚄 getting around",
              "hotel": "🏨 the stay"}


def _hydrate(chat_id: int) -> None:
    """Pull persisted events once per process so /saved survives restarts."""
    if chat_id in _hydrated:
        return
    _hydrated.add(chat_id)
    for ev in db.green_events(chat_id):
        _ledger.setdefault(chat_id, []).append(ev)


def record_saving(chat_id: int, kind: str, co2_kg: float, note: str,
                  meta: Optional[dict] = None) -> None:
    """One avoided-emissions event. kind: flight | transit | hotel."""
    if co2_kg <= 0:
        return
    ev = {"kind": kind, "co2_kg": round(float(co2_kg), 1), "note": note,
          "meta": meta or {}}
    with _LEDGER_LOCK:
        _hydrate(chat_id)
        _ledger.setdefault(chat_id, []).append(ev)
    db.log_green_event(chat_id, kind, ev["co2_kg"], note, meta)
    log.info("SAVED chat=%s kind=%s co2=%.1fkg note=%s", chat_id, kind, co2_kg, note)


def totals(chat_id: int) -> dict:
    """{total_kg, by_kind: {kind: kg}, events: [...]} — memory-first."""
    with _LEDGER_LOCK:
        _hydrate(chat_id)
        events = list(_ledger.get(chat_id, []))
    by_kind: dict[str, float] = {}
    for ev in events:
        by_kind[ev["kind"]] = round(by_kind.get(ev["kind"], 0.0) + ev["co2_kg"], 1)
    return {"total_kg": round(sum(by_kind.values()), 1),
            "by_kind": by_kind, "events": events}


def forget(chat_id: int) -> None:
    """/reset support."""
    with _LEDGER_LOCK:
        _ledger.pop(chat_id, None)
        _hydrated.discard(chat_id)


# ─── Human units (EPA equivalencies) ────────────────────────────────────────
def _fmt(n: float) -> str:
    if n >= 100:
        return f"{n:,.0f}"
    return f"{n:.1f}".rstrip("0").rstrip(".")


def fun_equivalents(kg: float) -> list[str]:
    """2-3 tangible lines sized to the number (EPA equivalency factors)."""
    if kg <= 0:
        return []
    lines = [f"🚗 {_fmt(kg / KG_PER_CAR_MILE)} miles NOT driven in a gas car"]
    if kg >= 30:
        lines.append(f"🔌 {_fmt(kg / KG_PER_PHONE_CHARGE)} smartphone charges")
    else:
        lines.append(f"⛽ {_fmt(kg / KG_PER_GAL_GASOLINE)} gallons of gasoline unburned")
    if kg >= 55:
        lines.append(f"🌳 {_fmt(kg / KG_PER_TREE_10YR)} tree seedlings growing for 10 years")
    elif kg >= 15:
        lines.append(f"🏠 {_fmt(kg / KG_PER_HOME_ELEC_DAY)} days of an American home's electricity")
    return lines


def scale_up_line(kg: float, groups: int = 1000) -> Optional[str]:
    """The judges' line: this trip × N groups, in home-electricity-years."""
    if kg <= 0:
        return None
    total_t = kg * groups / 1000.0
    homes_years = (kg * groups) / (KG_PER_HOME_ELEC_DAY * 365)
    return (f"if {groups:,} groups planned like this: {_fmt(total_t)} tonnes CO2e — "
            f"the annual electricity of {_fmt(homes_years)} American homes")


def render_saved(chat_id: int) -> str:
    """/saved — the full ledger card."""
    t = totals(chat_id)
    if t["total_kg"] <= 0:
        return ("🌱 nothing on the green ledger yet.\n"
                "lock a flight, pick the 🌱 hotel, or ask me for the itinerary — "
                "every green choice gets counted here.")
    lines = [f"🌱 green ledger — this trip has avoided *{_fmt(t['total_kg'])} kg CO2e*"]
    for kind, kgv in t["by_kind"].items():
        note = next((e["note"] for e in reversed(t["events"]) if e["kind"] == kind), "")
        if len(note) > 52:
            note = note[:49].rstrip() + "…"
        lines.append(f"  {KIND_LABEL.get(kind, kind)}: {_fmt(kgv)} kg" + (f" ({note})" if note else ""))
    lines.append("that's like:")
    lines += [f"  {eq}" for eq in fun_equivalents(t["total_kg"])]
    big = scale_up_line(t["total_kg"], 1000)
    if big:
        lines.append(f"📈 {big}")
    lines.append(f"_{SOURCES_LINE}_")
    return "\n".join(lines)
