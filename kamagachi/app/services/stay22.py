"""Stay22 client. Load-bearing across the whole product.

Endpoints (per https://dev.stay22.com/docs):
  - Inventory search: GET https://api.stay22.com/v2/accommodations
  - Allez redirect:   https://www.stay22.com/allez/{provider}?aid=&link=
  - Reporting:        GET https://api.stay22.com/v1/reporting/transactions

Auth: X-API-KEY header (100 req/min). Allez uses `aid` query param only.

If STAY22_API_KEY is missing we serve seeded demo data so the app still boots
and the demo path (deck → swipe → match → Allez) is walkable.
"""
from __future__ import annotations
import hashlib
import random
from typing import Any, Optional
from urllib.parse import urlencode, quote

import httpx

from ..config import STAY22_API_KEY, STAY22_AFFILIATE_ID
from ..models.schemas import DeckHotel


API_BASE = "https://api.stay22.com"
ALLEZ_BASE = "https://www.stay22.com/allez"


class Stay22Client:
    def __init__(self, api_key: str = STAY22_API_KEY, aid: str = STAY22_AFFILIATE_ID) -> None:
        self.api_key = api_key
        self.aid = aid
        self._client: Optional[httpx.AsyncClient] = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["X-API-KEY"] = self.api_key
            self._client = httpx.AsyncClient(base_url=API_BASE, headers=headers, timeout=15.0)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    # ─── Inventory ───────────────────────────────────────────────────────────
    async def search(
        self,
        address: str,
        checkin: Optional[str] = None,
        checkout: Optional[str] = None,
        adults: int = 2,
        rooms: int = 1,
        max_price: Optional[float] = None,
        page_size: int = 30,
        campaign: str = "kamagachi",
    ) -> list[DeckHotel]:
        """Return up to `page_size` DeckHotel objects for a city + date window."""
        if not self.api_key:
            return _seed_deck(address, page_size)

        params: dict[str, Any] = {
            "address": address, "adults": adults, "rooms": rooms,
            "pageSize": page_size, "aid": self.aid, "campaign": campaign,
        }
        if checkin: params["checkin"] = checkin
        if checkout: params["checkout"] = checkout
        if max_price and checkin and checkout:
            params["max"] = int(max_price)

        try:
            http = await self._http()
            resp = await http.get("/v2/accommodations", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[stay22] search failed for {address} ({e}); using seeded fallback")
            return _seed_deck(address, page_size)

        out: list[DeckHotel] = []
        for r in data.get("results", []):
            supplier = _pick_supplier(r.get("suppliers") or {})
            price = _price_from_supplier(supplier)
            base_url = r.get("url") or (supplier or {}).get("link") or ""
            out.append(DeckHotel(
                hotel_id=str(r.get("id") or ""),
                city=address.split(",")[0].strip(),
                name=r.get("name") or "Hotel",
                image_url=(r.get("media") or {}).get("thumbnail") or "",
                base_url=base_url,
                price_per_night=price,
                rating=float((r.get("rating") or {}).get("value") or 0.0),
                tags=_tags_from_result(r),
                custom_metadata={"suppliers": list((r.get("suppliers") or {}).keys())},
            ))
        return out or _seed_deck(address, page_size)

    # ─── Allez monetized link ────────────────────────────────────────────────
    def allez_url(
        self,
        provider: str = "roam",
        link: Optional[str] = None,
        address: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        checkin: Optional[str] = None,
        checkout: Optional[str] = None,
        adults: int = 2,
        campaign: str = "kamagachi_launch",
    ) -> str:
        params: dict[str, Any] = {"aid": self.aid, "campaign": campaign, "adults": adults}
        if link:    params["link"] = link
        elif lat is not None and lng is not None:
            params["lat"] = lat; params["lng"] = lng
        elif address:
            params["address"] = address
        if checkin: params["checkin"] = checkin
        if checkout: params["checkout"] = checkout
        return f"{ALLEZ_BASE}/{provider}?{urlencode(params)}"

    # ─── Reporting / conversion polling ──────────────────────────────────────
    async def bookings_count(
        self, third_party: str, campaign: Optional[str] = None,
        start_date: Optional[str] = None, end_date: Optional[str] = None,
    ) -> int:
        """Poll transactions endpoint. Returns count of matching bookings.
        Requires `thirdParty` — Stay22 tells you what to pass for your account.
        For the demo we count anything with a matching `campaign`.
        """
        if not self.api_key:
            return 0
        try:
            http = await self._http()
            params: dict[str, Any] = {"thirdParty": third_party, "format": "json", "limit": 500}
            if start_date: params["startDate"] = start_date
            if end_date: params["endDate"] = end_date
            resp = await http.get("/v1/reporting/transactions", params=params)
            resp.raise_for_status()
            rows = resp.json().get("data") or []
            if campaign:
                rows = [r for r in rows if campaign in (r.get("campaignIds") or [r.get("campaignId")])]
            return len(rows)
        except Exception as e:
            print(f"[stay22] reporting failed ({e})")
            return 0

    # ─── Market snapshot (feeds health decay) ────────────────────────────────
    async def market_snapshot(self, address: str, checkin: str, checkout: str) -> tuple[float, float]:
        """Return (avg_nightly_price_usd, availability_pct 0-100) for a city window.
        Availability is approximated by (results_count / requested_page_size * 100).
        """
        if not self.api_key:
            # Deterministic wobble around a seed baseline so the demo shows movement.
            seed = int(hashlib.md5(f"{address}{checkin}".encode()).hexdigest(), 16)
            rng = random.Random(seed ^ random.randint(0, 10_000))
            return (200 + rng.uniform(-20, 40), 95 - rng.uniform(0, 30))

        try:
            http = await self._http()
            params = {
                "address": address, "checkin": checkin, "checkout": checkout,
                "adults": 2, "pageSize": 30, "aid": self.aid,
            }
            resp = await http.get("/v2/accommodations", params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            prices: list[float] = []
            for r in results:
                for s in (r.get("suppliers") or {}).values():
                    p = _price_from_supplier(s)
                    if p:
                        prices.append(p)
                        break
            avg = (sum(prices) / len(prices)) if prices else 0.0
            total = (data.get("meta") or {}).get("total") or len(results)
            avail = min(100.0, (len(results) / 30.0) * 100.0)
            return (avg, avail)
        except Exception as e:
            print(f"[stay22] market_snapshot failed for {address} ({e})")
            return (0.0, 0.0)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _pick_supplier(suppliers: dict[str, Any]) -> Optional[dict[str, Any]]:
    for key in ("booking", "expedia", "hotelscom", "vrbo"):
        if suppliers.get(key):
            return suppliers[key]
    return next(iter(suppliers.values()), None)


def _price_from_supplier(s: Any) -> float:
    if not s:
        return 0.0
    price = (s.get("price") or {})
    total = price.get("total") or price.get("perNight") or 0
    return float(total or 0)


def _tags_from_result(r: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    rating = (r.get("rating") or {})
    if rating.get("hotelStars"):
        tags.append(f"{int(rating['hotelStars'])}★")
    if (r.get("policies") or {}).get("freeCancellation"):
        tags.append("Free cancellation")
    if (r.get("policies") or {}).get("instantBook"):
        tags.append("Instant book")
    t = r.get("type")
    if t:
        tags.append(str(t).replace("_", " ").title())
    return tags[:3]


# ─── Seeded demo inventory (no API key) ──────────────────────────────────────
_SEED_NAMES = [
    "Park Hyatt", "Hoshinoya", "The Ritz-Carlton", "Aman", "Andaz",
    "Conrad", "Four Seasons", "Palace Hotel", "Grand Hyatt", "Hyatt Regency",
    "Cerulean Tower", "Keio Plaza", "Century Southern Tower", "Shibuya Excel",
    "Sunroute Plaza", "Hotel Gracery", "The Peninsula", "Mandarin Oriental",
    "Nikko Style", "Toyoko Inn", "Sotetsu Fresa", "Muji Hotel", "Trunk House",
    "Nohga Hotel", "Kimpton Shinjuku", "Book and Bed", "Onyado Nono",
    "Hilton Tokyo", "The Prince Park Tower", "Sunroute Ariake",
]

_SEED_TAGS = [
    ["Skyline", "Iconic"], ["Onsen", "Ryokan"], ["Rooftop bar", "Central"],
    ["Design-forward"], ["Family-friendly", "Kitchenette"], ["Boutique"],
    ["Near station"], ["Views"], ["Business"], ["Sento nearby"],
]


def _seed_deck(address: str, n: int) -> list[DeckHotel]:
    city = address.split(",")[0].strip()
    seed = int(hashlib.md5(city.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    hotels: list[DeckHotel] = []
    for i in range(n):
        name = f"{rng.choice(_SEED_NAMES)} {city}"
        hid = f"seed-{city.lower()}-{i}"
        hotels.append(DeckHotel(
            hotel_id=hid, city=city, name=name,
            image_url=f"https://picsum.photos/seed/{hid}/800/600",
            base_url=f"https://www.booking.com/searchresults.html?ss={quote(city)}",
            price_per_night=round(rng.uniform(90, 550), 0),
            rating=round(rng.uniform(3.6, 4.9), 1),
            tags=rng.choice(_SEED_TAGS),
        ))
    return hotels


# module-level singleton
stay22 = Stay22Client()
