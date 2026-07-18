"""Consensus pipeline. Reconciles chaotic multi-person chat into ONE TripState.

Primary path: Gemini structured JSON extraction.
Fallback path: rule-based (regex + keyword) so the demo runs without a Gemini key.

Both paths produce the same shape: partial updates to TripState fields, applied
by `merge_updates()` and then healed by `services.health.reconcile_and_heal`.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from ..config import GEMINI_API_KEY, GEMINI_MODEL
from ..models.schemas import TripState, ItineraryLeg


# ─── Known-city dictionary (rule fallback) ───────────────────────────────────
JAPAN_CITIES = {
    "tokyo": "Tokyo", "kyoto": "Kyoto", "osaka": "Osaka", "nara": "Nara",
    "hokkaido": "Hokkaido", "sapporo": "Sapporo", "okinawa": "Okinawa",
    "hakone": "Hakone", "hiroshima": "Hiroshima", "kanazawa": "Kanazawa",
    "nagoya": "Nagoya", "fukuoka": "Fukuoka", "yokohama": "Yokohama",
    "kobe": "Kobe", "sendai": "Sendai", "takayama": "Takayama",
}


# ─── Rule-based extraction (fast fallback) ───────────────────────────────────
def _extract_budget(text: str) -> Optional[int]:
    m = re.search(r"\$\s?(\d{2,5})(?:\s?-\s?(\d{2,5}))?", text)
    if not m:
        m = re.search(r"(\d{3,5})\s?(?:usd|dollars|bucks)\b", text, re.I)
        return int(m.group(1)) if m else None
    lo, hi = m.group(1), m.group(2)
    return int(hi or lo)


def _extract_group_size(text: str) -> Optional[int]:
    m = re.search(r"\b(?:group of|we're|were|there(?:'|)s)\s+(\d{1,2})\b", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,2})\s+(?:people|of us|friends|ppl)\b", text, re.I)
    return int(m.group(1)) if m else None


def _extract_cities(text: str) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for key, name in JAPAN_CITIES.items():
        if re.search(rf"\b{key}\b", lower) and name not in found:
            found.append(name)
    return found


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _extract_month_windows(text: str) -> list[tuple[int, str]]:
    """Return list of (month_number, qualifier) e.g. (5, 'second week')."""
    out: list[tuple[int, str]] = []
    for m in re.finditer(
        r"\b(first|second|third|fourth|last|early|mid|late)?\s*(?:week\s*(?:of\s*)?)?"
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?\b",
        text, re.I,
    ):
        qual = (m.group(1) or "mid").lower()
        month = _MONTHS[m.group(2).lower()[:4] if m.group(2).lower().startswith("sept") else m.group(2).lower()[:3]]
        out.append((month, qual))
    return out


def _qualifier_to_day(qual: str) -> int:
    return {
        "first": 3, "second": 10, "third": 17, "fourth": 24,
        "last": 25, "early": 3, "mid": 14, "late": 24,
    }.get(qual, 14)


def rule_based_extract(recent_text: str) -> dict[str, Any]:
    """Best-effort structured extraction from concatenated chat text."""
    budget = _extract_budget(recent_text)
    size = _extract_group_size(recent_text)
    cities = _extract_cities(recent_text)
    months = _extract_month_windows(recent_text)
    year = datetime.now(timezone.utc).year

    itinerary: list[dict[str, Any]] = []
    for i, city in enumerate(cities):
        leg: dict[str, Any] = {"city": city}
        if i < len(months):
            month, qual = months[i]
            day = _qualifier_to_day(qual)
            leg["arrival_date"] = datetime(year, month, day, tzinfo=timezone.utc).isoformat()
            # default 4-night stay per city
            arrival = datetime(year, month, day, tzinfo=timezone.utc)
            departure_day = min(day + 4, 28)
            leg["departure_date"] = datetime(year, month, departure_day, tzinfo=timezone.utc).isoformat()
        itinerary.append(leg)

    return {
        "max_budget": budget,
        "group_size": size,
        "itinerary": itinerary,
    }


# ─── Gemini extraction (primary path) ────────────────────────────────────────
_GEMINI_SYSTEM = """You are the consensus engine for Kamagachi — a group-travel bot.
Multiple people are messaging in a Telegram group about planning a trip to Japan.
They will contradict each other, change their minds, and be vague.

Your job: read the recent messages and return ONE reconciled trip plan as JSON.
When people disagree, prefer the MOST RECENT firm statement. When someone says
"maybe" or "idk", treat it as a soft signal, not a commit. Prefer explicit
commitments ("I'm in for $1500", "May works for me") over speculation.

Return ONLY valid JSON with this exact shape:
{
  "max_budget": <int or null>,        // USD per person, upper bound of the group's ceiling
  "group_size": <int or null>,        // total people going
  "itinerary": [                       // sequential cities the group agrees on
    {
      "city": "<string>",
      "arrival_date": "<ISO 8601 datetime or null>",
      "departure_date": "<ISO 8601 datetime or null>"
    }
  ]
}
Do not include prose. Do not include null for fields you can't infer — omit them from itinerary items but keep the keys `max_budget` and `group_size` (use null).
"""


async def gemini_extract(recent_text: str) -> Optional[dict[str, Any]]:
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=_GEMINI_SYSTEM)
        resp = await model.generate_content_async(
            recent_text,
            generation_config={"response_mime_type": "application/json"},
        )
        return json.loads(resp.text)
    except Exception as e:
        print(f"[consensus] gemini failed ({e}); falling back to rules")
        return None


# ─── Merge partial updates into TripState ────────────────────────────────────
def merge_updates(current: TripState, updates: dict[str, Any]) -> TripState:
    data = current.model_dump()
    if updates.get("max_budget") is not None:
        data["max_budget"] = updates["max_budget"]
    if updates.get("group_size") is not None:
        data["group_size"] = updates["group_size"]

    incoming_legs = updates.get("itinerary") or []
    if incoming_legs:
        merged: list[ItineraryLeg] = []
        for raw in incoming_legs:
            leg = ItineraryLeg(
                city=raw["city"],
                arrival_date=_parse_iso(raw.get("arrival_date")),
                departure_date=_parse_iso(raw.get("departure_date")),
            )
            merged.append(leg)
        # dedupe by city preserving order
        seen: set[str] = set()
        dedup: list[ItineraryLeg] = []
        for l in merged:
            if l.city not in seen:
                dedup.append(l)
                seen.add(l.city)
        data["itinerary"] = [l.model_dump() for l in dedup]

    return TripState(**data)


def _parse_iso(s: Any) -> Optional[datetime]:
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


# ─── Public entry point ──────────────────────────────────────────────────────
async def extract_and_merge(current: TripState, recent_text: str) -> TripState:
    """Run Gemini → fallback to rules → merge into a new TripState."""
    updates = await gemini_extract(recent_text)
    if updates is None:
        updates = rule_based_extract(recent_text)
    return merge_updates(current, updates)
