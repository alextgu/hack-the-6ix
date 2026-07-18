"""Reusable Stay22 client, promoted from stay22_probe.py.

Keyless demo mode works (5 req/min) — the throttle enforces >12s between
calls at the module level so we can't accidentally get 429'd. Pass
STAY22_AID env var for affiliate attribution.

Not wired into the bot directly — `wire.py` calls this.
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from statistics import median
from typing import Optional


ENDPOINT = "https://api.stay22.com/v2/accommodations"

# Keyless demo tier is 5 req/min per Stay22 docs; leave headroom.
_MIN_INTERVAL_S = 12.0
_last_call_at: float = 0.0


def request_headers() -> dict[str, str]:
    """Shared headers for every Stay22 call (hotels.py uses this too).
    STAY22_API_KEY set → authenticated tier via Bearer; blank → keyless demo.
    The 12s throttle stays on either way as a safety net."""
    h = {"Accept": "application/json", "User-Agent": "trippet/1.0"}
    key = os.environ.get("STAY22_API_KEY", "").strip()
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _throttle() -> None:
    """Sleep until we're allowed to make another call. Safe to call from a
    thread (via asyncio.to_thread) — blocking sleep won't stall the event loop."""
    global _last_call_at
    wait = _MIN_INTERVAL_S - (time.time() - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.time()


def _location_params(loc: str) -> dict:
    """Accept 'City, Country' or 'lat,lng'. Sniff which."""
    s = loc.strip()
    parts = [p.strip() for p in s.split(",")]
    if len(parts) == 2:
        try:
            lat, lng = float(parts[0]), float(parts[1])
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {"lat": lat, "lng": lng}
        except ValueError:
            pass
    return {"address": s if "japan" in s.lower() else f"{s}, Japan"}


def get_stay(
    city_or_latlng: str,
    checkin: str,          # YYYY-MM-DD
    checkout: str,         # YYYY-MM-DD
    guests: int = 2,
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
        "currency": "USD",
        "pageSize": 30,
        "page": 1,
    }
    aid = os.environ.get("STAY22_AID", "").strip()
    if aid:
        params["aid"] = aid
        params["campaign"] = "trippet_live"

    _throttle()
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=request_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"[stay22] get_stay failed: {type(e).__name__}: {e}", file=sys.stderr)
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
        "currency": "USD",
        "pageSize": 30,
        "page": 1,
    }
    aid = os.environ.get("STAY22_AID", "").strip()
    if aid:
        params["aid"] = aid
        params["campaign"] = "trippet_live"

    _throttle()
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=request_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"[stay22] search_raw failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None

    return data.get("results") or []


if __name__ == "__main__":
    from datetime import date, timedelta
    ci = (date.today() + timedelta(weeks=6)).isoformat()
    co = (date.today() + timedelta(weeks=6, days=2)).isoformat()
    print(json.dumps(get_stay("Tokyo, Japan", ci, co, guests=2), indent=2))
