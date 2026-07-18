# Plan That Trip to Japan — Project Reference

A Telegram bot that turns a group chat's stalled Japan trip into a virtual pet whose health is live hotel data. The only way to save the pet is to actually book.

This file is the shared context for the build. Read it before working on any component.

---

## 1. Concept

**Problem.** Everyone wants to go to Japan. It comes up in the group chat constantly — nobody ever goes. The trip stays a sentence: everyone means it, nobody coordinates, and it quietly dies.

**Product.** A bot lives in the group chat. It reads the conversation, extracts the trip taking shape (city, dates, budget, group size, vibe), and maintains a **virtual pet** with **two health bars**:

- **Physical health** — driven by live hotel market pressure from Stay22. Prices rising and availability dropping damage it. Procrastination literally makes it sick.
- **Mental health** — driven by group engagement. An active, deciding group keeps it happy; silence makes it depressed.

The pet declines visibly in the chat as the trip stalls on either axis. When the group commits, the pet graduates: Stay22 returns the hotel booking and Phoebe assembles the events/activities. The sentence becomes a booked trip.

---

## 2. Input / onboarding *(future)*

Each user onboards individually, in their own time — no one input is visible to the group until submitted, so preferences are independent rather than everyone agreeing with the first person to speak.

- **Experienced travelers** — asked directly for preferences (regions, budget, pace, must-dos).
- **New / unsure travelers** — handed a **Tinder-style map exploration**: swipe through suggested spots and experiences from the data pool. Swipes reveal preference without the user needing to know what they want.
- **Self-directed exploration** — a user who explores the map themselves is giving structured preference data the same way. A first-class input path, not a fallback.

All paths feed the same trip-state object that drives the pet and the Stay22 query. Progress is the goal — every input sharpens the trip and advances the pet.

---

## 3. Architecture — ours vs. dependencies

| Layer | What | Ownership |
|---|---|---|
| Live inventory | Stay22 API — prices/availability across Expedia, Booking, Hotels.com, Vrbo | Dependency (data source) |
| Chat → constraints | Parse group chat into `{city, dates, budget, size, vibe}` | Ours — the Brain |
| Preference aggregation | Reconcile conflicting per-person inputs into one plan | Ours — hardest part |
| Health engine | Two-axis health (physical + mental), delta-based decay | Ours |
| Pet render | Telegram bot + pet visual posted on state change | Ours |
| Events | Phoebe agent books/holds activities on commit | Phoebe SDK |

---

## 4. Build areas

1. **Read** — parse group chat → `{city, dates, budget, size}`, reconcile conflicting answers into one plan. *(Hardest; the Freesolo model lives here.)*
2. **Price** — pull live Stay22 price/availability → drive the physical bar → fire the real booking on commit.
3. **Nudge** — track chat engagement → drive the mental bar. Phoebe's home: nudges and books events to fight decay.
4. **Render** — run the Telegram bot, draw the pet's moods, post the updated image on every state change.
5. **Explore** — the onboarding split (experienced vs. new) and the Tinder-style map exploration input.
6. **Speak** — the pet's voice; the deathbed call to the chat when a bar bottoms out. Only after 1–4 work end to end.

Store group/pet/constraint state in MongoDB Atlas.

---

## 5. Health engine

Two independent bars, both delta-based. Poll on a heartbeat (live) or per time-step (demo); compare each poll to the last snapshot and apply damage/heal from the change.

**Physical (market-driven):**
```
Δavailability = (rooms_now − rooms_last) / rooms_last     # negative = worse
Δprice        = price_now − price_last                     # positive = worse

damage = wA * max(0, −Δavailability) + wP * max(0, Δprice)
heal   = wA * max(0,  Δavailability) + wP * max(0, −Δprice)

physical = clamp(physical − min(damage, DAMAGE_CAP) + heal, 0, 100)
```

**Mental (group-driven):** same shape, off chat-engagement deltas. Decays a fixed amount per period of silence; recovers on real decisions/activity.

- Baseline = first poll after constraints are set.
- `DAMAGE_CAP` keeps one bad swing from zeroing a bar.
- `heal` gives the pet good days, not just a countdown.
- Tune `wA`, `wP` so a ~5% availability drop or ~$15 price jump is a clearly visible hit.

---

## 6. Sponsor fit

- **Stay22** — hotel inventory *is* the pet's physical health, and it still books real commission on commit. Hotel data somewhere it has no business being, not a booking carousel.
- **Phoebe** — the bot is an AI teammate doing the coordination nobody volunteers for; it books events and fights mental decay. Automating a real-world workflow, its exact brief.
- **ElevenLabs** — the pet has a voice and calls the chat when dying; the un-muteable channel. Agentic, real-time dialogue, a novel use of conversational AI.
- **Freesolo** — post-train a small, efficient model for the Read layer (messy chat → clean constraints), bootstrapped from a larger model's outputs. Real post-training/distillation, and it raises technical difficulty on the main track.
- **Gemini** — offload simpler parsing/generation calls.
- **MongoDB Atlas** — group/pet/constraint state store.