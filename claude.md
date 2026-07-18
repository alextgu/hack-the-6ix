# CLAUDE.md

## Project
Plan That Trip to Japan — a Telegram bot that turns a group chat's stalled Japan trip into a virtual pet whose two health bars are driven by live hotel data (physical) and group engagement (mental). Committing to the trip saves the pet. (name might change in future)

## Read this first
**`PROJECT.md` is the current truth (could change).** Read it before working on anything — it covers the concept, onboarding, architecture, build areas, the health engine, and sponsor fit. Follow it over assumptions.

## Working rules
- Match the build areas and ownership in `PROJECT.md` §3–4. Don't merge or reinvent components.
- Keep the LLM/extraction call isolated and swappable (a Freesolo model replaces it later).
- Placeholder art is fine — a designer owns the real pet visuals.
- Keep state in MongoDB Atlas per `PROJECT.md`.
- If a change contradicts `PROJECT.md`, flag it rather than silently diverging.

## Scope
The failure mode is many half-built lanes. Protect the core loop (chat → constraints → Stay22 → pet) above new surfaces.