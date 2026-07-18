"""Standalone chat-to-constraints module.

Not wired into the bot. `call_model()` is the ONE place the LLM is called —
swap it for Freesolo later without touching extract/aggregate.

Usage:
    GEMINI_API_KEY=xxx python brain.py

Get a free Gemini key: https://aistudio.google.com/apikey

If the key is missing the script still runs and reconciles hand-coded
fixture extractions so you can see the aggregation rules work.
"""
from __future__ import annotations
import json
import os
from collections import Counter
from datetime import date
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ─── ONE place the model is called — Gemini only, permanently ───────────────
# Per PIPELINE.md: Read seam = Gemini. Freesolo lives on the Agent seam in
# phoebe.py. Do NOT re-add Freesolo here. Cross-wiring is exactly the
# foot-gun PIPELINE.md exists to prevent.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp")


def call_model(prompt: str) -> str:
    """The only place we hit a model for the Read layer. Returns raw JSON string."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/apikey. "
            "The Read seam is Gemini only — see PIPELINE.md."
        )
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    resp = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"},
    )
    return resp.text


# ─── Prompt ─────────────────────────────────────────────────────────────────
_EXTRACT_PROMPT = """You extract trip-planning constraints from a group chat.

Return ONLY valid JSON matching this EXACT shape (all top-level keys required,
even if their values are null / empty):

{
  "city": <string or null>,
  "dates": {"start": "YYYY-MM-DD or null", "end": "YYYY-MM-DD or null"},
  "budget_per_person": <int USD or null>,
  "group_size": <int or null>,
  "vibe": [<string>, ...],
  "per_person": {
    "<sender_name>": {
      "budget": <int USD or null>,
      "dates": {"start": "YYYY-MM-DD or null", "end": "YYYY-MM-DD or null"},
      "city": <string or null>,
      "vibe": [<string>, ...]
    }
  },
  "confidence": {"city": <0..1>, "dates": <0..1>, "budget": <0..1>, "group_size": <0..1>}
}

RULES:
- The trip is to Japan. Cities are typically Tokyo, Kyoto, Osaka, Nara,
  Sapporo, Fukuoka, Okinawa, Hokkaido, etc.
- IGNORE off-topic chatter (cats, memes, "lol", TV shows). Non-trip
  messages contribute nothing. This is a privacy filter.
- Extract each speaker's own stated preferences into `per_person`. Do NOT
  guess for people who didn't say anything specific.
- Dates: parse phrases like "second week of April", "late May", "first
  week of June" into concrete YYYY-MM-DD ranges. Assume the current or
  upcoming year unless stated. If someone says "May works", set them to
  the full month of May.
- Budgets: parse "$1500", "1.5k", "2000 max", "under 2k" as int USD.
- Top-level `city`/`dates`/`budget_per_person`/`group_size`/`vibe`:
  fill ONLY if the group has clear consensus. If people disagree, leave
  the top-level null and let `per_person` carry the disagreement — the
  aggregate step will reconcile with explicit rules.
- `group_size`: count distinct speakers who spoke about the trip.
- `confidence`: per-field 0..1. 0.9+ if unanimous, 0.6-0.8 if mostly
  aligned, <0.5 if conflicting or absent.

TRANSCRIPT:
"""


# ─── extract ────────────────────────────────────────────────────────────────
def extract(messages: list[dict]) -> dict:
    """Chat messages → structured trip extraction."""
    convo = "\n".join(f"{m['sender']}: {m['text']}" for m in messages)
    raw = call_model(_EXTRACT_PROMPT + convo)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"model returned non-JSON: {e}\n---\n{raw}") from e
    return _normalize(data)


def _normalize(d: dict) -> dict:
    """Fill missing keys with defaults so downstream code never KeyErrors."""
    return {
        "city": d.get("city"),
        "dates": d.get("dates") or {"start": None, "end": None},
        "budget_per_person": d.get("budget_per_person"),
        "group_size": d.get("group_size"),
        "vibe": d.get("vibe") or [],
        "per_person": d.get("per_person") or {},
        "confidence": d.get("confidence") or {},
    }


# ─── Aggregation rules ─ each rule is small, named, and reads like English ─
def _parse_date(s: str) -> Optional[date]:
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def rule_budget_lowest(per_person: dict) -> tuple[Optional[int], str]:
    """Budget = the lowest stated per-person cap. Nobody gets priced out."""
    stated = [(name, p["budget"]) for name, p in per_person.items() if p.get("budget") is not None]
    if not stated:
        return None, "no budget stated by anyone"
    stated.sort(key=lambda x: x[1])
    lo_name, lo = stated[0]
    if len(stated) == 1:
        return lo, f"only {lo_name} stated (${lo})"
    others = ", ".join(f"{n}:${a}" for n, a in stated[1:])
    return lo, f"floor ${lo} from {lo_name}; others {others}"


def rule_dates_intersection(per_person: dict) -> tuple[dict, str]:
    """Dates = intersection of everyone's stated windows. No overlap → null."""
    windows = []
    for name, p in per_person.items():
        d = p.get("dates") or {}
        s, e = _parse_date(d.get("start")), _parse_date(d.get("end"))
        if s and e and s <= e:
            windows.append((name, s, e))
    if not windows:
        return {"start": None, "end": None}, "no date windows stated"
    max_start = max(w[1] for w in windows)
    min_end   = min(w[2] for w in windows)
    if max_start > min_end:
        detail = ", ".join(f"{n}:{s}→{e}" for n, s, e in windows)
        return {"start": None, "end": None}, f"no overlap ({detail})"
    return (
        {"start": max_start.isoformat(), "end": min_end.isoformat()},
        f"intersection of {len(windows)} windows",
    )


