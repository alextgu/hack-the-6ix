"""Held-out eval harness — NEVER the reward. Grades any completer on
dataset/eval.jsonl: schema validity, gold-line token-F1, Tabi-voice rate,
length. Usage:

  python -m training.eval_harness --model gemini            # frontier baseline
  python -m training.eval_harness --model flash:<run-id>    # trained checkpoint
  python -m training.eval_harness --model flash:<run-id> --n 25 --tag sft-e3
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

EVAL = Path(__file__).parent / "dataset" / "eval.jsonl"
FLASH = str(_REPO / ".venv-flash" / "bin" / "flash")


def _extract_json(t: str):
    if not t:
        return None
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _metrics(msg: str, gold: str) -> dict:
    pt, gt = set(msg.lower().split()), set(gold.lower().split())
    f1 = (2 * len(pt & gt) / (len(pt) + len(gt))) if pt and gt else 0.0
    voice = bool(msg) and (msg[:1].islower() or msg[:1] in "@[") and msg.count("\n") <= 2
    return {"valid": bool(msg), "f1": f1, "voice": voice, "len": len(msg)}


def completer_gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp"))
    r = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"},
                               request_options={"timeout": 30})
    return r.text or ""


def completer_flash(run_id: str):
    env = {**os.environ}
    # .env's FREESOLO_API_KEY overrides the CLI's stored login and belongs to a
    # different account — strip it so the authed (org thesix) session is used.
    env.pop("FREESOLO_API_KEY", None)
    cb = subprocess.run([sys.executable, "-c", "import certifi;print(certifi.where())"],
                        capture_output=True, text=True).stdout.strip()
    env.update(SSL_CERT_FILE=cb, REQUESTS_CA_BUNDLE=cb)

    def _c(prompt: str) -> str:
        p = subprocess.run([FLASH, "chat", run_id, "-m", prompt, "--max-tokens", "200",
                            "--temperature", "0.2"],
                           capture_output=True, text=True, timeout=120, env=env)
        return p.stdout.strip()
    return _c


def run_eval(completer, n: int | None = None, tag: str = "",
             dump: str | None = None) -> dict:
    rows = [json.loads(l) for l in EVAL.read_text().splitlines() if l.strip()]
    if n:
        rows = rows[:n]
    agg = {"valid": 0, "f1": 0.0, "voice": 0, "len": 0, "errors": 0}
    per_example: list[dict] = []
    for i, r in enumerate(rows):
        gold = str((_extract_json(r["output"]) or {}).get("message", ""))
        try:
            out = completer(r["input"])
        except Exception as e:
            agg["errors"] += 1
            per_example.append({"i": i, "input": r["input"], "gold": gold,
                                "error": repr(e)[:200]})
            continue
        msg = str(((_extract_json(out) or {}).get("message")) or "").strip()
        m = _metrics(msg, gold)
        agg["valid"] += m["valid"]; agg["f1"] += m["f1"]
        agg["voice"] += m["voice"]; agg["len"] += m["len"]
        # Per-example record — the artifact anyone can open and re-score.
        per_example.append({"i": i, "input": r["input"], "gold": gold,
                            "raw": out, "message": msg, "metrics": m})
        if (i + 1) % 10 == 0:
            print(f"    …{i+1}/{len(rows)}", file=sys.stderr)
    k = len(rows) - agg["errors"] or 1
    res = {"tag": tag, "n": len(rows), "errors": agg["errors"],
           "schema_valid_pct": round(100 * agg["valid"] / k, 1),
           "gold_f1": round(agg["f1"] / k, 4),
           "voice_pct": round(100 * agg["voice"] / k, 1),
           "avg_len": round(agg["len"] / k)}
    if dump:
        dp = Path(dump)
        dp.parent.mkdir(parents=True, exist_ok=True)
        with dp.open("w") as f:
            # Line 1 = aggregate summary; remaining lines = one per example.
            f.write(json.dumps({"summary": res}) + "\n")
            for rec in per_example:
                f.write(json.dumps(rec) + "\n")
        print(f"    wrote {len(per_example)} rows → {dp}", file=sys.stderr)
    print(json.dumps(res))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="gemini | flash:<run-id>")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--tag", default="")
    ap.add_argument("--dump", default=None,
                    help="write per-example completions+scores to this .jsonl")
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(_REPO / ".env")
    except ImportError:
        pass
    comp = completer_gemini if a.model == "gemini" else completer_flash(a.model.split(":", 1)[1])
    run_eval(comp, a.n, a.tag or a.model, a.dump)
