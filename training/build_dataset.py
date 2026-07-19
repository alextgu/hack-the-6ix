"""Build the messenger training dataset from the Mongo harvest (the flywheel).

Pulls the records the LIVE supervisor logs (db.messenger_records) and writes:
  dataset/train.jsonl       SFT rows: (context → chosen best line) + reward meta
  dataset/preference.jsonl  GRPO/preference rows: 4 candidates + scores + outcome
  dataset/eval.jsonl        decontaminated held-out split (never trained on)

Row shapes
  SFT:    {"input": <ctx>, "output": '{"message": <line>}',
           "meta": {chosen_motivation, candidate_motivations, mean_motivation,
                    progressed, committed}}
  pref:   {"input": <ctx>, "candidates": [{text, motivation}], "outcome": {...}}

If Mongo is absent/empty (no harvest yet), a few SYNTHETIC starter rows are
written so environment.py still loads and dry-runs — replace them by running the
live bot with MONGODB_URI set to harvest real data.

  python -m training.build_dataset [--eval-frac 0.15]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from app.integrations import db  # noqa: E402  (no-ops without Mongo)

OUT_DIR = Path(__file__).parent / "dataset"


def serialize_context(ctx: dict) -> str:
    """Canonical serialization of a messenger context → model input. Mirrors
    what supervisor.messenger sees; keep in parity when the trained model goes
    live so training and inference share one input format."""
    ts = ctx.get("trip_state", {}) or {}
    chat = ctx.get("recent_chat", []) or []
    lines = [f"{m.get('name')}: {m.get('text')}" for m in chat][-15:]
    return (
        "You are Tabi, the trip-planning pet in a group chat. Read the group's "
        "state and write ONE short persuasive line to move the plan forward. "
        'Return ONLY JSON: {"message": "..."}.\n\n'
        f"STAGE: {ts.get('stage')}  MISSING: {ts.get('missing')}\n"
        f"TRIP: city={ts.get('city')} dates={ts.get('dates')} "
        f"budget={ts.get('budget_per_person')} group_size={ts.get('group_size')}\n"
        f"PET: physical={ts.get('physical')} mental={ts.get('mental')}\n"
        f"BLOCKERS: {ctx.get('blocker_flags', [])}\n"
        "RECENT CHAT:\n" + "\n".join(lines)
    )


def _meta(rec: dict) -> dict:
    cand_mots = [c.get("motivation_score") for c in rec.get("candidates", [])
                 if c.get("motivation_score") is not None]
    outcome = rec.get("outcome") or {}
    return {
        "chosen_motivation": (rec.get("chosen") or {}).get("motivation_score"),
        "candidate_motivations": cand_mots,
        "mean_motivation": (sum(cand_mots) / len(cand_mots)) if cand_mots else None,
        "progressed": outcome.get("progressed"),
        "committed": outcome.get("committed"),
    }


def _is_eval(input_str: str, eval_frac: float) -> bool:
    """Deterministic, decontaminated: same input always lands on the same side."""
    h = int(hashlib.md5(input_str.encode()).hexdigest(), 16) % 1000
    return h < eval_frac * 1000


def _rows_from_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (sft_rows, preference_rows) from harvested records."""
    sft, pref = [], []
    for rec in records:
        ctx = rec.get("context") or {}
        chosen = (rec.get("chosen") or {}).get("text")
        if not chosen:
            continue
        inp = serialize_context(ctx)
        sft.append({"input": inp,
                    "output": json.dumps({"message": chosen}, ensure_ascii=False),
                    "meta": _meta(rec)})
        pref.append({"input": inp,
                     "candidates": [{"text": c.get("text"),
                                     "motivation": c.get("motivation_score")}
                                    for c in rec.get("candidates", []) if c.get("text")],
                     "outcome": rec.get("outcome")})
    return sft, pref


