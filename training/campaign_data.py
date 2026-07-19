"""Phase-0 campaign dataset: harvested flywheel records + diverse synthetic
scenarios → messenger-task rows, deduped, with a decontaminated eval split.

  .venv/bin/python -m training.campaign_data --n-synth 300 --eval-frac 0.12

Row: {"input": <serialized context>, "output": '{"message": ...}', "meta": {...}}
meta carries the VERIFIABLE ground truth the reward grades against (blocker
kind, action kind, subject/target names, missing fields, motivation) and is
never part of the model's target. Gold lines are Tabi-voice templates
parametrized per scenario (synthetic) or the real chosen line (harvested).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from app.integrations import db  # noqa: E402
from training.scenario_gen import generate  # noqa: E402
from training.build_dataset import serialize_context, _meta as _harvest_meta  # noqa: E402

OUT = Path(__file__).parent / "dataset"

# ─── Tabi-voice gold templates per action kind (lowercase, dramatic) ────────
def _gold_line(rng: random.Random, labels: dict, state: dict) -> str:
    a = labels["action"]; b = labels["blocker"]
    kind = a["kind"]; params = a.get("parameters") or {}
    city = state.get("city") or a.get("target") or "japan"
    if kind == "hold_rooms_48h":
        cands = params.get("candidates") or ["both cities"]
        pair = " vs ".join(cands)
        return rng.choice([
            f"you're deadlocked {pair} and it's literally aging me. i'm holding a room in each for 48h — someone say no",
            f"{pair}... pick ONE. i put a hold on both for 48h, whoever doesn't veto wins",
            f"ok the {pair} standoff ends now — rooms held in both for 48h, silence = i choose",
        ])
    if kind == "propose_cheaper_neighborhood":
        low = params.get("low_budget_person", "someone")
        return rng.choice([
            f"rerouting us to a cheaper corner of {city} so {low}'s budget fits — new picks in a sec",
            f"{low}'s wallet says no, so we shift neighborhoods in {city} instead of dropping anyone. on it",
            f"cheaper area of {city} coming up — nobody gets priced out on my watch, {low}",
        ])
    if kind == "dm_holdout" and b.get("kind") == "timing":
        names = ", ".join(list((state.get("per_person") or {}).keys())[:2]) or "everyone"
        return rng.choice([
            f"{names} — your dates don't overlap AT ALL and i'm shrinking. real windows, today",
            "our calendars don't touch. everyone drop the days you can ACTUALLY go — i'll find the overlap",
            f"dates are a mess ({names}, looking at you). give me must-hold days or i pick for you",
        ])
    if kind == "dm_holdout":  # silent holdout
        who = a.get("target", "someone")
        return rng.choice([
            f"{who} you've been suspiciously quiet — dates + budget, that's all i need to keep living",
            f"@{who} the plan is waiting on you and my health bar knows it. one number, one date range",
            f"{who}, say literally anything. budget? dates? blink twice?",
        ])
    if kind == "ask_group":
        return rng.choice([
            "quick one — top budget per person? i can't shop hotels blind",
            "nobody's said a budget and i'm too scared to guess. max $ per person, go",
            "budget check: what's the ceiling per person? the hotels need a number",
        ])
    return rng.choice([
        "plan's on track — i'll nap till you need me",
        "we're actually doing well?? keep it up, i'm thriving",
        "nothing blocking us right now. hydrate, then pick hotels",
    ])


def _chat_lines(rng: random.Random, state: dict) -> list[dict]:
    """Synthesize a short plausible transcript from per-person facts."""
    lines = []
    for name, p in list((state.get("per_person") or {}).items()):
        opts = []
        if p.get("city"):
            opts.append(f"{p['city']} for me")
        if p.get("budget"):
            opts.append(f"i can do ${p['budget']} max")
        d = p.get("dates") or {}
        if d.get("start"):
            opts.append(f"{d['start']} to {d.get('end','?')} works")
        if not opts:
            continue  # the silent one stays silent — that's the point
        rng.shuffle(opts)
        for o in opts[: rng.randint(1, 2)]:
            lines.append({"name": name, "text": o})
    rng.shuffle(lines)
    return lines[:8]


def _synth_row(rng: random.Random, sc: dict) -> dict:
    st = sc["state"]
    ctx = {
        "trip_state": {
            "city": st.get("city"), "dates": st.get("dates"),
            "budget_per_person": st.get("budget_per_person"),
            "group_size": st.get("group_size"),
            "stage": "GATHER", "missing": [], "physical": rng.randint(35, 95),
            "mental": rng.randint(30, 90),
        },
        "blocker_flags": st.get("blockers", []),
        "recent_chat": _chat_lines(rng, st),
    }
    gold = _gold_line(rng, sc["labels"], st)
    return {
        "input": serialize_context(ctx),
        "output": json.dumps({"message": gold}, ensure_ascii=False),
        "meta": {
            "source": "synthetic", "archetype": sc["archetype"],
            "blocker_kind": sc["labels"]["blocker"]["kind"],
            "action_kind": sc["labels"]["action"]["kind"],
            "subject": sc["labels"]["blocker"].get("subject"),
            "target": sc["labels"]["action"].get("target"),
            "chosen_motivation": 4.0, "progressed": None, "committed": None,
        },
    }


def _harvest_rows() -> list[dict]:
    rows = []
    for rec in db.messenger_records():
        chosen = (rec.get("chosen") or {}).get("text")
        ctx = rec.get("context") or {}
        if not chosen:
            continue
        m = _harvest_meta(rec)
        m.update({"source": "harvest", "archetype": "live",
                  "blocker_kind": None, "action_kind": None,
                  "subject": None, "target": None})
        rows.append({"input": serialize_context(ctx),
                     "output": json.dumps({"message": chosen}, ensure_ascii=False),
                     "meta": m})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-synth", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--eval-frac", type=float, default=0.12)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    harvested = _harvest_rows()
    synth = [_synth_row(rng, sc) for sc in generate(args.n_synth, args.seed)]
    rows = harvested + synth

    # Dedup on content (input+output).
    seen: set[str] = set()
    deduped = []
    for r in rows:
        h = hashlib.sha256((r["input"] + r["output"]).encode()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        deduped.append(r)

    # Decontaminated split: hash on INPUT so identical/near-identical contexts
    # can never straddle the split; then drop any residual overlap outright.
    train, eval_ = [], []
    for r in deduped:
        b = int(hashlib.md5(r["input"].encode()).hexdigest(), 16) % 1000
        (eval_ if b < args.eval_frac * 1000 else train).append(r)
    eval_inputs = {r["input"] for r in eval_}
    train = [r for r in train if r["input"] not in eval_inputs]
    assert not ({r["input"] for r in train} & eval_inputs), "contamination!"

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "train.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in train) + "\n")
    (OUT / "eval.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in eval_) + "\n")

    from collections import Counter
    arch = Counter(r["meta"]["archetype"] for r in deduped)
    print(f"[campaign_data] harvested={len(harvested)} synthetic={len(synth)} "
          f"→ deduped={len(deduped)} → train={len(train)} eval={len(eval_)} (disjoint ✓)")
    print(f"[campaign_data] archetype mix: {dict(arch)}")


if __name__ == "__main__":
    main()
