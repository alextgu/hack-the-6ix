"""Real hotel options for the card deck, via the Stay22 accommodations API.

The basecamp is FIXED for now (Shinjuku, Tokyo) — later the agent confirms a
basecamp with the group and passes it in. Every card is a real bookable
property: name, photo, live price for the dates, rating, and a Stay22
affiliate deeplink (that link IS the Stay22 integration for the demo — every
swipe is analytics on Stay22 inventory, and the winning card links out
through Stay22).

Fallback chain (so the demo never dies on stage):
  live Stay22 call → data/japan_hotels.json (cached real response)
                   → sample_response.json (older cached real response)

Reuses stay22.py's module-level throttle so the keyless 5 req/min budget is
shared with wire.py's price polls.
"""
from __future__ import annotations
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import stay22

log = logging.getLogger("trippet.hotels")

ROOT = Path(__file__).parent
CACHE_FILE = ROOT / "data" / "japan_hotels.json"
LEGACY_SAMPLE = ROOT / "sample_response.json"

# Demo basecamp — fixed. The agent seam replaces this with the confirmed one.
BASECAMP_NAME = "Shinjuku, Tokyo"
BASECAMP_QUERY = "Shinjuku, Tokyo, Japan"


def default_dates() -> tuple[str, str]:
    """Fri→Sun about six weeks out — far enough that suppliers quote prices."""
    d = date.today() + timedelta(weeks=6)
    fri = d + timedelta(days=(4 - d.weekday()) % 7)
    return fri.isoformat(), (fri + timedelta(days=2)).isoformat()


def _fetch_raw(query: str, checkin: str, checkout: str, guests: int) -> Optional[dict]:
    """One full accommodations call (we need the result objects, not the
    aggregates stay22.get_stay() returns)."""
    params: dict[str, object] = {
        "address": query,
        "checkin": checkin,
        "checkout": checkout,
        "adults": max(1, guests),
        "rooms": max(1, guests // 2 or 1),
        "currency": "USD",
        "pageSize": 30,
        "page": 1,
    }
    aid = os.environ.get("STAY22_AID", "").strip()
    if aid:
        params["aid"] = aid
        params["campaign"] = "trippet_cards"

    stay22._throttle()  # shared 12s keyless-tier budget
    url = f"{stay22.ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "trippet/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        log.warning("stay22 fetch failed: %s: %s", type(e).__name__, e)
        return None


def _normalize(raw: dict) -> list[dict]:
    """Stay22 result objects → flat card dicts. Drops anything without a
    photo, a price, and a rating — cards must be swipeable at a glance."""
    meta = raw.get("meta") or {}
    nights = int(meta.get("nights") or 2)
    cards: list[dict] = []
    seen_names: set[str] = set()

    for r in raw.get("results") or []:
        price = None
        link = None
        for s in (r.get("suppliers") or {}).values():
            p = (s.get("price") or {}).get("total")
            if p:
                price = float(p)
                link = s.get("link") or r.get("url")
                break
        thumb = (r.get("media") or {}).get("thumbnail")
        rating = (r.get("rating") or {})
        name = (r.get("name") or "").strip()
        if not (price and thumb and name and rating.get("value")):
            continue
        if name.lower() in seen_names:
            continue
        seen_names.add(name.lower())

        loc = r.get("location") or {}
        cap = r.get("capacity") or {}
        pol = r.get("policies") or {}
        cards.append({
            "id": str(r.get("id")),
            "name": name,
            "type": r.get("type") or "Hotel",
            "price_total": round(price),
            "nights": nights,
            "price_per_night": round(price / max(1, nights)),
            "rating": rating.get("value"),
            "rating_count": rating.get("count") or 0,
            "stars": rating.get("hotelStars"),
            "guests": cap.get("guests"),
            "beds": cap.get("beds"),
            "free_cancellation": bool(pol.get("freeCancellation")),
            "address": loc.get("address") or "",
            "lat": (loc.get("coordinates") or {}).get("lat"),
            "lng": (loc.get("coordinates") or {}).get("lng"),
            "thumbnail": thumb,
            "url": link or r.get("url"),
        })
    return cards


def _pick_deck(cards: list[dict], n: int) -> list[dict]:
    """Top-rated first, but spread the price range so the group has a real
    decision to make (cheapest + priciest of the well-rated set both appear).
    Listings with a lone review or absurd price outliers don't make the deck."""
    trusted = [c for c in cards if (c["rating_count"] or 0) >= 2] or cards
    prices = sorted(c["price_total"] for c in trusted)
    median_price = prices[len(prices) // 2] if prices else 0
    sane = [c for c in trusted if c["price_total"] <= median_price * 2.5] or trusted
    pool = sorted(sane, key=lambda c: (-(c["rating"] or 0), c["price_total"]))[: n * 3]
    if len(pool) <= n:
        return pool
    pool_by_price = sorted(pool, key=lambda c: c["price_total"])
    picked = {pool_by_price[0]["id"], pool_by_price[-1]["id"]}
    deck = [c for c in pool if c["id"] in picked]
    for c in pool:  # fill the rest by rating
        if len(deck) >= n:
            break
        if c["id"] not in picked:
            deck.append(c)
            picked.add(c["id"])
    deck.sort(key=lambda c: c["price_total"])
    return deck


def fetch_hotel_cards(max_cards: int = 5, guests: int = 4,
                      checkin: Optional[str] = None,
                      checkout: Optional[str] = None) -> dict:
    """→ {basecamp, checkin, checkout, source, cards:[...max 5]}. Never raises;
    always returns a playable deck via the fallback chain."""
    ci, co = (checkin, checkout) if (checkin and checkout) else default_dates()

    raw = _fetch_raw(BASECAMP_QUERY, ci, co, guests)
    source = "stay22_live"
    cards = _normalize(raw) if raw else []

    if len(cards) < max_cards and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            cards = _normalize(cached)
            source = "cache"
        except (json.JSONDecodeError, OSError) as e:
            log.warning("cache read failed: %s", e)
    if len(cards) < 1 and LEGACY_SAMPLE.exists():
        cards = _normalize(json.loads(LEGACY_SAMPLE.read_text(encoding="utf-8")))
        source = "sample"

    deck = _pick_deck(cards, max_cards)
    log.info("hotel deck ready: %d cards (source=%s)", len(deck), source)
    return {"basecamp": BASECAMP_NAME, "checkin": ci, "checkout": co,
            "source": source, "cards": deck}


def refresh_cache() -> bool:
    """Grab a live response and persist it as the committed fallback."""
    ci, co = default_dates()
    raw = _fetch_raw(BASECAMP_QUERY, ci, co, guests=4)
    if not raw or not _normalize(raw):
        return False
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ok = refresh_cache()
    print(f"cache refresh: {'ok' if ok else 'FAILED'}")
    deck = fetch_hotel_cards()
    print(json.dumps(deck, indent=2, ensure_ascii=False))
