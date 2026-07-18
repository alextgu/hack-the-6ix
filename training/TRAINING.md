# Phoebe Post-Training — Recipe

The full stack, chained: **SFT → OPD → GRPO**. Each stage earns its place;
skip one and you leave a track on the table.

- **SFT** (`configs/sft.toml`) — teaches the output contract and Sushi-kun
  register. Forward KL / mode-covering; cross-entropy on answer tokens.
  Ceiling = your data. This is the FLOOR; every downstream stage warm-starts
  from this adapter via `init_from_adapter`.
- **OPD** (`configs/opd.toml`) — on-policy distillation from a frontier
  teacher (default `glm-5.2`; also `deepseek-v4-pro`, `kimi-k2.6`). Reverse
  KL / mode-seeking; the teacher grades every token of the student's own
  attempt so credit lands on the mistakes it actually makes. Ceiling = the
  teacher. Gets a 4B to reason about blockers like a frontier model.
- **GRPO** (`configs/rl.toml`) — pushes past the teacher with the verifiable
  reward defined in `environment.py`. Ceiling = whatever the reward can
  measure. "It can pass any teacher."

Judge story: format → teacher-level → beyond-teacher, each technique earning
its place. Almost nobody chains all three.

## Run order

```bash
# 0.  publish the environment (once)
flash env publish training/environment.py --id <your-org>/phoebe-agent

# 1.  generate scenarios + gold outputs (needs a Phoebe LLM key — Gemini or Anthropic)
python -m training.scenario_gen --n 1000 --out training/dataset/scenarios.jsonl
python -m training.gen_dataset  --n 1000 --eval-frac 0.15

# 2.  SFT — sets the format contract
flash train --config training/configs/sft.toml
#     → note the run id, paste into opd.toml `init_from_adapter`

# 3.  OPD — frontier-level reasoning
flash train --config training/configs/opd.toml
#     → note the run id, paste into rl.toml `init_from_adapter`

# 4.  GRPO — beyond-teacher on the verifiable reward
flash train --config training/configs/rl.toml

# 5.  deploy the best checkpoint
flash deploy <best-run-id>
flash deployments --json      # copy openai_base_url
# then set in .env:
#   FREESOLO_AGENT_BASE_URL=https://<...>/v1
#   FREESOLO_AGENT_MODEL=<best-run-id>
```

## Guided decoding — non-negotiable

Every config sets `structured_outputs` to the JSON schema in
`environment.OUTPUT_SCHEMA`, so **p(format-breaking token) = 0** from token
one. Two payoffs:

1. Rollouts under GRPO/OPD can't produce malformed JSON — the reward grades
   content, not punctuation.
