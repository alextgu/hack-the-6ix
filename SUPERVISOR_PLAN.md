# Supervisor plan — the pet stops being passive

Tabi actively listens to everything, tracks the plan, and DECIDES when to
speak. A LangGraph supervisor orchestrates sub-agents; all outputs flow back
to it and it alone gates what reaches the chat.

## The journey (50% / 50%)

| Stage    | What must happen                                        | Who acts |
| -------- | ------------------------------------------------------- | -------- |
| GATHER   | first 50%: lock **dates + budget + city** from chat     | reader (brain.py/Gemini) fills TripState; pet chases missing pieces + silent people |
| FLIGHTS  | mock flight options posted; group picks one ("flight 2")| pet posts mock, regex locks the pick |
| HOTELS   | Stay22 card deck; swipe rounds converge on one hotel    | pet deals deck (cards.py) and nags stragglers |
| BOOK     | winner + /commit → real Stay22 Allez link               | existing booking.py |

## Graph (supervisor pattern, `supervisor.py`)

```
 on_message / on_heartbeat
        │
   ┌────▼──────┐   routes by what's still unknown; every
   │ SUPERVISOR │◄─ worker returns here; it alone decides
   └┬────┬────┬─┘   send / stay silent (cooldowns, dedupe)
    │    │    │
    │    │    └─► stage_tracker    deterministic: TripState + flight lock +
    │    │                         cards session → stage + missing fields
    │    └──────► profile_tracker  Gemini: extract per-user facts from new
    │                              messages → Mongo user_profiles
    └───────────► messenger        Gemini-as-Tabi: {send?, message, action}
                                   action ∈ none | deal_cards | post_flights
```

- **Supervisor is code, workers are LLM** — routing and the final send-gate
  stay deterministic and debuggable; the model does extraction + voice.
- Triggers: every wire.py debounce tick (≈3 msgs / 10s) and a heartbeat
  (run.py, every 10 min) so the pet can INITIATE when the chat goes quiet.

## Persistence (MongoDB — already in stack, `db.py`)

| Collection      | What                                              |
| --------------- | ------------------------------------------------- |
| `pets`          | physical/mental/mood/sim_week per chat — pet survives deploys now |
| `chat_log`      | every message, forever (the memory)               |
| `user_profiles` | per-user: budget, date prefs, cities, vibe, objections — "understand and track each user's request" |
| `trip_plans`    | stage, flight pick, decisions log                 |
| `card_sessions`, `analytics` | (already live)                       |

**RAG?** Not yet — one group chat fits in context; structured profiles +
rolling transcript beat embeddings at this scale. If recall over weeks of
chat is ever needed: Atlas Vector Search + Gemini embeddings, zero new infra.

## Done / TODO

- [x] LangGraph supervisor + 3 workers (this commit)
- [x] Pet health persisted + hydrated from Mongo
- [x] Chat log + user profiles collections
- [x] Mock flights stage + "flight N" lock
- [x] Heartbeat → pet initiates on silence
- [ ] DM the holdout privately (needs user_id capture per profile — logged)
- [ ] ElevenLabs voice note when pet hits 'dying'
- [ ] Freesolo post-trained model swap at the messenger seam (PIPELINE.md)
- [ ] Remove the temporary "map" trigger once demo-safe
