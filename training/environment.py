"""Freesolo environment — the Phoebe agent (diagnose → act → message).

FIRST PASS / SCAFFOLD. Structure matches `flash env setup` (single-turn:
EnvironmentSingleTurn + build_prompt_messages + score_response, TaskExample
with .input/.output, RewardResult(score, threshold)). Shaped to the agent
task; the *real* reward, data, and sim are TODO seams below.

Agent task
----------
  input  = an agent scenario: reconciled trip state (city/dates/budget/
           per_person) + blocker flags + recent chat context.
  output = {"blocker": {...}, "action": {...}, "message": "..."} as JSON.

Labels are baked into dataset/train.jsonl at generation time by
`training/gen_dataset.py`, which imports the REAL production logic
(phoebe.diagnose / phoebe.decide_action) so training targets match what the
bot actually does. This env therefore does NOT import phoebe/brain — it only
grades the model's JSON against the pre-computed gold in `example.output`,
which keeps the uploaded environment self-contained (`training/` only).

Upload + reference
------------------
  flash env push --name phoebe-agent .      # from this folder; returns an id
  # paste that id into configs/*.toml → [environment].id
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from freesolo.datasets.types import TaskExample
from freesolo.environments import EnvironmentSingleTurn, RewardResult


DEFAULT_DATASET_PATH = Path(__file__).parent / "dataset" / "train.jsonl"

# ─── Output contract (also the guided-decoding schema) ──────────────────────
# Keep in sync with phoebe.BlockerKind / phoebe.ActionKind.
BLOCKER_KINDS = ["person", "timing", "issue", "none"]
ACTION_KINDS = [
    "dm_holdout", "propose_cheaper_neighborhood", "hold_rooms_48h",
    "ask_group", "no_action",
]

# TODO(subagent): bind this as guided decoding (structured_outputs) in the
# RL/OPD configs so rollouts can't emit format-broken text and the reward can
# grade content, not punctuation.
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["blocker", "action", "message"],
    "properties": {
        "blocker": {
            "type": "object",
            "required": ["kind", "subject", "detail"],
            "properties": {
                "kind": {"type": "string", "enum": BLOCKER_KINDS},
                "subject": {"type": "string", "maxLength": 80},
                "detail": {"type": "string", "maxLength": 300},
            },
        },
        "action": {
            "type": "object",
            "required": ["kind", "target", "parameters"],
            "properties": {
                "kind": {"type": "string", "enum": ACTION_KINDS},
                "target": {"type": "string", "maxLength": 80},
                "parameters": {"type": "object"},
            },
        },
        "message": {"type": "string", "minLength": 5, "maxLength": 240},
    },
}


def schema_json_string() -> str:
    """Compact JSON for the TOML `structured_outputs` field (see configs TODO)."""
    return json.dumps(OUTPUT_SCHEMA, separators=(",", ":"))


def load_jsonl(path: str | Path):
    rows = []
    with Path(path).open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _parse_json(response_text: str) -> dict | None:
    """Guided decoding should yield clean JSON; stay defensive so a non-guided
    SFT/eval path can't crash the reward."""
    if not response_text:
        return None
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _as_dict(output) -> dict:
    """example.output is a JSON string in the dataset; tolerate a dict too."""
    if isinstance(output, dict):
        return output
    return _parse_json(str(output or "")) or {}


class PhoebeEnv(EnvironmentSingleTurn):
    """Single-turn: read a trip scenario → emit {blocker, action, message}."""

    dataset = load_jsonl(DEFAULT_DATASET_PATH)

    def build_prompt_messages(self, example: TaskExample, prompt_text: str):
        # example.input is the fully-formatted scenario string produced by
        # gen_dataset._fmt_input — keep the two in parity.
        return [{"role": "user", "content": example.input or prompt_text}]

    def score_response(self, example: TaskExample, response_text: str) -> RewardResult:
        # ── FIRST-PASS REWARD: verifiable core only (blocker + action match) ──
        gold = _as_dict(example.output)
        pred = _parse_json(response_text) or {}

        blocker_ok = pred.get("blocker", {}).get("kind") == gold.get("blocker", {}).get("kind")
        action_ok = pred.get("action", {}).get("kind") == gold.get("action", {}).get("kind")
        score = 0.5 * float(blocker_ok) + 0.5 * float(action_ok)

        # TODO(subagent): replace with the full ground-truth reward —
        #   0.45 * blocker.kind match         (verifiable)
        # + 0.25 * action.kind match          (verifiable)
        # + 0.30 * message_rubric(...)        (names blocker subject/target +
        #                                      Sushi-kun voice heuristic)
        # - length_penalty(message > 220..240 chars)  (kills length-hacking)
        # and bind OUTPUT_SCHEMA as guided decoding in the configs so the
        # reward grades content, not JSON validity. Keep a STRICTER held-out
        # eval_metric (exact blocker+action pair, no partial credit) that is
        # NEVER used as the reward, so reward-hacking can't fake progress.

        return RewardResult(
            score=score,
            threshold=1.0,
            blocker_ok=blocker_ok,
            action_ok=action_ok,
        )


def load_environment(dataset_path: str | None = None, **kwargs) -> PhoebeEnv:
    env = PhoebeEnv()
    if dataset_path:
        env.dataset = load_jsonl(dataset_path)
    return env
