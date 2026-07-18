#!/usr/bin/env bash
# Expose the local server publicly so Telegram can hit the webhook.
# Requires `cloudflared` (brew install cloudflared) OR `ngrok`.
set -euo pipefail
PORT="${PORT:-8000}"
if command -v cloudflared >/dev/null; then
  exec cloudflared tunnel --url "http://localhost:${PORT}"
elif command -v ngrok >/dev/null; then
  exec ngrok http "$PORT"
else
  echo "install cloudflared or ngrok first"; exit 1
fi