2. Kills format-collapse (failure mode #4) for free.

Pairs with `thinking = false`: reasoning tokens would break the schema
before the JSON starts.

## Reward design + anti-hacking (see `environment.PhoebeEnv.score_response`)

```
r  = 0.45 * (pred.blocker.kind == gold.blocker.kind)      # verifiable
r += 0.25 * (pred.action.kind  == gold.action.kind)        # verifiable
r += 0.30 * message_rubric(pred.message, gold_labels)      # rubric
r -= length_penalty(pred.message)                          # anti length-hacking
```

Defenses against reward-hacking (baked in — no per-run tweaking needed):

| Failure mode | Symptom | Mitigation |
| --- | --- | --- |
| Truncation (#1) | outputs cut mid-JSON | `max_completion_tokens = 640` — raise the cap FIRST |
| Length hacking (#2) | messages balloon to fill quota | `length_penalty` (soft floor 220, hard cap 240 via schema) |
| Entropy crash (#3) | rollouts converge, no group spread | `temperature = 0.9` in `rl.toml`; raise if traces show collapse |
| Format collapse (#4) | malformed JSON | `structured_outputs` guided decoding — mechanically impossible |
| Reward hacking generally | reward↑ eval flat | held-out `eval_metric` is stricter and separate — see below |

`kl_penalty_coef = 0.05` (KL leash β) keeps the policy near the reference so
degenerate-but-high-scoring text costs something. Tune only if a trace
demands it.

## Eval ≠ reward

`environment.PhoebeEnv.eval_metric` is **exact pair match** (blocker.kind AND
action.kind), no partial credit, no message grade. Run against the held-out
`eval.jsonl` split — never used as a training signal. Reward-hacking can't
masquerade as progress.

Held-out is decontaminated: `gen_dataset._split` hashes on the same content
`id` used by `scenario_gen`, guaranteeing disjoint splits.

### Grow past the noise floor

A 50-prompt eval swings several points on luck. Rerun the same checkpoint
twice (`run_ablation.py --seeds 2`) and treat any gain inside the run-to-run
band as noise. Report:

- **mean exact_pair_match ± spread** (the headline)
- **pass@k** for k in {1, 4} — agents care about pass@k
- **task eval AND general eval** (catastrophic-forgetting check) — if the
  general benchmark drifts, lower `epochs` / `learning_rate` / `lora_rank`

### The headline number

`+X points on exact_pair_match vs base, vs Gemini, vs the OPD teacher`,
with the noise-floor error bars.

## Hyperparameters — touch the four that matter (deck slide 43)

`learning_rate`, `epochs`, `group_size`, `max_completion_tokens`. **Change
one per run**; a trace tells you which knob moved it. Leave `batch_size`,
warmup, KL β, LoRA dropout, LR schedule at defaults until a trace names the
problem.

LoRA (slides 17–18): this is a new skill + RL headroom, not just a format
tweak — go higher rank. `lora_rank = 32`, `lora_alpha = 64` (α = 2r) on
Qwen3.5-4B (cap 64). Adapters wrap attention + MLP by default.

## The ablation matrix

`run_ablation.py` sweeps this grid and reports the pareto frontier
(accuracy vs latency vs cost):

| Axis | Values |
| --- | --- |
| Base model | 0.8B · 2B · 4B · (9B) · (35B-A3B MoE) |
| LoRA rank | 16 · 32 · 64 |
| Algorithm stack | SFT · SFT→GRPO · SFT→OPD→GRPO |
| Reasoning | thinking vs non-thinking |

The MoE row is a flex — 35B capacity at ~3B active latency, LoRA wraps
attention, router frozen. Closing slide: the scaling curve where a small
tuned model beats frontier zero-shot.

### Reading the curves (slide 34)

Healthy: reward ↑, held-out eval ↑, entropy easing down — all together.

- **stalled** (reward flat, eval flat) → check truncation (`max_completion_tokens`) and `group_size`
- **hacked** (reward ↑, eval flat) → read traces, patch reward
- **entropy crash** (rollouts converge) → raise `temperature` or loosen `kl_penalty_coef`

## Data

Hundreds-to-low-thousands of scenarios (deck: "hundreds not millions,
coverage beats volume"). `scenario_gen.py` covers all six archetypes with
varying group sizes, budget distributions, city configurations, and date
windows.

Dedup: sha256 of canonical-JSON on the state. Decontamination: `id`-hash
split, asserted disjoint at write time.

Labels come from **production** `phoebe.diagnose` + `phoebe.decide_action`
— never regressing on the live logic; GRPO then pushes past it.

## Serving

`flash deploy <best-run-id>` gives an OpenAI-compatible endpoint (prefix
caching on). Point `FREESOLO_AGENT_BASE_URL` at it and `phoebe.py`'s dispatch
switches from Gemini/Anthropic to the trained specialist. Or `flash export`
to HF for Fireworks/Baseten hosting.

The ablation picks the model that fits your latency budget — the "make the
product better" payoff: Phoebe runs on a specialist that beats Gemini on
deadlock resolution, faster and cheaper.

## What lives where

```
training/
├── scenario_gen.py     hundreds of diverse scenarios; labels from production
├── gen_dataset.py      distills Sushi-kun gold via phoebe.compose_message
├── environment.py      PhoebeEnv + reward + eval_metric + JSON schema
├── configs/
│   ├── sft.toml        FLOOR — format + register
│   ├── opd.toml        MIDDLE — frontier teacher (init_from_adapter=SFT)
│   └── rl.toml         TOP — GRPO on verifiable reward (init_from_adapter=OPD)
├── run_ablation.py     grid × 2 seeds; dry-run default; --live to burn GPU
└── TRAINING.md         this file
```
