#!/usr/bin/env bash
# One-shot dev setup. Creates a venv and installs deps.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
echo "✓ venv ready. run ./scripts/run.sh"