def rule_city_majority(per_person: dict) -> tuple[Optional[str], str]:
    """City = plurality vote. Ties are flagged and left null."""
    votes = [p["city"].strip().title() for p in per_person.values() if p.get("city")]
    if not votes:
        return None, "no city stated"
    counts = Counter(votes)
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        tied = [c for c, n in top if n == top[0][1]]
        return None, f"TIE between {', '.join(tied)} ({top[0][1]} votes each)"
    winner, n = top[0]
    return winner, f"{n}/{sum(counts.values())} chose {winner}"


def rule_group_size_distinct_speakers(per_person: dict, fallback: Optional[int]) -> tuple[int, str]:
    """Group size = distinct people who spoke about the trip. Fallback to model's guess."""
    n = len(per_person)
    if n > 0:
        return n, f"{n} distinct speakers about the trip"
    if fallback is not None:
        return fallback, "no per_person data — using model's group_size guess"
    return 0, "unknown"


def rule_vibe_union(extraction: dict) -> tuple[list[str], str]:
    """Vibe = union of all mentioned tags."""
    tags: set[str] = set(extraction.get("vibe") or [])
    for p in (extraction.get("per_person") or {}).values():
        for v in (p.get("vibe") or []):
            tags.add(v)
    return sorted(tags), f"{len(tags)} unique tag(s) across all speakers"


# ─── aggregate ──────────────────────────────────────────────────────────────
def aggregate(extraction: dict) -> dict:
    """Apply the rules to reconcile the top-level fields from per_person data."""
    pp = extraction.get("per_person") or {}
    city, city_note = rule_city_majority(pp)
    dates, dates_note = rule_dates_intersection(pp)
    budget, budget_note = rule_budget_lowest(pp)
    group_size, group_note = rule_group_size_distinct_speakers(pp, extraction.get("group_size"))
    vibe, vibe_note = rule_vibe_union(extraction)
    return {
        "city": city,
        "dates": dates,
        "budget_per_person": budget,
        "group_size": group_size,
        "vibe": vibe,
        "per_person": pp,
        "confidence": extraction.get("confidence") or {},
        "notes": {
            "city": city_note,
            "dates": dates_note,
            "budget": budget_note,
            "group_size": group_note,
            "vibe": vibe_note,
        },
    }


# ─── Sample transcripts ─────────────────────────────────────────────────────
SAMPLES: dict[str, list[dict]] = {
    "sample_1_budget_conflict": [
        {"sender": "alice", "text": "yo japan when"},
        {"sender": "bob",   "text": "down for tokyo probably"},
        {"sender": "carla", "text": "i can do $1500 max"},
        {"sender": "dave",  "text": "yeah tokyo, i'm broke, $800 or nothing"},
        {"sender": "alice", "text": "second week of april works for me"},
        {"sender": "bob",   "text": "april is fine, tokyo"},
        {"sender": "carla", "text": "same, tokyo, second week of april"},
    ],
    "sample_2_city_split": [
        {"sender": "alice", "text": "japan trip finally"},
        {"sender": "bob",   "text": "kyoto or bust"},
        {"sender": "carla", "text": "i'd rather do tokyo tbh"},
        {"sender": "dave",  "text": "kyoto for me"},
        {"sender": "alice", "text": "i'm team tokyo"},
        {"sender": "bob",   "text": "ugh fine let's argue"},
        {"sender": "carla", "text": "budget ~$2000 tho"},
        {"sender": "alice", "text": "i can do 2k, first week of may"},
        {"sender": "dave",  "text": "may works, $2200 max"},
    ],
    "sample_3_vague_dates_offtopic": [
        {"sender": "alice", "text": "japan?"},
        {"sender": "bob",   "text": "oh totally, may works, tokyo"},
        {"sender": "carla", "text": "haha my cat is being weird"},
        {"sender": "dave",  "text": "i can only go first week of june"},
        {"sender": "alice", "text": "hmm early may is out for me then"},
        {"sender": "bob",   "text": "late may early june tokyo works for me"},
        {"sender": "carla", "text": "btw did anyone watch the game"},
        {"sender": "alice", "text": "late may through early june works, tokyo yes"},
        {"sender": "carla", "text": "ok fine, tokyo, budget $1800, late may works"},
        {"sender": "dave",  "text": "$1800 fine, tokyo, first week of june"},
    ],
}