# ─── Synthetic starters (used only when no harvest exists yet) ───────────────
_SYNTH = [
    {"ctx": {"trip_state": {"stage": "GATHER", "missing": ["dates", "budget"],
                            "city": "Tokyo", "dates": {"start": None, "end": None},
                            "budget_per_person": None, "group_size": 4,
                            "physical": 82, "mental": 61},
             "blocker_flags": ["budget_missing: no budget stated"],
             "recent_chat": [{"name": "alice", "text": "tokyo for sure"},
                             {"name": "bob", "text": "when though"}]},
     "line": "tokyo locked 🎉 now the boring bit — alice, bob, drop your dates + a rough budget so i can stop starving",
     "meta": {"chosen_motivation": 4.5, "candidate_motivations": [4.5, 3.0, 2.0],
              "mean_motivation": 3.17, "progressed": True, "committed": False}},
    {"ctx": {"trip_state": {"stage": "GATHER", "missing": ["city"],
                            "city": None, "dates": {"start": "2027-05-01", "end": "2027-05-07"},
                            "budget_per_person": 1800, "group_size": 4,
                            "physical": 55, "mental": 40},
             "blocker_flags": ["city_tie: TIE between Tokyo, Kyoto (2 votes each)"],
             "recent_chat": [{"name": "carla", "text": "kyoto"},
                             {"name": "dave", "text": "tokyo tho"}]},
     "line": "we're deadlocked tokyo vs kyoto and it's literally aging me. quick vote — 👍 tokyo, ❤️ kyoto, i'll hold a room in the winner",
     "meta": {"chosen_motivation": 5.0, "candidate_motivations": [5.0, 3.5],
              "mean_motivation": 4.25, "progressed": False, "committed": False}},
    {"ctx": {"trip_state": {"stage": "HOTELS", "missing": [],
                            "city": "Tokyo", "dates": {"start": "2027-04-12", "end": "2027-04-18"},
                            "budget_per_person": 1500, "group_size": 4,
                            "physical": 70, "mental": 75},
             "blocker_flags": [],
             "recent_chat": [{"name": "alice", "text": "ok flights done"}]},
     "line": "flights done, i'm thriving 😤 last stretch — swipe the hotel deck i just dropped and we're officially booked",
     "meta": {"chosen_motivation": 4.0, "candidate_motivations": [4.0, 2.5],
              "mean_motivation": 3.25, "progressed": True, "committed": True}},
]


def _synthetic_rows() -> tuple[list[dict], list[dict]]:
    sft, pref = [], []
    for s in _SYNTH:
        inp = serialize_context(s["ctx"])
        sft.append({"input": inp,
                    "output": json.dumps({"message": s["line"]}, ensure_ascii=False),
                    "meta": s["meta"]})
        pref.append({"input": inp,
                     "candidates": [{"text": s["line"], "motivation": s["meta"]["chosen_motivation"]}],
                     "outcome": {"progressed": s["meta"]["progressed"],
                                 "committed": s["meta"]["committed"]}})
    return sft, pref


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-frac", type=float, default=0.15)
    args = ap.parse_args()

    records = db.messenger_records()
    if records:
        sft, pref = _rows_from_records(records)
        source = f"{len(records)} harvested records"
    else:
        sft, pref = _synthetic_rows()
        source = "SYNTHETIC starters (no harvest — set MONGODB_URI + run the bot to collect real data)"

    # Decontaminated held-out split (by input hash; train/eval disjoint).
    train = [r for r in sft if not _is_eval(r["input"], args.eval_frac)]
    eval_ = [r for r in sft if _is_eval(r["input"], args.eval_frac)]
    if not train:  # tiny synthetic set — keep everything trainable
        train, eval_ = sft, []

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "train.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in train) + "\n")
    (OUT_DIR / "preference.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in pref) + "\n")
    (OUT_DIR / "eval.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in eval_) + ("\n" if eval_ else ""))

    labeled = sum(1 for r in sft if r["meta"].get("progressed") is not None)
    print(f"[build_dataset] source: {source}")
    print(f"[build_dataset] wrote {len(train)} train + {len(eval_)} eval SFT rows, "
          f"{len(pref)} preference rows → {OUT_DIR}/")
    print(f"[build_dataset] {labeled}/{len(sft)} rows have a ground-truth outcome "
          "(the rest await back-fill / are neutral in the reward)")
    train_ids = {r["input"] for r in train}
    assert train_ids.isdisjoint({r["input"] for r in eval_}), "contamination!"
    print("[build_dataset] contamination check: train/eval disjoint ✓")


if __name__ == "__main__":
    main()
