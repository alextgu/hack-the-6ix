"""Ablation driver: sweep {base × rank × algorithm-stack × thinking}, twice
each for noise-floor, and write the results table.

Rerun each config twice → measure run-to-run variance so a gain inside the
noise band doesn't get reported as real.

Dry-run mode (default) prints the plan + fake results so you can eyeball the
grid without spending money. Real mode invokes `flash train` per row and
polls for completion.

  python -m training.run_ablation --dry-run
  python -m training.run_ablation --live --seeds 2
"""
from __future__ import annotations
import argparse
import copy
import itertools
import json
import subprocess
import time
import tomllib  # 3.11+
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CFG_DIR = ROOT / "configs"
RESULTS = ROOT / "ablation_results.jsonl"


# ─── The grid ──────────────────────────────────────────────────────────────
BASE_MODELS = [
    "Qwen/Qwen3.5-0.8B",       # cheap smoke
    "Qwen/Qwen3.5-2B",
    "Qwen/Qwen3.5-4B",         # default
    # "Qwen/Qwen3.5-9B",       # uncomment when ready
    # "some-org/moe-35b-a3b",  # MoE flex: 35B capacity @ ~3B latency
]
LORA_RANKS = [16, 32, 64]
STACKS = [
    ("sft",),                  # SFT only
    ("sft", "grpo"),           # SFT → GRPO
    ("sft", "opd", "grpo"),    # the full stack (SFT → OPD → GRPO)
]
THINKING_MODES = [False, True]


@dataclass
class Row:
    base: str
    rank: int
    stack: tuple[str, ...]
    thinking: bool
    seed: int

    def slug(self) -> str:
        model = self.base.replace("/", "-").replace(".", "")
        return f"{model}_r{self.rank}_{'-'.join(self.stack)}_th{int(self.thinking)}_s{self.seed}"


def build_grid(seeds: int) -> list[Row]:
    rows: list[Row] = []
    for base, rank, stack, think in itertools.product(
        BASE_MODELS, LORA_RANKS, STACKS, THINKING_MODES,
    ):
        for s in range(seeds):
            rows.append(Row(base=base, rank=rank, stack=stack, thinking=think, seed=s))
    return rows


# ─── Config rendering ──────────────────────────────────────────────────────
def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def _dumps_toml(cfg: dict[str, Any]) -> str:
    """Minimal TOML dump — good enough for the fields the templates use.
    Avoids adding tomli-w just to write config files for one CLI."""
    out: list[str] = []
    for k, v in cfg.items():
        if isinstance(v, dict):
            continue
        out.append(f"{k} = {_toml_val(v)}")
    for k, v in cfg.items():
        if isinstance(v, dict):
            out.append(f"\n[{k}]")
            for kk, vv in v.items():
                out.append(f"{kk} = {_toml_val(vv)}")
    return "\n".join(out) + "\n"


def _toml_val(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v)  # gives us the quoting for free
    if isinstance(v, list):
        return "[" + ", ".join(_toml_val(x) for x in v) + "]"
    raise TypeError(f"can't TOML-encode {type(v).__name__}")


# Stage name → config template filename.
_STAGE_TEMPLATE = {"sft": "sft.toml", "opd": "opd.toml", "grpo": "rl.toml"}


