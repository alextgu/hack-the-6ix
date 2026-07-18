# Plan That Trip to Japan — Project Reference

A Telegram bot that turns a group chat's stalled Japan trip into a virtual pet whose health is live hotel data. The only way to save the pet is to actually book.

This file is the shared context for the build. 
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
3. **Nudge** — track chat engagement → drive the mental bar. Phoebe's home: the diagnose-target-convince agent (§6) that finds the blocker and resolves it.
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

## 6. Phoebe agent — diagnose, target, convince

Trips don't die generically — they die from one specific blocker. A dumb bot nags the whole group; a good agent finds the single thing that's stuck and resolves only that. This is the core Phoebe loop, and it mirrors real Phoebe (triage the urgent thing, target the right person, get to yes).

**Diagnose — identify the one blocker.** Look at the trip state + chat and find the binding constraint. It's one of three:

1. **A person.** A holdout who hasn't confirmed and everyone's waiting on, or the person whose budget/dates are the binding constraint (e.g. their $1,200 cap sits below the group median, so no hotel fits everyone).
2. **Timing.** No overlapping date window, or the group keeps deferring while a price/availability deadline approaches.
3. **The exact issue.** Budget conflict, date conflict, destination split (Tokyo vs. Osaka), or pure decision paralysis — everyone agrees, nobody commits.

Finding the blocker is real analysis (which single constraint is binding), not a broadcast — that's the technical-difficulty story for this track.

**Target + convince — resolve that one thing, don't nag everyone.**

- Blocker is a *person* → DM them privately: "everyone's in on April 12–19, just need your yes."
- Blocker is *budget* → don't ask the group to spend more; propose the cheaper neighborhood that makes the low cap fit. Remove the objection instead of pushing on it.
- Blocker is *paralysis* → make the default: hold rooms for 48h, "someone say no" (the opt-out mechanic).

The mental health bar signals *that* there's friction; this agent determines *what and who*, then acts. Where possible it takes one real autonomous action (hold a room, DM the holdout, kick off onboarding) and hands the group a summary, not a task.

---

## 7. Sponsor fit — what each track contributes

Every track maps to a real part of the build. Nothing is bolted on. Format per track: **what it powers in the product → the angle that wins its track.**

**Stay22** — *powers:* the pet's physical health bar (live prices/availability) and the real booking on commit.
*Wins by:* using hotel inventory as a creature's vital sign instead of a search result — "data somewhere it has no business being," and it still books real commission. Never show a hotel list mid-game (that's the banned carousel); the hotel only surfaces at commit.

**Phoebe** — *powers:* the coordination agent (§6) — diagnose the one blocker (person / timing / issue), target the keystone, convince by removing the objection, hand the group a summary.
*Wins by:* mirroring real Phoebe's triage-and-resolve architecture and learning each friend's role from behavior (keystone targeting). Finding the binding constraint is real analysis, not a broadcast — that's the technical-difficulty story.

**ElevenLabs** *(bonus track — Sunday polish, not core)* — *powers:* the pet's voice.
*Voice style:* creature gibberish ("sushi sushi") with **real emotional inflection** — weak/sad when dying, bright when the trip's alive — plus a translated caption. Charm + their "emotional inflection" criterion at once.
*Wins by:* being a two-way agent, not one-way TTS — you can reply and it takes one real action (hold a room, kick off onboarding, DM the holdout). Two-way-ness wins the track, **not** a phone call — so no Twilio needed; do it in Telegram.
*Scope:* build only after the core loop works. If short on time, ship one-way voice as a touch and treat the track as a bonus.

**Freesolo** — *powers:* the Read layer (chat → trip constraints) and, ambitiously, the Phoebe persuasion agent itself.
*Wins by:* following their own SFT → GRPO recipe. SFT the constraint-extraction first (valid JSON via guided decoding) — that's the deployable floor. Then GRPO in a simulated friend-group environment with a *ground-truth* reward (did the sim group commit), scored per-turn, with held-out evals. Ground-truth reward beats the hackable LLM-judge everyone else will use. *(Workshop tomorrow — learn the environment/reward details there.)*

**MongoDB Atlas** — *powers:* all state — group, pet, per-person preferences, price/health history.
*Wins by:* using three differentiating features, not just storage. **Vector Search:** embed preferences, semantically match to Japan spots (powers Explore). **Time-series collections:** the health bars + price history are literally time-series (the scrubber replays them). **Change streams:** push live pet updates. "Not our database — our matching engine, the pet's memory, and its nervous system."

**Gemini** *(optional, not a target)* — *may power:* the teacher model that generates Freesolo's SFT training data, and a fallback before the tuned model exists.
*Not chasing its track:* Freesolo replaced the model work, so Gemini isn't central enough to win "Best Use of Gemini." Keep it as a quiet helper only.