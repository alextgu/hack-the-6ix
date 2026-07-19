# Held-out eval — the proof behind "4× the frontier"

This folder is the evidence for the pitch claim: *our fine-tuned 4B beats a
frontier model ~4× at finding the group's real blocker, on scenarios it never
trained on.* Everything here is re-runnable — don't take the number on faith,
open the file or re-run the harness.

## The claim, and where each part is proven

| Claim | Proof |
| --- | --- |
| Held-out — "never trained on" | `dataset/eval.jsonl` (50) shares **0** inputs with `dataset/train.jsonl` (290 unique). Verify: the one-liner at the bottom. |
| Same eval, ground-truth scored | `../eval_harness.py` grades **both** models against the gold `message` line (token-F1). Identical code path; it can't favor ours. |
| The numbers | `results-frontier.jsonl` and `results-trained.jsonl` below — every prompt, both models' actual completions, per-example scores. |
| It's the live model | `results-trained.jsonl` is the deployed run `flash-1784429566-05568e2a` — the same one `FREESOLO_AGENT_BASE_URL` points the messenger at. |

## The measured run (this snapshot)

| Metric | Frontier (gemini, zero-shot) | Trained (GRPO-B, live) |
| --- | --- | --- |
| Gold-F1 | 0.078 | **0.317**  (4.04×) |
| In-voice % | 0 | **98** |
| Valid-JSON % | 88 | **100** |
| n / errors | 50 / 0 | 50 / 0 |

Decoding is stochastic (flash at temp 0.2), so a re-run moves these by ~0.01.
The committed `.jsonl` files are the source of truth for the landing/webapp chart.

## File format

Line 1 is `{"summary": {...aggregate...}}`; each remaining line is one example:
`{"i", "input", "gold", "raw" (model's raw output), "message" (parsed), "metrics": {"valid","f1","voice","len"}}`.

The qualitative story is visible per row — e.g. on the same prompt the trained
model answers in Tabi's lowercase pet-voice while the frontier writes like a
generic assistant (`voice: true` vs `false`).

## Regenerate

```bash
# frontier baseline
python -m training.eval_harness --model gemini \
  --tag frontier --dump training/eval/results-frontier.jsonl
# the live trained adapter
python -m training.eval_harness --model flash:flash-1784429566-05568e2a \
  --tag trained  --dump training/eval/results-trained.jsonl
```

## Verify the held-out split yourself

```bash
python - <<'PY'
import json
inp=lambda p:{json.dumps(json.loads(l)["input"],sort_keys=True) for l in open(p) if l.strip()}
tr,ev=inp("training/dataset/train.jsonl"),inp("training/dataset/eval.jsonl")
print("overlap:",len(tr&ev),"/",len(ev))   # -> 0 / 50
PY
```
