# Tabi — Plan That Trip to Japan

**Everyone wants to go to Japan. It comes up in the group chat constantly — nobody ever goes.** The trip stays a sentence: everyone means it, nobody coordinates, and it quietly dies.

**Tabi** is a Telegram bot that turns that stalled group chat into a **virtual pet** with two health bars. The pet visibly rots the longer the group stalls — and the only way to save it is to actually book the trip.

- 🩺 **Physical health** — driven by **live Stay22 hotel-market pressure**. Prices rising and availability dropping damage the pet. Procrastination literally makes it sick.
- 🧠 **Mental health** — driven by **group engagement**. An active, deciding group keeps it happy; silence makes it depressed.

When the group finally commits, the pet graduates: Stay22 returns the real hotel booking, the green engine tallies the CO₂e saved, the pet says goodbye in its own voice, and a souvenir "Japan Trip Coin" is minted. The sentence becomes a booked trip.

### 🔗 Links

- **Live showcase → https://hack-the-6ix.netlify.app/**
- **Devpost → https://devpost.com/software/a-nhsi8g**

Built at **Hack the 6ix**. Read `PROJECT.md` for the full concept, `REPO_MAP.md` for a module-by-module map, and `PIPELINE.md` for the model seams.

---

## How it works

A single asyncio process runs the Telegram bot and a FastAPI server together, sharing in-process state so the bot and the Mini App always agree.

```
messages → Read (Gemini) extracts {city, dates, budget, size, vibe}
                ↓
         reconcile per-person constraints into one plan
                ↓
         Stay22 live prices/availability → physical health bar
         chat engagement deltas          → mental health bar
                ↓
         pet re-renders in chat on every state change
                ↓
/commit → real Stay22 booking + green tally + voice goodbye + trip coin
```

The pet also acts on plain chat: it reads the conversation, reconciles each person's constraints, and speaks up (once past its send-gate + cooldown) only when a self-scored candidate thought clears threshold — it's a LangGraph supervisor, not a keyword bot.

---

## What's built

| Area | What it does | Stack |
| --- | --- | --- |
| **Read** | Group chat → structured trip constraints `{city, dates, budget, size, vibe}`, then reconcile conflicting per-person inputs into one plan | Gemini (`app/agents/brain.py`) — permanent seam |
| **The pet (supervisor)** | LangGraph supervisor "Tabi" routes stage-tracker (code) + profile-tracker + messenger; sole send-gate w/ cooldown; stages GATHER → FLIGHTS → HOTELS → BOOK; heartbeat lets the pet initiate after silence | LangGraph (`app/agents/supervisor.py`) |
| **Physical bar** | Live Stay22 v2 client (rate-guarded), two-bar delta health engine; fake 6-week price series drives the `/scrub` demo | `app/integrations/stay22.py`, `app/core/health.py` |
| **Booking** | On commit, picks the highest-rated hotel within `budget × guests × nights`, extracts real Allez booking URLs verbatim from Stay22 (never constructs them) | `app/integrations/booking.py` |
| **Hotel deck** | Swipeable "map" card deck of ≤5 real hotels near a fixed basecamp; group decision engine resolves rounds by unanimous-like / bottom-half elimination | `app/bot/cards.py`, `app/integrations/hotels.py` |
| **Render** | Pillow in-chat pet PNG (5 mood tiers, two bars, dynamic caption) | `app/render/pet.py` |
| **Mini App** | Telegram WebApp face — vanilla HTML/CSS/JS, Lottie animations per mood, polls `/api/state/{group_id}` every 3s | `webapp/`, served by FastAPI |
| **Flights** | Flight options with fallback chain (Amadeus test API → fixture → mock); each option enriched with locally-computed CO₂e, lowest flagged 🌱; "flight N" locks one | `app/integrations/flights.py` |
| **Green engine** | All carbon math + a savings ledger (DEFRA/CHSB/JR/EPA local constants — no network call can break a number); `/saved` shows CO₂e avoided in human units; `/itinerary` builds a green-routed day-by-day plan | `app/integrations/green.py`, `app/agents/greenplanner.py` |
| **Voice** | The pet's ElevenLabs voice — creature gibberish with real emotional inflection (weak when dying, bright when alive) + translated caption; two-way, degrades to text | ElevenLabs, ffmpeg |
| **Souvenir coin** | Devnet SPL mint for the "Japan Trip Coin" on commit — never touches mainnet | Node, `@solana/web3.js` (`solana/mint.mjs`) |
| **State** | MongoDB Atlas as matching engine + memory + nervous system: analytics/swipe telemetry, pets (health survives deploys), chat log, per-person profiles, trip plans | `app/integrations/db.py` |
| **Auth (scaffold)** | Complete Auth0 SPA login layer, kept deliberately isolated — ready to gate the Mini App or an admin view, not yet wired | `auth0/` (`@auth0/auth0-spa-js`) |
| **Landing** | Public showcase site, static-exported to Netlify | Next.js 16 + React 19 + Tailwind 4 (`landing/`) |
| **Training** | Freesolo Flash post-training scaffold (SFT → OPD → GRPO) for the messenger model, dataset built from real logged interactions (Mongo flywheel) | `training/` |
| **Design system** | Shared CSS tokens so bot render, landing, and Mini App share one look | `design-system/` |