# Fallback fixtures so `aggregate` can be demoed when no key is set.
FIXTURE_EXTRACTIONS: dict[str, dict] = {
    "sample_1_budget_conflict": {
        "city": "Tokyo",
        "dates": {"start": "2027-04-12", "end": "2027-04-18"},
        "budget_per_person": None,
        "group_size": 4,
        "vibe": [],
        "per_person": {
            "alice": {"budget": None, "dates": {"start": "2027-04-12", "end": "2027-04-18"}, "city": "Tokyo", "vibe": []},
            "bob":   {"budget": None, "dates": {"start": "2027-04-01", "end": "2027-04-30"}, "city": "Tokyo", "vibe": []},
            "carla": {"budget": 1500, "dates": {"start": "2027-04-12", "end": "2027-04-18"}, "city": "Tokyo", "vibe": []},
            "dave":  {"budget": 800,  "dates": {"start": None, "end": None},                 "city": "Tokyo", "vibe": []},
        },
        "confidence": {"city": 0.95, "dates": 0.75, "budget": 0.6, "group_size": 0.9},
    },
    "sample_2_city_split": {
        "city": None,
        "dates": {"start": None, "end": None},
        "budget_per_person": None,
        "group_size": 4,
        "vibe": [],
        "per_person": {
            "alice": {"budget": 2000, "dates": {"start": "2027-05-01", "end": "2027-05-07"}, "city": "Tokyo", "vibe": []},
            "bob":   {"budget": None, "dates": {"start": None, "end": None},                 "city": "Kyoto", "vibe": []},
            "carla": {"budget": 2000, "dates": {"start": None, "end": None},                 "city": "Tokyo", "vibe": []},
            "dave":  {"budget": 2200, "dates": {"start": "2027-05-01", "end": "2027-05-31"}, "city": "Kyoto", "vibe": []},
        },
        "confidence": {"city": 0.35, "dates": 0.6, "budget": 0.8, "group_size": 0.9},
    },
    "sample_3_vague_dates_offtopic": {
        "city": "Tokyo",
        "dates": {"start": None, "end": None},
        "budget_per_person": 1800,
        "group_size": 4,
        "vibe": [],
        "per_person": {
            "alice": {"budget": None, "dates": {"start": "2027-05-25", "end": "2027-06-07"}, "city": "Tokyo", "vibe": []},
            "bob":   {"budget": None, "dates": {"start": "2027-05-25", "end": "2027-06-07"}, "city": "Tokyo", "vibe": []},
            "carla": {"budget": 1800, "dates": {"start": "2027-05-25", "end": "2027-05-31"}, "city": "Tokyo", "vibe": []},
            "dave":  {"budget": 1800, "dates": {"start": "2027-06-01", "end": "2027-06-07"}, "city": "Tokyo", "vibe": []},
        },
        "confidence": {"city": 0.95, "dates": 0.7, "budget": 0.85, "group_size": 0.9},
    },
}


# ─── main ──────────────────────────────────────────────────────────────────
def _print_result(name: str, extraction: dict, reconciled: dict) -> None:
    print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
    print("--- extract() ---")
    print(json.dumps(extraction, indent=2, ensure_ascii=False))
    print("--- aggregate() ---")
    print(json.dumps(reconciled, indent=2, ensure_ascii=False))


def main() -> None:
    have_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    if not have_key:
        print("⚠  GEMINI_API_KEY not set — using FIXTURE_EXTRACTIONS so you can")
        print("   still see aggregate() rules work. Get a free key at:")
        print("   https://aistudio.google.com/apikey\n")
        for name, transcript in SAMPLES.items():
            fixture = FIXTURE_EXTRACTIONS[name]
            _print_result(f"{name} (FIXTURE)", fixture, aggregate(fixture))
        return

    for name, transcript in SAMPLES.items():
        try:
            e = extract(transcript)
            r = aggregate(e)
            _print_result(name, e, r)
        except Exception as ex:
            print(f"\n✗ {name} failed: {type(ex).__name__}: {ex}")


if __name__ == "__main__":
    main()
