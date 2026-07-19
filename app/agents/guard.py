"""Outgoing-message guard — the pet cannot propose a destination off-script.

WHY THIS EXISTS
The messenger prompt now states the destination country up front, but a prompt
is a request, not a guarantee: a model under pressure to "propose a default"
will still occasionally reach for the most available city in its head. It did,
live, on a group literally named "Japannnnn":

    "due to applicant silence, default destination is now chicago."

That isn't only embarrassing. stay22.CITY_COORDS, green.CITY_AIRPORT and the
fixed basecamp are all Japan-only, so an off-country city that reaches the
group is a promise the rest of the system cannot keep.

THE DISTINCTION THAT MATTERS
Naming a foreign city is not itself wrong. This was a genuinely good message:

    "beijing is in china Lucas. since you are lost, i am choosing tokyo."

The pet is CORRECTING someone — that's exactly the behaviour we want, and a
blunt "no foreign city names ever" filter would have destroyed it. So the guard
targets the specific failure: presenting an off-country city as where the group
is going. Correction and refusal are allowed; endorsement is not.

HOW IT'S USED
messenger() already generates several candidates and ranks them, so the guard
filters that pool before ranking — a violating candidate is simply never
eligible. _gate() then re-checks whatever finally won, covering lines that
never came from the candidate pool (canned fallbacks, hardcoded beats). Failing
closed there means silence, which is always safer than a wrong promise.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("trippet.guard")

TRIP_COUNTRY = os.environ.get("TRIP_COUNTRY", "Japan")

# Cities and countries a model reaches for when it wants "a destination". Not
# exhaustive and doesn't need to be — it covers the high-frequency defaults,
# and anything missed still faces the prompt-level instruction.
_OFF_PLACES = [
    # North America
    "chicago", "new york", "nyc", "los angeles", "san francisco", "miami",
    "las vegas", "vegas", "toronto", "vancouver", "montreal", "boston",
    "seattle", "austin", "denver", "mexico city", "cancun", "honolulu",
    # Europe
    "paris", "london", "rome", "milan", "barcelona", "madrid", "lisbon",
    "amsterdam", "berlin", "munich", "prague", "vienna", "budapest",
    "athens", "dublin", "copenhagen", "stockholm", "oslo", "zurich",
    "venice", "florence", "santorini", "reykjavik", "istanbul",
    # Asia-Pacific (the near-misses that matter most for a Japan trip)
    "beijing", "shanghai", "hong kong", "taipei", "seoul", "busan",
    "bangkok", "phuket", "singapore", "kuala lumpur", "bali", "jakarta",
    "manila", "hanoi", "ho chi minh", "saigon", "delhi", "mumbai", "goa",
    "sydney", "melbourne", "auckland", "queenstown",
    # Elsewhere
    "dubai", "abu dhabi", "doha", "cairo", "marrakech", "cape town",
    "rio de janeiro", "buenos aires", "lima", "bogota",
    # Countries — "let's do thailand" is the same failure as a city
    "china", "korea", "south korea", "thailand", "vietnam", "taiwan",
    "singapore", "indonesia", "philippines", "india", "france", "italy",
    "spain", "germany", "greece", "portugal", "iceland", "australia",
    "new zealand", "brazil", "mexico", "canada", "usa", "america",
]

_OFF_RE = re.compile(r"\b(" + "|".join(re.escape(p) for p in _OFF_PLACES) + r")\b",
                     re.IGNORECASE)

# The pet saying a foreign place is NOT where we're going. These are the good
# messages — corrections, jokes at someone's expense, explicit refusals.
_CORRECTION_RE = re.compile(
    r"is (not|n't) in \s*" + TRIP_COUNTRY                     # "beijing is not in japan"
    + r"|is in (china|korea|thailand|france|italy|the us|america|canada)"
    + r"|not\s+(going|flying|booking)\s+to"
    + r"|isn'?t\s+" + TRIP_COUNTRY
    + r"|nowhere near"
    + r"|wrong (country|continent)"
    + r"|we'?re going to " + TRIP_COUNTRY
    + r"|this is a " + TRIP_COUNTRY + r" trip",
    re.IGNORECASE)

# Language that presents a place as the plan rather than as a mistake.
_ENDORSE_RE = re.compile(
    r"\b(destination is|we'?re going to|let'?s go to|let'?s do|locking in"
    r"|lock in|i'?m choosing|i choose|default (destination|city)|booking"
    r"|book(ing)? us|penciled in|putting us down|going with|settled on"
    r"|new plan|switching to|instead we)\b",
    re.IGNORECASE)


def off_country_places(text: str) -> list[str]:
    """Every off-country place named in `text` (lowercased, deduped)."""
    return sorted({m.group(1).lower() for m in _OFF_RE.finditer(text or "")})


def violates_destination(text: str) -> tuple[bool, str]:
    """Does this message present somewhere outside TRIP_COUNTRY as the plan?

    Returns (violates, reason). The order of checks is the whole design:
      1. no off-country place at all      → fine, the common case
      2. it reads as a correction/refusal → fine, this is desired behaviour
      3. it reads as an endorsement       → BLOCK, this is the Chicago failure
      4. named but ambiguous              → BLOCK, because on a trip whose every
         downstream component is TRIP_COUNTRY-only, an unexplained foreign city
         has no good reading. Failing closed costs one candidate; failing open
         costs a promise the system can't keep.
    """
    t = text or ""
    places = off_country_places(t)
    if not places:
        return False, ""
    if _CORRECTION_RE.search(t):
        return False, f"correction mentioning {places}"
    if _ENDORSE_RE.search(t):
        return True, f"endorses off-country destination: {places}"
    return True, f"names off-country place with no correction: {places}"


def safe(text: str) -> bool:
    return not violates_destination(text)[0]
