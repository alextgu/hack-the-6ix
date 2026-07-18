# REPO_MAP — one line per module, who calls what

## Layout

```
run.py                     entry point — python run.py (bot polling + api in one loop)
app/
  bot/        bot.py  wire.py  cards.py            Telegram + orchestration + deck engine
  core/       state.py  health.py                  in-memory state + two-bar mechanics
  agents/     brain.py  phoebe.py  gemini.py        LLM seams (Read = Gemini, Agent = Freesolo)
  integrations/ stay22.py  booking.py  hotels.py  db.py   external APIs (Stay22, MongoDB)
  render/     pet.py                                Pillow in-chat pet PNG
  api/        api.py                                FastAPI state endpoint + webapp static
webapp/                    Telegram Mini App (vanilla HTML/CSS/JS)
training/                  Freesolo post-training scaffold (SFT → OPD → GRPO)
data/  sample_response.json   Stay22 fixtures (loaded by app/integrations/hotels.py)
stay22_probe.py            dev-only Stay22 HTTP probe (regenerates sample_response.json)
```

Imports use absolute package paths (`from app.core import state`). Run from the
repo root so `app` is importable: `python run.py`, or standalone entry points via
`python -m app.agents.brain`, `python -m app.bot.bot`.

**Live runtime** (imported by `run.py` or `app/bot/bot.py`):

| Module                     | What it does                                                                       | Imported by |
| -------------------------- | ---------------------------------------------------------------------------------- | ----------- |
| `run.py`                   | Runs `app/bot/bot.py` polling + `app/api/api.py` uvicorn in ONE asyncio loop so they share `state._GROUPS`. Supervisor loop restarts the bot on transient `TimedOut`. | user (`python run.py`) |
| `app/bot/bot.py`           | Telegram brain (python-telegram-bot v20). Handlers: `/start /health /scrub /commit /open`, message ingestion. Renders the in-chat pet PNG. | `run.py` (via `build_app`), standalone via `python -m app.bot.bot` |
| `app/api/api.py`           | FastAPI — `GET /api/state/{group_id}` (reads shared state), serves `webapp/` static files with open CORS for the Telegram webview. `ROOT` resolves to repo root. | `run.py` |
| `app/core/state.py`        | In-memory per-group source of truth: `TripState`, `PetState`, `GroupState`, `MarketSnapshot`, `DateWindow`. `get_or_create` / `reset`. | `bot`, `api`, `wire`, `health`, `pet` |
| `app/core/health.py`       | Two-bar delta formula (PROJECT.md §5). `apply_market_delta`, `apply_mental_delta`, `scrub_to_week`, `commit_trip`. Fake 6-week Stay22 series drives `/scrub`. | `bot`, `wire` |
| `app/render/pet.py`        | Pillow PNG renderer for the in-chat pet (5 mood tiers, two bars, dynamic caption). | `bot` |
| `app/bot/wire.py`          | Live loop coordinator. Buffers messages, debounces `brain.extract` + `stay22.get_stay` calls, writes reconciled trip fields to `state`, stashes blockers (`city_tie` / `date_no_overlap` / `budget_missing`) for `phoebe` to consume. | `bot` |
| `app/agents/brain.py`      | **Read seam — Gemini only, permanently** (PIPELINE.md). `call_model` → `extract(messages)` → `aggregate(...)`. Rule-based aggregators. | `wire`, standalone via `python -m app.agents.brain` |
| `app/integrations/stay22.py` | Stay22 v2 client with 12s module-level throttle (keyless 5 req/min tier). `get_stay` returns `{price_median, price_cheapest, result_count}`; `search_raw` returns the full `results[]` array so `booking` can pick by rating. | `wire`, `hotels`, `booking` (via bot), standalone |
| `app/integrations/booking.py` | Commit → booking picker. `pick_hotel` picks the highest-rated within `budget × guests × nights` (fallback: cheapest). `booking_options` extracts Allez URLs verbatim from Stay22 — never constructs them. | `app/bot/bot.py::cmd_commit` |
| `app/bot/cards.py`         | Group decision engine for the deck. Round resolves when every participant swiped every active card; unanimous like wins (2+ people), else bottom half eliminated 5→3→2→1. In-memory truth, mirrored to Mongo. TEMP trigger: the word "map" in chat; real seam: `bot.open_hotel_cards`. | `bot`, `api` |
| `app/integrations/hotels.py` | Stay22 → swipeable hotel deck: ≤5 real cards near the fixed basecamp (Shinjuku/Shibuya) with live prices/photos/ratings/Allez links. Fallback chain live → `data/japan_hotels.json` → `sample_response.json` (paths resolve to repo root). | `cards` |
| `app/integrations/db.py`   | MongoDB Atlas layer: `card_sessions` mirror + append-only `analytics` (swipe dwell/drag/velocity, card views, link-outs). Never raises; retry cooldown + event buffering when Atlas flakes. `pymongo` imported lazily. | `cards`, `api` |
| `webapp/`                  | Telegram Mini App face — vanilla HTML/CSS/JS, Lottie animations per mood, polls `/api/state/{group_id}` every 3s. Served by `app/api/api.py` at `/` and `/webapp/*`. | Telegram (via WebApp button set by `bot`) |

