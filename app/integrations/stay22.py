"""Reusable Stay22 client, promoted from stay22_probe.py.

Keyless demo mode works (5 req/min) — the throttle enforces >12s between calls
at the module level so we can't accidentally get 429'd. Set STAY22_API_KEY for
the authenticated tier (150 req/min) and the throttle relaxes to 0.5s. Pass
STAY22_AID env var for affiliate attribution.

Not wired into the bot directly — `wire.py` calls this.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import time
import urllib.request
import urllib.parse
from statistics import median
from typing import Optional


log = logging.getLogger("trippet.stay22")

ENDPOINT = "https://api.stay22.com/v2/accommodations"

# Demo tier is 5 req/min per IP → 12s spacing. Authenticated is 150 req/min
# per key (sliding 60s window), so an authenticated deck can refresh in-place
# instead of making the group wait out a throttle.
_DEMO_INTERVAL_S = 12.0
_AUTH_INTERVAL_S = 0.5
_last_call_at: float = 0.0


def _min_interval() -> float:
    return _AUTH_INTERVAL_S if authenticated() else _DEMO_INTERVAL_S

# ─── Geocoding ──────────────────────────────────────────────────────────────
# `address=` is geocoded upstream and is NOT reliable for Japanese places:
# probed 2026-07-18, "Tokyo, Japan" resolves to the Izu Peninsula (Shimoda /
# Minamiizu, ~150 km south) and "Shibuya, Tokyo, Japan" lands in Shibaura.
# The same queries as lat/lng + radius return correct central-Tokyo inventory.
# So: resolve known places locally, and only fall back to `address=`.
DEFAULT_RADIUS_M = 12_000

CITY_COORDS: dict[str, tuple[float, float]] = {
    # Tokyo + wards/neighbourhoods (basecamp candidates)
    "tokyo": (35.6812, 139.7671),      "shinjuku": (35.6896, 139.7006),
    "shibuya": (35.6580, 139.7016),    "ginza": (35.6717, 139.7650),
    "asakusa": (35.7148, 139.7967),    "ikebukuro": (35.7295, 139.7109),
    "roppongi": (35.6628, 139.7315),   "akihabara": (35.6984, 139.7731),
    "ueno": (35.7138, 139.7770),       "shinagawa": (35.6285, 139.7387),
    "marunouchi": (35.6812, 139.7671),
    # Other Japanese cities
    "osaka": (34.7025, 135.4959),      "namba": (34.6659, 135.5011),
    "kyoto": (34.9858, 135.7588),      "gion": (35.0037, 135.7788),
    "sapporo": (43.0687, 141.3508),    "fukuoka": (33.5898, 130.4207),
    "hakata": (33.5898, 130.4207),     "nagoya": (35.1706, 136.8816),
    "hiroshima": (34.3975, 132.4756),  "okinawa": (26.2124, 127.6809),
    "naha": (26.2124, 127.6809),       "yokohama": (35.4657, 139.6222),
    "nara": (34.6851, 135.8048),       "kobe": (34.6913, 135.1830),
    "kanazawa": (36.5780, 136.6486),   "sendai": (38.2606, 140.8819),
    "hakone": (35.2324, 139.1069),     "nikko": (36.7198, 139.6982),
    "kamakura": (35.3192, 139.5468),   "takayama": (36.1461, 137.2522),
    "niseko": (42.8048, 140.6874),     "hakodate": (41.7737, 140.7264),
    "kawaguchiko": (35.4996, 138.7539),
}


def bbox_around(lat: float, lng: float, radius_m: int = DEFAULT_RADIUS_M) -> dict:
    """Square viewport centred on a point, as nelat/nelng/swlat/swlng.

    Needed for clustering: the API treats "center+radius without a bbox" as a
    structural blocker and always returns a flat list, so `cluster=top` is
    silently ignored unless the viewport is expressed as a bounding box."""
    import math
    dlat = (radius_m / 1000.0) / 111.32
    dlng = (radius_m / 1000.0) / (111.32 * max(0.01, math.cos(math.radians(lat))))
    return {"nelat": round(lat + dlat, 6), "nelng": round(lng + dlng, 6),
            "swlat": round(lat - dlat, 6), "swlng": round(lng - dlng, 6)}


def resolve_coords(place: str) -> Optional[tuple[float, float]]:
    """'Shinjuku, Tokyo, Japan' → (lat, lng), or None if we don't know it.
    Tries the most specific comma part first so 'Shinjuku, Tokyo' resolves to
    Shinjuku rather than Tokyo."""
    for part in [p.strip().lower() for p in (place or "").split(",")]:
        part = part.replace("-ku", "").replace(" city", "").strip()
        if part and part != "japan" and part in CITY_COORDS:
            return CITY_COORDS[part]
    return None


def campaign_tag(base: str, chat_id: Optional[int] = None) -> str:
    """Stay22 attribution tag. The spec requires '-' as the separator.

    A constant tag makes every group indistinguishable in Hub reporting; tagging
    per chat is what lets a booking be joined back to one group's pet. The
    chat id is hashed — it's a Telegram identifier and this string leaves our
    system in an outbound URL."""
    if chat_id is None:
        return base
    digest = hashlib.sha256(str(chat_id).encode()).hexdigest()[:10]
    return f"{base}-{digest}"


def attribution_params(base: str, chat_id: Optional[int] = None) -> dict:
    """{aid, campaign} when STAY22_AID is set, else {} (keyless demo)."""
    aid = os.environ.get("STAY22_AID", "").strip()
    if not aid:
        return {}
    return {"aid": aid, "campaign": campaign_tag(base, chat_id)}


def authenticated() -> bool:
    return bool(os.environ.get("STAY22_API_KEY", "").strip())


# ISO 4217, case-insensitive upstream; invalid codes are rejected with a 400,
# so keep this to codes we've actually meant to support. Stay22 converts from
# USD, and a supplier that can't natively price a currency falls back — so the
# response's own meta.currency is the authority, not this request value.
SUPPORTED_CURRENCIES = {"USD", "CAD", "EUR", "GBP", "JPY", "AUD"}
ZERO_DECIMAL = {"JPY"}   # yen has no minor unit — never render "¥12,345.00"


def currency() -> str:
    """Display currency for every Stay22 call. A Toronto group planning in CAD
    shouldn't have to convert in their heads mid-argument."""
    c = (os.environ.get("STAY22_CURRENCY") or "USD").strip().upper()
    if c not in SUPPORTED_CURRENCIES:
        log.warning("STAY22_CURRENCY=%r unsupported — falling back to USD", c)
        return "USD"
    return c


