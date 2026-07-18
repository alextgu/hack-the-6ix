"""Freesolo environment for the Phoebe agent.

Verifiable-heavy reward (own the ground truth):
  0.45 · exact blocker.kind match
  0.25 · exact action.kind match
  0.30 · message rubric (mentions blocker subject + in-Sushi-voice heuristic)
 −len(message) penalty above 240 chars (kills length-hacking)

Guided decoding: JSON schema below is bound from token 0 via
`structured_outputs` in the RL/OPD configs, so rollouts can't produce
format-broken text — the reward grades content, not punctuation.

`score_response` is the RL reward. `eval_metric` is the stricter held-out
metric (exact blocker.kind + action.kind match, no partial credit) —
NEVER used as the reward, so reward-hacking can't masquerade as progress.

Publish this env to Freesolo's Environments Hub with:
  flash env publish training/environment.py --id <your-org>/phoebe-agent
Then reference it in configs/*.toml as [environment].id.
"""
from __future__ import annotations
import json
import re
from typing import Any

try:
    from freesolo.environments import EnvironmentSingleTurn, RewardResult
    from freesolo.datasets import TaskExample
except ImportError:  # allow static/local checking without freesolo installed
    class EnvironmentSingleTurn:  # type: ignore
        pass

    class RewardResult:  # type: ignore
        def __init__(self, score: float, threshold: float = 0.9, **meta: Any) -> None:
            self.score = score
            self.threshold = threshold
            self.meta = meta
            for k, v in meta.items():
                setattr(self, k, v)

    class TaskExample:  # type: ignore
        input: str
        output: Any


# ─── JSON schema — pin structured_outputs to this in the configs ───────────
BLOCKER_KINDS = ["person", "timing", "issue", "none"]
ACTION_KINDS = [
    "dm_holdout", "propose_cheaper_neighborhood", "hold_rooms_48h",
    "ask_group", "no_action",
]

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["blocker", "action", "message"],
    "properties": {
        "blocker": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "subject", "detail"],
            "properties": {
                "kind":    {"type": "string", "enum": BLOCKER_KINDS},
                "subject": {"type": "string", "maxLength": 80},
                "detail":  {"type": "string", "maxLength": 300},
            },
        },
        "action": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "target", "parameters"],
            "properties": {
                "kind":       {"type": "string", "enum": ACTION_KINDS},
                "target":     {"type": "string", "maxLength": 80},
                "parameters": {"type": "object"},
            },
        },
        "message": {"type": "string", "minLength": 5, "maxLength": 240},
    },
}


# ─── Length + voice heuristics ─────────────────────────────────────────────
_LENGTH_SOFT_CAP = 220   # target
_LENGTH_HARD_CAP = 240   # matches schema maxLength
_VOICE_PENALTIES = re.compile(
    r"(as an ai|i'm an ai|i am a language model|as an assistant|"
    r"here (?:is|are) (?:a|the)|please note|kindly)", re.I,
)


def _length_penalty(message: str) -> float:
    """Soft floor at 220 chars; linear penalty up to 240; hard-cap already
    enforced by schema. Returns [0.0, 0.15]."""
    over = max(0, len(message) - _LENGTH_SOFT_CAP)
    return min(0.15, 0.15 * over / (_LENGTH_HARD_CAP - _LENGTH_SOFT_CAP))


def _voice_score(message: str) -> float:
    """Cheap heuristics for 'Sushi-kun voice':
      + starts lowercase (∴ no capitalized preamble)
      + no LLM-tell phrases
      + short (single line-ish)
    Returns [0.0, 1.0]. Combined with subject-mention below in message_rubric."""
    if not message:
        return 0.0
    s = 0.0
    if message[:1].islower() or message[:1] in "@#":
        s += 0.4
    if not _VOICE_PENALTIES.search(message):
        s += 0.4
    if message.count("\n") == 0:
        s += 0.2
    return s


def message_rubric(pred_msg: str, gold_labels: dict) -> float:
    """0.0..1.0 rubric. Reward the message for (a) naming the blocker subject
    or (b) at least addressing the action's target, AND (c) sounding like Sushi.
    The gold message is used for schema keys, not string-matched — we want
    variety in phrasing, so no ROUGE-L overkill."""
    subject = (gold_labels.get("blocker") or {}).get("subject", "") or ""
    target = (gold_labels.get("action") or {}).get("target", "") or ""
    msg_lo = pred_msg.lower()

    mention = 0.0
    if subject and subject.lower() in msg_lo:
        mention = 1.0
    elif target and target.lower() in msg_lo:
        mention = 0.6
    voice = _voice_score(pred_msg)
    return 0.5 * mention + 0.5 * voice


# ─── Parse guarded response ────────────────────────────────────────────────
def parse_response(response_text: str) -> dict | None:
    """Guided decoding SHOULD give us clean JSON; still defensive so a
    non-guided fallback path (e.g. SFT eval) doesn't crash the reward."""
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


# ─── The Environment ───────────────────────────────────────────────────────
class PhoebeEnv(EnvironmentSingleTurn):
    """Single-turn: read a trip state, emit {blocker, action, message}.

    Register in configs/*.toml as `[environment].id = "<org>/phoebe-agent"`,
    then set `[train].structured_outputs = <OUTPUT_SCHEMA as JSON string>`.
    """

    def build_prompt_messages(self, example: TaskExample, prompt_text: str):
        # `example.input` is the fully-formatted string produced by
        # gen_dataset._fmt_input — keep parity there and here.
        text = example.input if getattr(example, "input", None) else prompt_text
        return [{"role": "user", "content": text}]

    def score_response(self, example: TaskExample, response_text: str) -> RewardResult:
        gold = getattr(example, "output", None) or {}
        pred = parse_response(response_text) or {}

        blocker_ok = (pred.get("blocker", {}).get("kind") ==
                      gold.get("blocker", {}).get("kind"))
        action_ok = (pred.get("action", {}).get("kind") ==
                     gold.get("action", {}).get("kind"))
        rubric = message_rubric(pred.get("message", "") or "", gold)
        penalty = _length_penalty(pred.get("message", "") or "")

        score = (
            0.45 * (1.0 if blocker_ok else 0.0)
            + 0.25 * (1.0 if action_ok else 0.0)
            + 0.30 * rubric
            - penalty
        )
        score = max(0.0, min(1.0, score))
        return RewardResult(
            score=score,
            threshold=0.9,
            blocker_ok=blocker_ok, action_ok=action_ok,
            rubric=rubric, length_penalty=penalty,
        )

    # NOT wired as the reward — surfaced separately by run_ablation.py against
    # the held-out eval split. Stricter: both blocker.kind AND action.kind
    # must match exactly.  No partial credit, no message grade.
    def eval_metric(self, example: TaskExample, response_text: str) -> dict:
        gold = getattr(example, "output", None) or {}
        pred = parse_response(response_text) or {}
        blocker_ok = (pred.get("blocker", {}).get("kind") ==
                      gold.get("blocker", {}).get("kind"))
        action_ok = (pred.get("action", {}).get("kind") ==
                     gold.get("action", {}).get("kind"))
        return {
            "exact_pair_match": 1.0 if (blocker_ok and action_ok) else 0.0,
            "blocker_ok": 1.0 if blocker_ok else 0.0,
            "action_ok": 1.0 if action_ok else 0.0,
        }


# Export schema as a JSON string for the TOML `structured_outputs` field.
def schema_json_string() -> str:
    return json.dumps(OUTPUT_SCHEMA, separators=(",", ":"))
