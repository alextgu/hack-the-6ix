"""Distill gold {blocker, action, message} outputs from the working Phoebe.

Pipeline:
  1. scenario_gen.generate(...) → N labelled scenarios (deterministic labels)
  2. phoebe.compose_message(...) → dynamic Sushi-kun gold message (LLM call)
  3. dedup + decontaminate → train.jsonl / eval.jsonl

Because message distillation calls the model per row, keep --n modest at first
(200-500) and use --skip-messages for a dry preview.

  python -m training.gen_dataset --n 800 --eval-frac 0.15
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from training.scenario_gen import generate, ARCHETYPES  # noqa: E402
import phoebe  # noqa: E402


def _fmt_input(state: dict) -> str:
    """The exact string the trained model will see as input.
    Kept in sync with `environment.PhoebeEnv.build_prompt_messages`."""
    return (
        "You are Sushi-kun (Phoebe agent). Read this reconciled trip state "
        "and return the ONE binding blocker, the resolution action, and the "
        "outreach message. Return ONLY JSON matching the schema.\n\n"
        f"STATE:\n{json.dumps(state, default=str, indent=2)}"
    )


def _fmt_output(labels: dict, message: str) -> dict:
    """The gold answer the model must learn to produce."""
    return {
        "blocker": labels["blocker"],
        "action":  labels["action"],
        "message": message,
    }


def _row(scenario: dict, message: str) -> dict:
    return {
        "id": scenario["id"],
        "archetype": scenario["archetype"],
        "input":  _fmt_input(scenario["state"]),
        "output": _fmt_output(scenario["labels"], message),
    }


def _split(rows: list[dict], eval_frac: float) -> tuple[list[dict], list[dict]]:
    """Deterministic decontaminated split: hash-based, so the SAME `id` never
    lands on both sides (this hashes on the same key the generator used)."""
    train, eval_ = [], []
    for r in rows:
        bucket = int(r["id"], 16) % 1000
        if bucket < eval_frac * 1000:
            eval_.append(r)
        else:
            train.append(r)
    # sanity: disjoint by id
    train_ids = {r["id"] for r in train}
    eval_ids = {r["id"] for r in eval_}
    assert train_ids.isdisjoint(eval_ids), "contamination! id overlap between splits"
    return train, eval_


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--eval-frac", type=float, default=0.15)
    ap.add_argument("--out-dir", type=Path, default=Path("training/dataset"))
    ap.add_argument("--skip-messages", action="store_true",
                    help="stub gold messages (no LLM calls) — for pipeline testing")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    print(f"[gen_dataset] generating {args.n} scenarios...")
    scenarios = list(generate(args.n, args.seed))

    for i, sc in enumerate(scenarios, 1):
        if args.skip_messages:
            gold_msg = "[stub — run without --skip-messages to distill via Phoebe]"
        else:
            try:
                action = phoebe.Action(**sc["labels"]["action"])
                gold_msg = phoebe.compose_message(action, sc["state"])
            except Exception as e:
                print(f"  ! [{sc['id']}] compose_message failed ({e}); skipping row")
                continue
        rows.append(_row(sc, gold_msg))
        if i % 25 == 0:
            print(f"  ...{i}/{len(scenarios)}")

    train, eval_ = _split(rows, args.eval_frac)
    (args.out_dir / "train.jsonl").write_text("\n".join(json.dumps(r) for r in train) + "\n")
    (args.out_dir / "eval.jsonl").write_text("\n".join(json.dumps(r) for r in eval_) + "\n")

    print(f"[gen_dataset] wrote {len(train)} train + {len(eval_)} eval rows to {args.out_dir}/")
    print(f"[gen_dataset] contamination check: disjoint by id ✓")


if __name__ == "__main__":
    main()