### Health engine

Two independent bars, both delta-based. Poll on a heartbeat (live) or per time-step (demo); compare each poll to the last snapshot and apply damage/heal from the change. A `DAMAGE_CAP` keeps one bad swing from zeroing a bar; `heal` gives the pet good days, not just a countdown. See `PROJECT.md` §5 for the formula.

---

## Layout

```
run.py            entry point — bot polling + FastAPI Mini App in ONE asyncio loop
app/
  bot/            Telegram handlers + the wire (chat → constraints → health) + card deck
  agents/         supervisor (LangGraph "Tabi"), brain (Gemini Read), phoebe (agent seam), greenplanner
  integrations/   stay22, booking, hotels, flights, green, db (Mongo), elevenlabs, solana_coin
  api/            FastAPI — pet-state endpoint + serves the Mini App
  render/         Pillow pet card
  core/           in-memory state + the two-bar health engine
webapp/           Telegram Mini App (vanilla HTML/JS, served by FastAPI)
landing/          public showcase (Next.js 16, static-exported to Netlify)
training/         Freesolo Flash pipeline (SFT → OPD → GRPO) for the messenger model
solana/           devnet "Japan Trip Coin" mint (Node; called by app/integrations)
auth0/            isolated Auth0 login scaffold (ready to adopt, not yet wired)
design-system/    shared CSS tokens (bot render + landing + webapp share one look)
assets/           pet sprites, fonts, coin art
data/             Stay22 + flight fixtures (offline fallback)
```

Imports use absolute package paths (`from app.core import state`); run from the repo root.

---

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env      # fill in the keys you have; each integration fails safe if its key is missing
```

Also needs **ffmpeg** on PATH (ElevenLabs voice notes → OGG/Opus) and, for the souvenir coin, **Node** (the `solana/` mint script). Both degrade to text/skip if absent.

**BotFather (once):** `/mybots` → your bot → *Bot Settings* → *Group Privacy* → **Turn off** so the bot sees plain group messages.

## Run

```bash
# Bot + Mini App in one process (the whole product)
./.venv/bin/python run.py            # binds :8000; PORT=xxxx to override

# Landing showcase (separate, static)
cd landing && npm install && npm run dev
```

Runs with no `TELEGRAM_BOT_TOKEN` in **API-only mode** (Mini App serves, no polling). Every external integration is fail-open: Mongo / Stay22 / Gemini / ElevenLabs / Amadeus / Solana down → the core loop keeps running. Carbon numbers are pure local math, so `/saved` answers even fully offline.

### Mini App over HTTPS (Telegram requirement)

Telegram Mini Apps load from HTTPS. In dev, tunnel the FastAPI port and put the URL in `.env` as `PUBLIC_WEBAPP_URL`:

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
| `/silence N` | Dev — simulate N ignored nudges; watch mental drop without waiting out real silence |
| `/commit` | Graduation finale — real Stay22 booking, green stats, voice, trip coin |
| `/end` | Dev — 'we're in Japan': graduation + Solana trip coin, skips the live Stay22 search |
| `/saved` | Green ledger: CO₂e avoided so far, in human units |
| `/itinerary` | Green-routed day-by-day plan |
| `/open` | Send just the Mini App button |
| `/stop` · `/resume` | Mute / un-mute the pet in this chat |
| `/reset` | Erase everything the bot knows about the group |

## Deploy

- **Bot + API** → Docker → Google Cloud Run (`Dockerfile`, `DEPLOY.md`; CI in `.github/workflows/deploy.yml`). One instance — state is shared in-process.
- **Landing** → Netlify static export (`netlify.toml`: base `landing`, publish `out`).

## Model seams (see `PIPELINE.md`)

- **Read** — Gemini turns group chat into structured trip constraints (never swapped).
- **Messenger / Agent** — the pet's voice and the coordination agent (`app/agents/phoebe.py`). Runs a **Freesolo-trained** model when `FREESOLO_AGENT_BASE_URL` is set; falls back to Gemini on any error. The `training/` pipeline builds its dataset from real logged interactions (Mongo flywheel).

## Sponsor fit

Every track maps to a real part of the build — nothing bolted on. **Stay22** is the pet's physical vital sign and the real booking on commit; **MongoDB Atlas** is the matching engine, memory, and nervous system (analytics, vector-ready preferences, time-series health/price, change-ready pet updates); **Freesolo** trains the Read + agent seams via SFT → GRPO; **ElevenLabs** gives the pet a two-way emotional voice; **Auth0** is a ready-to-adopt login layer; **Solana** mints the souvenir trip coin. See `PROJECT.md` §7 for the full mapping.
