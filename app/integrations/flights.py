"""Flight options — live Amadeus test API with a bulletproof fallback chain.

Chain (the demo can NEVER die here):
  1. Amadeus Self-Service test API (only if AMADEUS_CLIENT_ID/SECRET are set;
     8s total budget, one attempt, cached per chat for the process lifetime)
  2. data/flight_offers.json — bundled realistic YYZ→Japan offers
  3. mock_options() — the original seeded generator, priced off the budget

Whatever the source, every option is enriched IDENTICALLY by the green
engine: great-circle CO2e per passenger (DEFRA factors, computed locally —
no API involved), the lowest-carbon option is flagged 🌱, and the delta vs
the dirtiest option is what /saved counts when the group locks the green one.

The options actually POSTED to a chat are persisted in the trip plan
("flight_options") so the lock step always scores against exactly what the
group saw — even across a restart mid-demo.
"""
from __future__ import annotations
import json
import logging
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from app.integrations import green

log = logging.getLogger("trippet.flights")

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_FILE = ROOT / "data" / "flight_offers.json"

AIRLINES = ["ANA", "Japan Airlines", "Air Canada", "Zipair", "United"]
_CARRIER_NAMES = {
    "AC": "Air Canada", "NH": "ANA", "JL": "Japan Airlines", "TK": "Turkish",
    "UA": "United", "AA": "American", "DL": "Delta", "ZG": "Zipair",
    "KE": "Korean Air", "OZ": "Asiana", "BR": "EVA Air", "CX": "Cathay Pacific",
    "WS": "WestJet",
}

_AMADEUS_BASE = "https://test.api.amadeus.com"
_token: dict = {"value": None, "expires_at": 0.0}
_options_cache: dict[int, list[dict]] = {}   # chat_id → enriched options


# ─── Source 3: the original mock (final fallback, never fails) ───────────────
def mock_options(chat_id: int, city: Optional[str], budget: Optional[int]) -> list[dict]:
    rng = random.Random(chat_id)  # stable per group
    base = min(max((budget or 1200) * 0.55, 450), 1400)
    dest = green.airport_for_city(city)
    opts = []
    for i, style in enumerate(["cheapest", "balanced", "comfy"], start=1):
        mult = {"cheapest": 0.82, "balanced": 1.0, "comfy": 1.28}[style]
        price = int(base * mult / 10) * 10
        stops = {"cheapest": 1, "balanced": 1 if rng.random() < 0.5 else 0, "comfy": 0}[style]
        opts.append({
            "n": i,
            "airline": rng.choice(AIRLINES),
            "route": f"YYZ → {dest}",
            "origin": "YYZ", "dest": dest,
            "price": price,
            "stops": stops,
            "via": ["ORD"] if stops else [],
            "style": style,
            "source": "estimated",
        })
    return opts


# ─── Source 2: bundled fixture ───────────────────────────────────────────────
def _fixture_options(city: Optional[str]) -> list[dict]:
    try:
        raw = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("flight fixture unreadable: %s", e)
        return []
    dest = green.airport_for_city(city)
    pool = [o for o in raw.get("options", []) if o.get("dest") == dest] \
        or raw.get("options", [])
    opts = []
    for i, o in enumerate(pool[:3], start=1):
        opts.append({
            "n": i,
            "airline": o.get("airline", "ANA"),
            "route": f"{o.get('origin', 'YYZ')} → {o.get('dest', dest)}",
            "origin": o.get("origin", "YYZ"), "dest": o.get("dest", dest),
            "price": int(o.get("price", 1100)),
            "stops": int(o.get("stops", 0)),
            "via": o.get("via", []),
            "style": o.get("style", "balanced"),
            "source": "cached",
        })
    return opts