**Scaffolded — not yet wired to the bot** (agent seam, PIPELINE.md):

| Module                | What it is |
| --------------------- | ---------- |
| `app/agents/phoebe.py`  | **Agent seam — Freesolo later.** `agent_call` uses `FREESOLO_AGENT_BASE_URL`, falls back to Gemini for now. `diagnose(state)` → one `Blocker`; `decide_action(blocker, state)` → `Action`; `compose_message(action, state)` → outreach text. Standalone via `python -m app.agents.phoebe`. |
| `app/agents/gemini.py`  | **Multimodal per-message pipeline** (PROJECT.md §6) — distinct from `brain.py`: reads messages ONE at a time (text + photo/OCR), timestamps + classifies each as a blocker signal so Phoebe sees *who* said *what*, *when*. `call_model` is the single swappable LLM call. Standalone via `python -m app.agents.gemini`. Not yet imported by the bot. |

**Reference / dev-only** (not imported at runtime):

| File                     | What it is |
| ------------------------ | ---------- |
| `stay22_probe.py`        | Standalone HTTP probe against Stay22's demo tier. Saves `sample_response.json`. Useful for eyeballing the response shape when the API changes. |
| `sample_response.json`   | A saved real Stay22 response from `stay22_probe.py`. Used to eyeball-test `booking.pick_hotel` offline. |
| `PROJECT.md`             | Product spec — concept, health engine, sponsor fit. Read first. |
| `PIPELINE.md`            | Two-seam model allocation. **Gemini = Read (`app/agents/brain.py`). Freesolo = Agent (`app/agents/phoebe.py`). Separate seams — never merge.** |
| `claude.md`              | Claude Code working rules for this repo. |
| `README.md`              | Setup + run instructions. |
| `.claude/agents/code-worker.md` | Opus sub-agent profile for implementation/refactor tasks. |

**Env vars (grouped by owner):**

- **Telegram / Mini App:** `TELEGRAM_BOT_TOKEN`, `PUBLIC_WEBAPP_URL`
- **Stay22:** `STAY22_API_KEY`, `STAY22_AID` (both `stay22.py` and `booking.py` inherit the AID transparently via URL passthrough)
- **Read (Gemini):** `GEMINI_API_KEY`, `GEMINI_MODEL`
- **Agent (Freesolo, later):** `FREESOLO_API_KEY`, `FREESOLO_AGENT_BASE_URL`, `FREESOLO_AGENT_MODEL`
- **Voice (later, ElevenLabs):** `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_DYING`, `ELEVENLABS_VOICE_ALIVE`
- **MongoDB (cards + analytics):** `MONGODB_URI`, `MONGODB_DB`

**Data flow (linear, one direction):**

```
messages → bot.log_message → wire.note_message
                                ↓ (debounce)
                             brain.extract (Gemini) → brain.aggregate
                                ↓
                             state.TripState + wire._blockers
                                ↓
                             stay22.get_stay (rate-guarded)
                                ↓
                             health.apply_market_delta → pet.physical
                                ↓
/commit → stay22.search_raw → booking.pick_hotel → booking.booking_options
                                ↓
                             Telegram inline URL button (real Allez link)

phoebe.diagnose(state) → phoebe.decide_action → phoebe.compose_message   [scaffolded; not yet wired]
```
