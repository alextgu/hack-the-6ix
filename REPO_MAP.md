# REPO_MAP — one line per module, who calls what

**Live runtime** (imported by `bot.py` or `run.py`):

| Module        | What it does                                                                       | Imported by |
| ------------- | ---------------------------------------------------------------------------------- | ----------- |
| `bot.py`      | Telegram brain (python-telegram-bot v20). Handlers: `/start /health /scrub /commit /open`, message ingestion. Renders the in-chat pet PNG. | `run.py` (via `build_app`), standalone via `main()` |
| `run.py`      | Runs `bot.py` polling + `api.py` uvicorn in ONE asyncio loop so they share `state._GROUPS`. Supervisor loop restarts the bot on transient `TimedOut`. | user (`python run.py`) |
| `api.py`      | FastAPI — `GET /api/state/{group_id}` (reads shared state), serves `webapp/` static files with open CORS for the Telegram webview. | `run.py` |
| `state.py`    | In-memory per-group source of truth: `TripState`, `PetState`, `GroupState`, `MarketSnapshot`, `DateWindow`. `get_or_create` / `reset`. | `bot.py`, `api.py`, `wire.py`, `health.py` |
| `health.py`   | Two-bar delta formula (PROJECT.md §5). `apply_market_delta`, `apply_mental_delta`, `scrub_to_week`, `commit_trip`. Fake 6-week Stay22 series drives `/scrub`. | `bot.py`, `wire.py` |
| `pet.py`      | Pillow PNG renderer for the in-chat pet (5 mood tiers, two bars, dynamic caption). | `bot.py` |
| `wire.py`     | Live loop coordinator. Buffers messages, debounces `brain.extract` + `stay22.get_stay` calls, writes reconciled trip fields to `state`, stashes blockers (`city_tie` / `date_no_overlap` / `budget_missing`) for `phoebe` to consume. | `bot.py` |
| `brain.py`    | **Read seam — Gemini only, permanently** (PIPELINE.md). `call_model` → `extract(messages)` → `aggregate(...)`. Rule-based aggregators: `rule_budget_lowest`, `rule_dates_intersection`, `rule_city_majority`, `rule_group_size_distinct_speakers`, `rule_vibe_union`. | `wire.py`, standalone via `main()` |
| `stay22.py`   | Stay22 v2 client with 12s module-level throttle (keyless 5 req/min tier). `get_stay` returns `{price_median, price_cheapest, result_count}`; `search_raw` returns the full `results[]` array so `booking` can pick by rating. | `wire.py`, `booking.py` (via bot), standalone via `main()` |
| `booking.py`  | Commit → booking picker. `pick_hotel` picks the highest-rated within `budget × guests × nights` (fallback: cheapest). `booking_options` extracts Allez URLs verbatim from Stay22's response — never constructs them. Up to 2 alternates. | `bot.py::cmd_commit` |
| `phoebe.py`   | **Agent seam — Freesolo later** (PIPELINE.md). `agent_call` uses `FREESOLO_AGENT_BASE_URL`, falls back to Gemini for now. `diagnose(state)` → one `Blocker` (person/timing/issue). `decide_action(blocker, state)` → `Action`. `compose_message(action, state)` → outreach text. Scaffolded; not yet wired to the bot. | standalone via `main()` |
| `hotels.py`   | Stay22 → swipeable hotel deck: ≤5 real cards near the fixed basecamp (Shinjuku/Shibuya) with live prices/photos/ratings/Allez links. Fallback chain live → `data/japan_hotels.json` → `sample_response.json`. Shares stay22.py's throttle. | `cards.py` |
| `cards.py`    | Group decision engine for the deck. Round resolves when every participant swiped every active card; unanimous like wins (2+ people), else bottom half eliminated 5→3→2→1. In-memory truth, mirrored to Mongo. TEMP trigger: the word "map" in chat (`bot.log_message`); real seam: `bot.open_hotel_cards`. | `bot.py`, `api.py` |
| `db.py`       | MongoDB Atlas layer: `card_sessions` mirror + append-only `analytics` (swipe dwell/drag/velocity, card views, link-outs), plus `pets` (health persists across deploys), `chat_log` (full message memory), `user_profiles` (per-person facts), `trip_plans` (stage + flight lock). Never raises; retry cooldown + event buffering when Atlas flakes. | `cards.py`, `api.py`, `supervisor.py`, `state.py`, `bot.py` |
| `supervisor.py` | **LangGraph supervisor — the active pet** (SUPERVISOR_PLAN.md). Deterministic supervisor routes stage_tracker (code) + profile_tracker (Gemini) + messenger (Gemini-as-Tabi); sole send-gate with cooldowns. Stages GATHER → FLIGHTS → HOTELS → BOOK. | `bot.py`, `run.py` (heartbeat) |
| `flights.py`  | Mock flight stage: 3 stable fake options priced off budget; "flight N" in chat locks one. Deliberately fake per plan. | `bot.py`, `supervisor.py` |
| `webapp/`     | Telegram Mini App face — vanilla HTML/CSS/JS, Lottie animations per mood, polls `/api/state/{group_id}` every 3s. Served by `api.py` at `/` and `/webapp/*`. | Telegram (via WebApp button set by `bot.py`) |

**Reference / dev-only** (not imported at runtime):

| File                     | What it is |
| ------------------------ | ---------- |
| `stay22_probe.py`        | Standalone HTTP probe against Stay22's demo tier. Saves `sample_response.json`. Useful for eyeballing the response shape when the API changes. |
| `sample_response.json`   | A saved real Stay22 response from `stay22_probe.py`. Used to eyeball-test `booking.pick_hotel` offline. |
| `PROJECT.md`             | Product spec — concept, health engine, sponsor fit. Read first. |
| `PIPELINE.md`            | Two-seam model allocation. **Gemini = Read (`brain.py`). Freesolo = Agent (`phoebe.py`). Separate seams — never merge.** |
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