# ─── Source 1: Amadeus test API ──────────────────────────────────────────────
def _amadeus_token() -> Optional[str]:
    cid = os.environ.get("AMADEUS_CLIENT_ID", "").strip()
    secret = os.environ.get("AMADEUS_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        return None
    if _token["value"] and time.time() < _token["expires_at"] - 60:
        return _token["value"]
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": cid,
        "client_secret": secret}).encode()
    req = urllib.request.Request(
        f"{_AMADEUS_BASE}/v1/security/oauth2/token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=4) as resp:
        data = json.loads(resp.read())
    _token["value"] = data.get("access_token")
    _token["expires_at"] = time.time() + float(data.get("expires_in", 1799))
    return _token["value"]


def _amadeus_options(city: Optional[str], departure_date: Optional[str]) -> list[dict]:
    """One live search. Raises nothing to callers — get_options wraps it."""
    token = _amadeus_token()
    if not token:
        return []
    dest = green.airport_for_city(city)
    if not departure_date:
        from app.integrations.hotels import default_dates
        departure_date = default_dates()[0]
    params = urllib.parse.urlencode({
        "originLocationCode": "YYZ", "destinationLocationCode": dest,
        "departureDate": departure_date, "adults": 1, "max": 12,
        "currencyCode": "USD",
    })
    req = urllib.request.Request(
        f"{_AMADEUS_BASE}/v2/shopping/flight-offers?{params}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read())
    carriers = (data.get("dictionaries") or {}).get("carriers") or {}

    seen: set[tuple] = set()
    parsed = []
    for offer in data.get("data") or []:
        try:
            segs = offer["itineraries"][0]["segments"]
            code = segs[0]["carrierCode"]
            via = [s["arrival"]["iataCode"] for s in segs[:-1]]
            price = float(offer["price"]["grandTotal"])
            key = (code, tuple(via))
            if key in seen:
                continue
            seen.add(key)
            parsed.append({
                "airline": _CARRIER_NAMES.get(code) or carriers.get(code, code).title(),
                "origin": segs[0]["departure"]["iataCode"],
                "dest": segs[-1]["arrival"]["iataCode"],
                "price": int(round(price)),
                "stops": len(segs) - 1,
                "via": via,
            })
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    if not parsed:
        return []
    # a real decision set: cheapest, a nonstop/fewest-stops, and one more
    by_price = sorted(parsed, key=lambda o: o["price"])
    by_stops = sorted(parsed, key=lambda o: (o["stops"], o["price"]))
    picks: list[dict] = []
    for cand in (by_price[0], by_stops[0], *by_price[1:]):
        if cand not in picks:
            picks.append(cand)
        if len(picks) == 3:
            break
    opts = []
    for i, o in enumerate(picks, start=1):
        opts.append({**o, "n": i, "route": f"{o['origin']} → {o['dest']}",
                     "style": "live", "source": "live"})
    return opts


# ─── Enrichment + the public entry point ─────────────────────────────────────
def _enrich(opts: list[dict]) -> list[dict]:
    """Local CO2e per option + 🌱 flag on the lowest-carbon one."""
    for o in opts:
        o["co2_kg"] = green.flight_co2_kg(o.get("origin", "YYZ"),
                                          o.get("dest", "NRT"),
                                          o.get("stops", 0), o.get("via"))
        o["green"] = False
    if opts:
        min(opts, key=lambda o: o["co2_kg"])["green"] = True
    return opts


def get_options(chat_id: int, city: Optional[str], budget: Optional[int],
                departure_date: Optional[str] = None) -> list[dict]:
    """BLOCKING (possible network) — call via asyncio.to_thread from the bot.
    Never raises, never returns []."""
    if chat_id in _options_cache:
        return _options_cache[chat_id]
    opts: list[dict] = []
    try:
        opts = _amadeus_options(city, departure_date)
        if opts:
            log.info("flights: live Amadeus (chat=%s, %d offers)", chat_id, len(opts))
    except Exception as e:
        log.warning("flights: live fetch failed (%s: %s) — falling back",
                    type(e).__name__, e)
    if not opts:
        opts = _fixture_options(city)
        if opts:
            log.info("flights: bundled fixture (chat=%s)", chat_id)
    if not opts:
        opts = mock_options(chat_id, city, budget)
        log.info("flights: mock generator (chat=%s)", chat_id)
    opts = _enrich(opts)
    _options_cache[chat_id] = opts
    return opts


def forget(chat_id: int) -> None:
    """/reset support."""
    _options_cache.pop(chat_id, None)


def greenest_delta_kg(opts: list[dict]) -> float:
    """kg CO2e per person between the dirtiest and the greenest option."""
    if len(opts) < 2:
        return 0.0
    kgs = [o["co2_kg"] for o in opts if "co2_kg" in o]
    return round(max(kgs) - min(kgs), 1) if len(kgs) >= 2 else 0.0


def _fmt_co2(kg: float) -> str:
    return f"{kg / 1000:.1f} t" if kg >= 1000 else f"{kg:.0f} kg"


def render_options(opts: list[dict]) -> str:
    src = {"live": "live prices", "cached": "recent prices",
           "estimated": "estimated"}.get(opts[0].get("source", "estimated"),
                                         "estimated") if opts else "estimated"
    lines = [f"✈️ flights ({src}) — reply \"flight {'/'.join(str(o['n']) for o in opts)}\":"]
    for o in opts:
        stops = "nonstop" if o["stops"] == 0 else (
            f"1 stop ({o['via'][0]})" if o.get("via") else f"{o['stops']} stop")
        tag = " 🌱 greenest" if o.get("green") else ""
        lines.append(f"  {o['n']}. {o['airline']} {o['route']} — "
                     f"${o['price']}/person · {stops} · "
                     f"{_fmt_co2(o.get('co2_kg', 0))} CO2e{tag}")
    delta = greenest_delta_kg(opts)
    if delta > 0:
        lines.append(f"the 🌱 pick avoids ~{_fmt_co2(delta)} CO2e per person "
                     "vs the dirtiest option (round trip, DEFRA factors)")
    return "\n".join(lines)
