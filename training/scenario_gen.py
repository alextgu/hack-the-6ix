"""Generate diverse friend-group trip scenarios with GROUND-TRUTH labels.

Ground truth = whatever the production `phoebe.diagnose` + `phoebe.decide_action`
say. Never regressing on the app's actual logic; the trained model has to at
least match production, then GRPO pushes past it.

  python -m training.scenario_gen --n 800 --out training/dataset/scenarios.jsonl

Dedup: sha256 of the input state dict (canonical JSON). Decontamination between
train/eval is handled by gen_dataset.py before writing splits.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

# Import from the repo root — training/ is a subpackage.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import phoebe  # noqa: E402  — labels MUST come from production logic


JAPAN_CITIES = ["Tokyo", "Kyoto", "Osaka", "Nara", "Sapporo", "Fukuoka", "Hakone", "Kanazawa"]
NAMES = ["alice", "bob", "carla", "dave", "erin", "fatima", "greg", "hana"]
VIBES = ["food", "shrines", "shopping", "nightlife", "quiet", "budget", "luxury", "onsen"]

# 6-week-out window baseline, dates spread across a plausible planning horizon.
_YEAR = 2027


def _iso(m: int, d: int) -> str:
    return f"{_YEAR}-{m:02d}-{d:02d}"


def _canonical_hash(state: dict) -> str:
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


# ─── Scenario builders (one per blocker archetype) ─────────────────────────
def _pick_names(rng: random.Random, n: int) -> list[str]:
    return rng.sample(NAMES, n)


def _base_person(rng: random.Random,
                 budget: int | None = None,
                 city: str | None = None,
                 date_span: tuple[int, int, int, int] | None = None,
                 vibe: list[str] | None = None) -> dict:
    dates = {}
    if date_span:
        sm, sd, em, ed = date_span
        dates = {"start": _iso(sm, sd), "end": _iso(em, ed)}
    return {
        "budget": budget,
        "city": city,
        "dates": dates,
        "vibe": vibe or [],
    }


def gen_city_tie(rng: random.Random) -> dict:
    """2 cities each get exactly the same number of votes."""
    size = rng.choice([4, 4, 4, 6])
    names = _pick_names(rng, size)
    c1, c2 = rng.sample(JAPAN_CITIES, 2)
    half = size // 2
    per_person = {}
    for i, n in enumerate(names):
        city = c1 if i < half else c2
        per_person[n] = _base_person(
            rng, budget=rng.choice([None, 1500, 2000, 2500]),
            city=city,
            date_span=(5, rng.randint(1, 10), 5, rng.randint(11, 20)),
            vibe=rng.sample(VIBES, k=rng.randint(0, 2)),
        )
    return {
        "city": None,
        "dates": {"start": _iso(5, 5), "end": _iso(5, 12)},
        "budget_per_person": None,
        "group_size": size,
        "per_person": per_person,
        "blockers": [f"city_tie: TIE between {c1}, {c2} ({half} votes each)"],
        "notes": {"city": f"TIE between {c1}, {c2} ({half} votes each)"},
    }


def gen_date_no_overlap(rng: random.Random) -> dict:
    size = rng.randint(3, 5)
    names = _pick_names(rng, size)
    city = rng.choice(JAPAN_CITIES)
    # Split the group into two disjoint windows.
    per_person = {}
    for i, n in enumerate(names):
        if i % 2 == 0:
            span = (5, rng.randint(1, 10), 5, rng.randint(11, 18))
        else:
            span = (6, rng.randint(1, 10), 6, rng.randint(15, 25))
        per_person[n] = _base_person(
            rng, budget=rng.choice([None, 1500, 1800, 2000]),
            city=city, date_span=span,
            vibe=rng.sample(VIBES, k=rng.randint(0, 2)),
        )
    detail = ", ".join(
        f"{n}:{p['dates']['start']}→{p['dates']['end']}"
        for n, p in per_person.items()
    )
    return {
        "city": city,
        "dates": {"start": None, "end": None},
        "budget_per_person": 1800,
        "group_size": size,
        "per_person": per_person,
        "blockers": [f"date_no_overlap: no overlap ({detail})"],
        "notes": {"dates": "no overlap"},
    }


def gen_low_budget_person(rng: random.Random) -> dict:
    """One person is well below group median — rule.low_budget_person should fire."""
    size = rng.randint(3, 5)
    names = _pick_names(rng, size)
    city = rng.choice(JAPAN_CITIES)
    median_budget = rng.choice([1500, 2000, 2500])
    low_budget = int(median_budget * rng.uniform(0.30, 0.55))  # <70%
    per_person = {}
    span = (rng.choice([4, 5]), rng.randint(1, 10), rng.choice([4, 5]), rng.randint(11, 20))
    for i, n in enumerate(names):
        b = low_budget if i == 0 else median_budget + rng.randint(-100, 300)
        per_person[n] = _base_person(
            rng, budget=b, city=city, date_span=span,
            vibe=rng.sample(VIBES, k=rng.randint(0, 2)),
        )
    return {
        "city": city,
        "dates": {"start": _iso(span[0], span[1]), "end": _iso(span[2], span[3])},
        "budget_per_person": low_budget,
        "group_size": size,
        "per_person": per_person,
        "blockers": [],
    }


def gen_silent_person(rng: random.Random) -> dict:
    """One person spoke but stated nothing concrete."""
    size = rng.randint(3, 5)
    names = _pick_names(rng, size)
    city = rng.choice(JAPAN_CITIES)
    per_person = {}
    span = (rng.choice([4, 5]), rng.randint(1, 10), rng.choice([4, 5]), rng.randint(11, 20))
    for i, n in enumerate(names):
        if i == 0:
            per_person[n] = _base_person(rng)  # silent
        else:
            per_person[n] = _base_person(
                rng, budget=rng.choice([1500, 2000]), city=city, date_span=span,
                vibe=rng.sample(VIBES, k=rng.randint(0, 2)),
            )
    return {
        "city": city,
        "dates": {"start": _iso(span[0], span[1]), "end": _iso(span[2], span[3])},
        "budget_per_person": 1500,
        "group_size": size,
        "per_person": per_person,
        "blockers": [],
    }


def gen_budget_missing(rng: random.Random) -> dict:
    size = rng.randint(3, 5)
    names = _pick_names(rng, size)
    city = rng.choice(JAPAN_CITIES)
    per_person = {}
    span = (rng.choice([4, 5]), rng.randint(1, 10), rng.choice([4, 5]), rng.randint(11, 20))
    for n in names:
        per_person[n] = _base_person(
            rng, budget=None, city=city, date_span=span,
            vibe=rng.sample(VIBES, k=rng.randint(0, 2)),
        )
    return {
        "city": city,
        "dates": {"start": _iso(span[0], span[1]), "end": _iso(span[2], span[3])},
        "budget_per_person": None,
        "group_size": size,
        "per_person": per_person,
        "blockers": ["budget_missing: no budget stated"],
    }


def gen_healthy(rng: random.Random) -> dict:
    """Trip on track — no blocker should fire. Keeps the model calibrated on
    the 'nothing to do' case so it doesn't hallucinate work."""
    size = rng.randint(3, 5)
    names = _pick_names(rng, size)
    city = rng.choice(JAPAN_CITIES)
    per_person = {}
    span = (rng.choice([4, 5]), rng.randint(1, 10), rng.choice([4, 5]), rng.randint(11, 20))
    budget = rng.choice([1500, 2000, 2500])
    for n in names:
        per_person[n] = _base_person(
            rng, budget=budget + rng.randint(-100, 300),
            city=city, date_span=span,
            vibe=rng.sample(VIBES, k=rng.randint(1, 3)),
        )
    return {
        "city": city,
        "dates": {"start": _iso(span[0], span[1]), "end": _iso(span[2], span[3])},
        "budget_per_person": budget,
        "group_size": size,
        "per_person": per_person,
        "blockers": [],
    }


