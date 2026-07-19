"""Generate the STARTER training dataset for the Phoebe agent env.

FIRST PASS: a handful of rows distilled from the sample states in
`phoebe.py`'s __main__ (phoebe._SAMPLES). Labels come from the REAL production
logic — phoebe.diagnose → phoebe.decide_action — so the training targets match
what the bot actually decides. The gold message uses phoebe's deterministic
canned line (no LLM/network needed), which keeps this reproducible.

  python -m training.gen_dataset            # writes training/dataset/train.jsonl

TODO(subagent): replace this with the full scenario generator —
  * diversity: every blocker kind × group size × budget spread
  * a decontaminated train/eval split (hash on scenario id; disjoint)
  * optionally distill the gold message via phoebe.compose_message (LLM) for
    phrasing variety instead of the canned line.
See training/scenario_gen.py for the diversity-generator seam.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

# Make the bot package importable so we reuse the production agent logic.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from app.agents import phoebe  # noqa: E402

OUT_PATH = Path(__file__).parent / "dataset" / "train.jsonl"


def _fmt_input(name: str, state: dict) -> str:
    """The exact string the trained model sees. MUST stay in parity with
    environment.PhoebeEnv.build_prompt_messages."""
    return (
        "You are Sushi-kun, the trip-planning pet agent. Read this reconciled "
        "trip state (constraints + blocker flags) and return the ONE binding "
        "blocker, the resolution action, and a short outreach message. "
        "Return ONLY JSON: {\"blocker\":{\"kind\",\"subject\",\"detail\"},"
        "\"action\":{\"kind\",\"target\",\"parameters\"},\"message\":\"...\"}.\n\n"
        f"SCENARIO: {name}\n"
        f"STATE:\n{json.dumps(state, default=str, indent=2)}"
    )


def _gold_output(state: dict) -> dict:
    """Ground-truth labels from the real Phoebe pipeline (deterministic)."""
    blocker = phoebe.diagnose(state)              # → Blocker
    action = phoebe.decide_action(blocker, state)  # → Action
    message = phoebe._canned(action)              # deterministic gold message
    return {
        "blocker": {"kind": blocker.kind, "subject": blocker.subject, "detail": blocker.detail},
        "action": {"kind": action.kind, "target": action.target,
                   "parameters": action.parameters or {}},
        "message": message,
    }


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for name, state in phoebe._SAMPLES.items():
        # phoebe.diagnose reads state["blockers"]; _SAMPLES already carries them.
        out = _gold_output(state)
        rows.append({
            "input": _fmt_input(name, state),
            # output is a JSON string so a row is {"input": str, "output": str},
            # matching the flash starter row shape; the env json-parses it.
            "output": json.dumps(out, ensure_ascii=False),
        })
    return rows


def main() -> None:
    rows = build_rows()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    print(f"[gen_dataset] wrote {len(rows)} starter rows → {OUT_PATH}")
    for r in rows:
        out = json.loads(r["output"])
        print(f"  · blocker={out['blocker']['kind']:7} action={out['action']['kind']}")


if __name__ == "__main__":
    main()
