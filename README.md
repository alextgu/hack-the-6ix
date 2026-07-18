# trippet — Plan That Trip to Japan

A Telegram bot whose group's stalled Japan trip is turned into a virtual pet
with two health bars. See `PROJECT.md` for the concept, `CLAUDE.md` for
working rules.

Working name: **trippet** (not permanent).

## Layout

See `REPO_MAP.md` for a one-line-per-module map + who calls what.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env       # then edit: TELEGRAM_BOT_TOKEN, PUBLIC_WEBAPP_URL
```

**BotFather setup (once):** `/mybots` → your bot → *Bot Settings* → *Group
Privacy* → **Turn off** (so the bot sees plain messages, not just commands).

## Run

Two options:

```bash
# A) Bot only (no Mini App)
./.venv/bin/python bot.py

# B) Bot + Mini App face (recommended — this is the whole product)
./.venv/bin/python run.py     # binds :8000; set PORT=xxxx to override
```

## Exposing the Mini App over HTTPS (required by Telegram)

Telegram Mini Apps must load from an HTTPS URL. In development, tunnel your
local FastAPI port. Any of these work:

```bash
# cloudflared (recommended — no signup)
brew install cloudflared
cloudflared tunnel --url http://localhost:8000

# ngrok
ngrok http 8000
```

Copy the resulting `https://...` URL and put it in `.env` as
`PUBLIC_WEBAPP_URL`, then restart `run.py`. Now `/start` and `/open` will
send buttons that launch the Mini App.

You can preview the Mini App standalone (outside Telegram) by opening
`http://localhost:8000/?group=12345` — it degrades gracefully when the
Telegram SDK isn't present.

## Commands

| Command       | What it does |
| ------------- | ------------ |
| `/start`      | Hatch/reset the pet, post its PNG, offer the Mini App button |
| `/health`     | Repost the current pet PNG + numbers |
| `/scrub N`    | Dev — jump the simulated timeline to week 0..6 (drives both bars) |
| `/commit`     | Both bars back to full — graduated pet |
| `/open`       | Send just the Mini App button |

## The state seam

Everything reads/writes `state._GROUPS[chat_id]`. TODO seams for MongoDB
Atlas, the LLM Read layer, the Nudge engagement counter, Phoebe, and voice
are marked inline. The FastAPI face never computes health — it only displays
what the bot wrote.