def render_configs_for(row: Row, tmp_dir: Path, prev_run_ids: dict[str, str]) -> list[Path]:
    """One TOML per stage. `prev_run_ids` maps 'sft' → sft_run_id, etc.,
    so each downstream stage warm-starts from the previous stage's adapter."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for stage in row.stack:
        cfg = _load_toml(CFG_DIR / _STAGE_TEMPLATE[stage])
        cfg["model"] = row.base
        cfg["thinking"] = row.thinking
        cfg["seed"] = 42 + row.seed
        train = cfg.setdefault("train", {})
        # SFT sets rank; downstream stages inherit via init_from_adapter.
        if stage == "sft":
            train["lora_rank"] = row.rank
            train["lora_alpha"] = row.rank * 2
        else:
            for k in ("lora_rank", "lora_alpha"):
                train.pop(k, None)
            train["init_from_adapter"] = prev_run_ids.get(
                "opd" if stage == "grpo" and "opd" in row.stack else "sft"
            ) or "<UPSTREAM-RUN-MISSING>"
        p = tmp_dir / f"{row.slug()}_{stage}.toml"
        p.write_text(_dumps_toml(cfg))
        paths.append(p)
    return paths


# ─── Runner ────────────────────────────────────────────────────────────────
def run_flash_train(cfg_path: Path) -> tuple[str, dict]:
    """Real invocation: `flash train --config <path>`. Parses the printed
    run id + waits for `flash runs get <id> --json` to say status=succeeded.
    Returns (run_id, eval_metrics)."""
    proc = subprocess.run(
        ["flash", "train", "--config", str(cfg_path)],
        capture_output=True, text=True,
    )
    # Freesolo prints the run id on stdout; scrape it.
    for line in proc.stdout.splitlines():
        if line.startswith("run_id:"):
            run_id = line.split(":", 1)[1].strip()
            break
    else:
        raise RuntimeError(f"no run_id in flash output:\n{proc.stdout}\n{proc.stderr}")

    # Poll for completion (real world: use `flash runs get --json`).
    while True:
        status = subprocess.run(
            ["flash", "runs", "get", run_id, "--json"],
            capture_output=True, text=True,
        )
        data = json.loads(status.stdout)
        if data.get("status") in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(30)

    if data.get("status") != "succeeded":
        raise RuntimeError(f"{run_id} → {data.get('status')}")
    return run_id, data.get("eval", {})


def dry_run(cfg_path: Path, row: Row, stage: str) -> tuple[str, dict]:
    """Fake run — pretend numbers to eyeball the grid + noise floor logic."""
    import random
    rng = random.Random(hash((row.slug(), stage)))
    fake_id = f"dryrun-{row.slug()}-{stage}"
    # A plausibly-improving-across-stages fake metric.
    base = {"sft": 0.55, "opd": 0.68, "grpo": 0.79}[stage]
    noise = rng.uniform(-0.03, 0.03)
    rank_bonus = {16: 0.0, 32: 0.02, 64: 0.03}[row.rank]
    return fake_id, {"exact_pair_match": round(base + noise + rank_bonus, 4)}


# ─── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="actually run `flash train`; default is dry-run")
    ap.add_argument("--seeds", type=int, default=2,
                    help="reruns per config (noise-floor detection)")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap the grid for a quick preview")
    ap.add_argument("--tmp", type=Path, default=Path("training/tmp_configs"))
    args = ap.parse_args()

    rows = build_grid(args.seeds)
    if args.limit:
        rows = rows[: args.limit]
    print(f"[ablation] {len(rows)} configs "
          f"({'LIVE — flash train will run' if args.live else 'dry-run'})")

    RESULTS.parent.mkdir(exist_ok=True)
    with RESULTS.open("w") as out:
        for i, row in enumerate(rows, 1):
            prev_ids: dict[str, str] = {}
            stage_metrics: dict[str, dict] = {}
            print(f"\n[{i}/{len(rows)}] {row.slug()}")
            paths = render_configs_for(row, args.tmp, prev_ids)
            try:
                for stage, path in zip(row.stack, paths):
                    print(f"  → stage {stage}: {path.name}")
                    if args.live:
                        run_id, metrics = run_flash_train(path)
                    else:
                        run_id, metrics = dry_run(path, row, stage)
                    prev_ids[stage] = run_id
                    stage_metrics[stage] = metrics
                final_stage = row.stack[-1]
                result = {
                    "config": row.slug(),
                    "base": row.base,
                    "rank": row.rank,
                    "stack": list(row.stack),
                    "thinking": row.thinking,
                    "seed": row.seed,
                    "final_eval": stage_metrics[final_stage],
                    "per_stage_ids": prev_ids,
                }
                out.write(json.dumps(result) + "\n")
                out.flush()
                print(f"  ✓ final: {result['final_eval']}")
            except Exception as e:
                print(f"  ✗ FAILED: {e}")
                out.write(json.dumps({"config": row.slug(), "error": str(e)}) + "\n")

    print(f"\n[ablation] results → {RESULTS}")
    _summarise(RESULTS)


def _summarise(results_path: Path) -> None:
    """Group by (base, rank, stack, thinking) and print mean±spread across seeds."""
    if not results_path.exists():
        return
    from collections import defaultdict
    groups: dict[tuple, list[float]] = defaultdict(list)
    for line in results_path.read_text().splitlines():
        r = json.loads(line)
        if "error" in r:
            continue
        key = (r["base"], r["rank"], tuple(r["stack"]), r["thinking"])
        groups[key].append(r["final_eval"].get("exact_pair_match", 0.0))
    print("\nbase                          rank stack                   think  n  mean   spread")
    print("─" * 90)
    for key, vals in sorted(groups.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        base, rank, stack, think = key
        mean = sum(vals) / len(vals)
        spread = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
        print(f"{base:30s} {rank:>4} {'-'.join(stack):23s} {int(think):>4}  {len(vals)}  {mean:.3f}  ±{spread:.3f}")


if __name__ == "__main__":
    main()