ARCHETYPES = {
    "city_tie":         gen_city_tie,
    "date_no_overlap":  gen_date_no_overlap,
    "low_budget":       gen_low_budget_person,
    "silent_person":    gen_silent_person,
    "budget_missing":   gen_budget_missing,
    "healthy":          gen_healthy,
}


# ─── Ground-truth labelling (imports production Phoebe) ────────────────────
def label(state: dict) -> dict:
    """Attach {blocker, action} using PRODUCTION diagnose+decide_action."""
    blocker = phoebe.diagnose(state)
    action = phoebe.decide_action(blocker, state)
    return {
        "blocker": asdict(blocker),
        "action":  asdict(action),
    }


# ─── Main gen loop ─────────────────────────────────────────────────────────
def generate(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield unique labelled scenarios. Rejects dupes on content hash."""
    rng = random.Random(seed)
    seen: set[str] = set()
    archetype_names = list(ARCHETYPES.keys())

    tries = 0
    while len(seen) < n and tries < n * 20:
        tries += 1
        arch = rng.choice(archetype_names)
        state = ARCHETYPES[arch](rng)
        h = _canonical_hash(state)
        if h in seen:
            continue
        seen.add(h)
        yield {
            "id": h,
            "archetype": arch,
            "state": state,
            "labels": label(state),
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=800, help="target unique scenarios")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("training/dataset/scenarios.jsonl"))
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    per_arch: dict[str, int] = {}
    with args.out.open("w") as f:
        for s in generate(args.n, args.seed):
            f.write(json.dumps(s, default=str) + "\n")
            per_arch[s["archetype"]] = per_arch.get(s["archetype"], 0) + 1
            written += 1

    print(f"[scenario_gen] wrote {written} scenarios to {args.out}")
    for arch, count in sorted(per_arch.items()):
        print(f"  {arch:16s} {count}")


if __name__ == "__main__":
    main()
