"""Freesolo environment — the MESSENGER task (train Tabi's persuasive voice).

Reshaped from the old diagnose task to the messenger task that the LIVE
supervisor actually runs:

  input  = serialized agent context: trip_state + blocker_flags + recent_chat
           (produced by training/build_dataset.py::serialize_context, which
           mirrors what supervisor.messenger sees).
  output = ONE persuasive line as guided-decoding JSON: {"message": "..."}.

Reward (score_response) — dense, ground-truth-anchored:
  + motivation component  — how strong the chosen line's self-score was
                            (proxy for "consistent with high-scoring
                             candidates"; TODO: real candidate-similarity)
  + OUTCOME component     — the VERIFIABLE ground truth: did the group actually
                            progress after this line was sent? (harvested by
                            the Mongo flywheel, back-filled by the bot)
  − length penalty        — kills length-hacking
eval_metric (commit_rate / progress_rate) is a STRICTER held-out signal and is
NEVER used as the reward — so reward-hacking can't masquerade as progress.

Rows carry a `meta` field (outcome + motivations) that the reward reads via a
per-input index; the model's OUTPUT is message-only (guided decoding), so meta
never leaks into training targets.

Upload: flash env push --name phoebe-agent .   (id already in configs)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from freesolo.datasets.types import TaskExample
from freesolo.environments import EnvironmentSingleTurn, RewardResult


DEFAULT_DATASET_PATH = Path(__file__).parent / "dataset" / "train.jsonl"

# Guided-decoding schema: the model may only emit {"message": "..."} so every
# rollout is valid JSON and the reward grades content, not punctuation.
# TODO(subagent): bind this as structured_outputs in configs/{rl,opd}.toml.
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["message"],
    "properties": {"message": {"type": "string", "minLength": 3, "maxLength": 300}},
}


def schema_json_string() -> str:
    return json.dumps(OUTPUT_SCHEMA, separators=(",", ":"))


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _load_raw(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# Load once. `dataset` is what Flash trains on (input/output only); `_META`
# indexes the reward ground-truth by input so score_response can reach it
# without leaking it into the SFT target.
_RAW = _load_raw(DEFAULT_DATASET_PATH) if DEFAULT_DATASET_PATH.exists() else []
_META = {r["input"]: (r.get("meta") or {}) for r in _RAW}


def _length_penalty(msg: str) -> float:
    return min(0.2, max(0, len(msg) - 220) / 400.0)


class MessengerEnv(EnvironmentSingleTurn):
    """Single-turn: read the serialized context → emit ONE persuasive line."""

    dataset = [{"input": r["input"], "output": r["output"]} for r in _RAW]

    def build_prompt_messages(self, example: TaskExample, prompt_text: str):
        return [{"role": "user", "content": example.input or prompt_text}]

    def score_response(self, example: TaskExample, response_text: str) -> RewardResult:
        """Dense, verifiable, tiered reward (per the post-training playbook):
        parse gate → addresses-the-blocker rubric → voice → outcome, with a
        length penalty so length-hacking never pays. Never raises."""
        try:
            meta = _META.get(example.input, {})
            pred = _extract_json(str(response_text)) or {}
            msg = str(pred.get("message", "")).strip()

            # Tier 0 — hard validity gate: unparseable/empty → 0 (no judge to hack).
            if not msg:
                return RewardResult(score=0.0, threshold=0.75)

            score = 0.25  # parses + non-empty (dense floor so GRPO has gradient)

            # Tier 1 (0.35) — VERIFIABLE: does the line address the actual
            # blocker? Checked against ground-truth labels baked at gen time.
            msg_lo = msg.lower()
            mentions = 0.0
            for key in ("subject", "target"):
                v = meta.get(key)
                if v and str(v).lower() not in ("none", "group") and str(v).lower() in msg_lo:
                    mentions = 1.0
            bk = meta.get("blocker_kind")
            topic_words = {
                "issue": ("city", "budget", "hold", "pick", "vote"),
                "timing": ("date", "day", "window", "overlap", "calendar", "when"),
                "person": ("budget", "$", "date", "quiet", "waiting"),
                "none": ("track", "nap", "hotel", "keep", "thriving", "well"),
            }.get(bk, ())
            topical = any(w in msg_lo for w in topic_words) if topic_words else 0.0
            score += 0.35 * max(mentions, 0.6 * float(bool(topical)))

            # Tier 2 (0.20) — voice: lowercase, ≤3 lines, no LLM-tells.
            voice = 0.0
            if msg[:1].islower() or msg[:1] in "@[":
                voice += 0.5
            if msg.count("\n") <= 2:
                voice += 0.25
            if not re.search(r"(as an ai|i am a language model|certainly|here is)", msg_lo):
                voice += 0.25
            score += 0.20 * voice

            # Tier 3 (0.20) — ground-truth outcome when the flywheel has it.
            progressed = meta.get("progressed")
            score += 0.20 * (0.5 if progressed is None else float(bool(progressed)))

            score -= _length_penalty(msg)
            score = max(0.0, min(1.0, score))
            return RewardResult(score=score, threshold=0.75)
        except Exception:
            return RewardResult(score=0.0, threshold=0.75)

    # Stricter held-out signal — NEVER the reward: gold-line token-F1 +
    # validity. Judges the run; the reward above trains it.
    def eval_metric(self, example: TaskExample, response_text: str) -> dict:
        pred = _extract_json(str(response_text)) or {}
        msg = str(pred.get("message", "")).strip()
        gold = str((_extract_json(str(example.output)) or {}).get("message", ""))
        pt, gt = set(msg.lower().split()), set(gold.lower().split())
        f1 = (2 * len(pt & gt) / (len(pt) + len(gt))) if pt and gt else 0.0
        return {"schema_valid": 1.0 if msg else 0.0, "gold_token_f1": round(f1, 4)}


def load_environment(dataset_path: str | None = None, **kwargs) -> MessengerEnv:
    env = MessengerEnv()
    if dataset_path:
        raw = _load_raw(dataset_path)
        env.dataset = [{"input": r["input"], "output": r["output"]} for r in raw]
        _META.update({r["input"]: (r.get("meta") or {}) for r in raw})
    return env