_SYMBOLS = {"USD": "$", "CAD": "CA$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$"}


def fmt_money(amount: float, cur: Optional[str] = None) -> str:
    """Whole-unit money for chat text. Mirrors the Mini App's money() so the
    same price never appears as '$420' in one surface and 'CA$420' in another."""
    cur = (cur or currency()).upper()
    return f"{_SYMBOLS.get(cur, cur + ' ')}{round(amount):,}"


def request_headers() -> dict[str, str]:
    """Shared headers for every Stay22 call (hotels.py uses this too).

    Auth is the `X-API-KEY` header — NOT `Authorization: Bearer`. We sent
    Bearer until 2026-07-18, which the gateway ignores, so a perfectly good
    key silently left us on the 5 req/min demo tier instead of 150 req/min.
    Rate limits per the OpenAPI spec: demo 5/min per IP, authenticated
    150/min per key, sliding 60s window."""
    h = {"Accept": "application/json", "User-Agent": "trippet/1.0"}
    key = os.environ.get("STAY22_API_KEY", "").strip()
    if key:
        h["X-API-KEY"] = key
    return h


def _throttle() -> None:
    """Sleep until we're allowed to make another call. Safe to call from a
    thread (via asyncio.to_thread) — blocking sleep won't stall the event loop."""
    global _last_call_at
    wait = _min_interval() - (time.time() - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.time()


def _location_params(loc: str, as_bbox: bool = False,
                     radius_m: int = DEFAULT_RADIUS_M) -> dict:
    """Accept 'City, Country' or 'lat,lng'. Sniff which.

    Resolution order: explicit lat,lng → known place from CITY_COORDS →
    `address=`. The address path is last because upstream geocoding misplaces
    Japanese cities badly (see CITY_COORDS).

    `as_bbox` returns a bounding box rather than center+radius — required by
    callers that want clustering (see bbox_around)."""
    def _geo(lat: float, lng: float) -> dict:
        if as_bbox:
            return bbox_around(lat, lng, radius_m)
        return {"lat": lat, "lng": lng, "radius": radius_m}

    s = loc.strip()
    parts = [p.strip() for p in s.split(",")]
    if len(parts) == 2:
        try:
            lat, lng = float(parts[0]), float(parts[1])
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return _geo(lat, lng)
        except ValueError:
            pass
    known = resolve_coords(s)
    if known:
        return _geo(*known)
    log.warning("no local coords for %r — falling back to address= (geocode may be off)", s)
    return {"address": s if "japan" in s.lower() else f"{s}, Japan"}


def get_stay(
    city_or_latlng: str,
    checkin: str,          # YYYY-MM-DD
    checkout: str,         # YYYY-MM-DD
    guests: int = 2,
    chat_id: Optional[int] = None,
) -> Optional[dict]:
    """One call → {price_cheapest, price_median, result_count}.

    Returns None on network/decode errors or if inputs are incomplete.
    Result count of 0 with prices=None means the address geocoded fine
    but no supplier had a price for those dates."""
    if not (city_or_latlng and checkin and checkout):
        return None

    params: dict[str, object] = {
        **_location_params(city_or_latlng),
        "checkin": checkin,
        "checkout": checkout,
        "adults": max(1, int(guests)),
        "rooms": max(1, int(guests) // 2 or 1),
        "currency": currency(),
        "pageSize": 30,
        "page": 1,
    }
    params.update(attribution_params("trippet-live", chat_id))

    _throttle()
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=request_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        # Any failure (HTTP, network, timeout, bad JSON) → None so the caller
        # falls back to last-known state; a live demo never crashes on this.
        log.warning("get_stay failed: %s: %s", type(e).__name__, e)
        return None

    results = data.get("results") or []
    prices: list[float] = []
    for r in results:
        # take first supplier that quotes a price
        for s in (r.get("suppliers") or {}).values():
            p = (s.get("price") or {}).get("total")
            if p:
                prices.append(float(p))
                break

    return {
        "price_cheapest": min(prices) if prices else None,
        "price_median":   float(median(prices)) if prices else None,
        "result_count":   len(results),
    }


def search_raw(
    city_or_latlng: str,
    checkin: str,
    checkout: str,
    guests: int = 2,
    chat_id: Optional[int] = None,
) -> Optional[list[dict]]:
    """Same call semantics as get_stay(), but returns the raw `results[]`
    array so callers (booking.py) can pick a specific hotel by rating/price.

    Not a rewrite of get_stay — additive. Small duplication of the request
    block is intentional: keep get_stay's behavior 100% stable.
    """
    if not (city_or_latlng and checkin and checkout):
        return None

    params: dict[str, object] = {
        **_location_params(city_or_latlng),
        "checkin": checkin,
        "checkout": checkout,
        "adults": max(1, int(guests)),
        "rooms": max(1, int(guests) // 2 or 1),
        "currency": currency(),
        "pageSize": 30,
        "page": 1,
    }
    params.update(attribution_params("trippet-live", chat_id))

    _throttle()
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=request_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        # Any failure → None; cmd_commit degrades to "no rooms" instead of crashing.
        log.warning("search_raw failed: %s: %s", type(e).__name__, e)
        return None

    return data.get("results") or []


if __name__ == "__main__":
    from datetime import date, timedelta
    ci = (date.today() + timedelta(weeks=6)).isoformat()
    co = (date.today() + timedelta(weeks=6, days=2)).isoformat()
    print(json.dumps(get_stay("Tokyo, Japan", ci, co, guests=2), indent=2))
