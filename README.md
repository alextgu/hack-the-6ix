# trippet — Plan That Trip to Japan

A Telegram bot that turns a group chat's stalled Japan trip into a virtual pet
with two health bars: **physical** (live Stay22 hotel-market pressure) and
**mental** (group engagement). The pet visibly rots the longer the group
stalls; the only way to save it is to actually book. See `PROJECT.md` for the
concept and `PIPELINE.md` for the model seams; `REPO_MAP.md` maps each module.

## Layout

```
run.py            entry point — bot polling + FastAPI Mini App in ONE asyncio loop
app/
  bot/            Telegram handlers + the wire (chat → constraints → health)
  agents/         supervisor (LangGraph "Tabi"), brain (Gemini Read), face, greenplanner
  integrations/   stay22, booking, db (Mongo), flights, green, elevenlabs, solana_coin, telegram_avatar
  api/            FastAPI — pet-state endpoint + serves the Mini App
  render/         Pillow pet card + tami sprite resolver
  core/           in-memory state + the two-bar health engine
webapp/           Telegram Mini App (vanilla HTML/JS, served by FastAPI)
landing/          public showcase (Next.js, static-exported to Netlify)
training/         Freesolo Flash pipeline (SFT → OPD → GRPO) for the messenger model
solana/           devnet "Japan Trip Coin" mint (Node; called by solana_coin.py)
design-system/    shared CSS tokens (bot render + landing + webapp share one look)
assets/           pet sprites, fonts, coin art
data/             Stay22 fixture (offline fallback)
_graveyard/       removed-but-kept-for-review — see the cleanup report, not shipped
```

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env      # fill in the keys you have; each integration fails safe if its key is missing
```

Also needs **ffmpeg** on PATH (ElevenLabs voice notes → OGG/Opus) and, for the
souvenir coin, **Node** (the `solana/` mint script). Both degrade to text/skip
if absent.

**BotFather (once):** `/mybots` → your bot → *Bot Settings* → *Group Privacy* →
**Turn off** so the bot sees plain group messages.

## Run

```bash
# Bot + Mini App in one process (the whole product)
./.venv/bin/python run.py            # binds :8000; PORT=xxxx to override

# Landing showcase (separate, static)
cd landing && npm install && npm run dev
```

Runs with no `TELEGRAM_BOT_TOKEN` in **API-only mode** (Mini App serves, no
polling). Every external integration is fail-open: Mongo/Stay22/Gemini/
ElevenLabs/Solana down → the core loop keeps running.

### Mini App over HTTPS (Telegram requirement)

Telegram Mini Apps load from HTTPS. In dev, tunnel the FastAPI port and put the
URL in `.env` as `PUBLIC_WEBAPP_URL`:

```bash
cloudflared tunnel --url http://localhost:8000    # or: ngrok http 8000
```

Preview standalone (no Telegram) at `http://localhost:8000/?group=12345`.

## Commands

| Command | What it does |
| --- | --- |
| `/start` | Hatch/wake the pet, post its card, offer the Mini App button |
| `/health` | Repost the current pet card + numbers |
| `/scrub N` | Dev — jump the simulated timeline to week 0..6 (drives both bars) |
| `/commit` | Graduation finale — real Stay22 booking, green stats, voice, trip coin |
| `/saved` | Green ledger: CO₂e avoided so far, in human units |
| `/itinerary` | Green-routed day-by-day plan |
| `/open` | Send just the Mini App button |
| `/stop` · `/resume` | Mute / un-mute the pet in this chat |
| `/reset` | Erase everything the bot knows about the group |

The pet also acts on plain chat: it reads the conversation, reconciles each
person's constraints, and speaks up (once past its send-gate + cooldown) only
when a self-scored candidate thought clears threshold.

## Deploy

- **Bot + API** → Docker → Google Cloud Run (`Dockerfile`, `DEPLOY.md`; CI in
  `.github/workflows/deploy.yml`). One instance — state is shared in-process.
- **Landing** → Netlify static export (`netlify.toml`: base `landing`, publish `out`).

## Model seams (see `PIPELINE.md`)

- **Read** — Gemini turns group chat into structured trip constraints (never swapped).
- **Messenger** — the pet's voice. Runs a **Freesolo-trained Qwen3.5-4B** (SFT→GRPO,
  deployed) when `FREESOLO_AGENT_BASE_URL` is set; falls back to Gemini on any error.
  The `training/` pipeline builds its dataset from real logged interactions (Mongo flywheel).
