# Kamagachi

A gamified group-travel coordination system that lives inside a Telegram group chat.
The pet dies unless the group actually finishes planning and booking a trip to Japan.

The core objective isn't "build a hotel search." It's peak-unhinged, big-brain use of
the [Stay22 API](https://dev.stay22.com/) — Stay22 is load-bearing across the entire
product: it drives the swipe deck, the health decay (market pressure), the monetized
booking deep-links, and the conversion telemetry.

## The story

1. Group chat → bot introduces the pet (already dying).
2. People talk chaotically. Consensus engine reconciles budget + group size + a
   multi-city itinerary. Each locked constraint **heals the pet**.
3. At 50% health the pet drops a **Telegram Mini App swipe deck** — real hotels
   from Stay22, one city at a time, sequentially unlocked.
4. **Unanimous swipe** → Stay22 `Allez` monetized deep-link → the pet gets happy.
5. Background poller hits the **Stay22 reporting API**; when `Bookings > 0` for
   the chat's affiliate token, the pet hits 100% (golden mustache).
6. If the group stalls OR market data moves against them (price spike / rooms
   selling), the pet **takes damage** and can escalate to an **ElevenLabs voice
   note** that names names.

## Stack

Python 3.13 · FastAPI · aiogram · MongoDB Atlas (or in-memory fallback) ·
Stay22 v2 · Gemini · ElevenLabs · vanilla-JS Telegram Mini App

## Run

```bash
cd kamagachi
./scripts/setup.sh              # creates .venv, installs deps
./scripts/run.sh                # boots FastAPI on :8000 (uvicorn --reload)
# In another terminal, expose the port so Telegram can hit the webhook:
./scripts/tunnel.sh             # cloudflared or ngrok
# Update PUBLIC_BASE_URL in .env with the public URL, then restart run.sh
```

## Standalone mini-app demo (no bot)

```bash
./scripts/run.sh
python -m kamagachi.scripts.seed_demo   # creates 'demo-chat' trip
open http://localhost:8000/miniapp/?chat_id=demo-chat
```

## Standalone pet visual test

Open `kamagachi/app/static/pet/pet.html` in a browser (must be served over HTTP
because it `fetch`es the SVG). Easiest: `./scripts/run.sh` and visit
`http://localhost:8000/static/pet/pet.html`.

## Environment

Only two of these are strictly required to see the loop work:

| Key | Required? | Notes |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | for Telegram | from BotFather. Disable Privacy Mode. |
| `STAY22_API_KEY` | for real inventory | else the demo uses seeded fake hotels. |
| `STAY22_AFFILIATE_ID` | for real commission | else `kamagachi` (test aid). |
| `MONGODB_URI` | prod path | in-memory fallback boots without it. |
| `GEMINI_API_KEY` | for smart consensus | rule-based fallback works without it. |
| `ELEVENLABS_API_KEY` | for the voice call | falls back to plain text messages. |
| `PUBLIC_BASE_URL` | for Telegram webhook + Mini App | e.g. from cloudflared. |

Full template: `../.env.example`.

## Architecture

Event-Driven Service Pattern. `services/events.py` is a tiny async pub/sub bus.
Every plugin registers as a subscriber — the core engine and DB schema never need
to change to add a capability.

Layers:

| # | Layer | Files |
| - | ----- | ----- |
| 1 | Telegram ingestion | `bot/telegram.py` |
| 2 | Consensus (Gemini + rule fallback) | `services/consensus.py` |
| 3 | Deck + Stay22 sourcing | `services/deck.py`, `services/stay22.py` |
| 4 | Gamification + market decay | `services/health.py` |
| 5 | Events / activities (Phoebe) | *(hook only; teammate builds source)* |
| 6 | Voice (ElevenLabs) | `services/voice.py` |
| — | Vector ranking | `services/preferences.py` |
| — | Time-series | `storage/repo.py` (Mongo timeseries collections) |
| — | Mini App (swipe UI) | `app/miniapp/` |
| — | Pet visual + animations | `app/static/pet/` |

## Tune the feel

Every gamification number is in `app/config.py::Gamification`. Tune live.

## What's intentionally missing

- Phoebe events source (activity/food/ticket data feed) — interface is clean and
  ready in `events_collection` + a stub service module can drop in.
- Freesolo replacement — consensus works via Gemini + regex fallback; swap in
  when ready.
