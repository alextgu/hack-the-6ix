/**
 * Sushi-kun demo model — a faithful TypeScript port of the Python backend's
 * canonical logic (the repo had no landing.html, so this is ported from source):
 *   - health.py  → _MARKET_SERIES, apply_market_delta, scrub_to_week, mental decay
 *   - state.py   → derive_mood thresholds
 *   - pet.py     → _caption() dialogue + MOOD_COLORS
 *
 * Pure functions, no React — imported by the client demo component.
 */

export type Mood = "happy" | "worried" | "sick" | "dying" | "graduated";

export interface Snapshot {
  price: number; // 時価 — avg hotel price (USD)
  rooms: number; // availability proxy (arbitrary units; only ratios matter)
}

// health.py::_MARKET_SERIES — prices trending up, availability down, with dips
// at weeks 2 & 4 so the pet visibly recovers on the "good weeks".
export const MARKET: Snapshot[] = [
  { price: 200, rooms: 100 }, // week 0 baseline
  { price: 214, rooms: 88 }, // week 1 rising, filling
  { price: 206, rooms: 92 }, // week 2 GOOD WEEK
  { price: 232, rooms: 80 }, // week 3 bad
  { price: 227, rooms: 84 }, // week 4 small good week
  { price: 248, rooms: 72 }, // week 5 rough
  { price: 263, rooms: 65 }, // week 6 final squeeze
];

export const MAX_WEEK = MARKET.length - 1;

// health.py tuning constants (verbatim).
const WEIGHT_AVAILABILITY = 200.0;
const WEIGHT_PRICE_USD = 0.7;
const DAMAGE_CAP = 25;
const MENTAL_DECAY_PER_WEEK = 12;

// health.py::apply_market_delta — capped damage on the bad side, uncapped heal.
export function applyMarketDelta(physical: number, prev: Snapshot, curr: Snapshot): number {
  const dAvail = (curr.rooms - prev.rooms) / Math.max(1.0, prev.rooms);
  const dPrice = curr.price - prev.price;

  const damage = WEIGHT_AVAILABILITY * Math.max(0, -dAvail) + WEIGHT_PRICE_USD * Math.max(0, dPrice);
  const heal = WEIGHT_AVAILABILITY * Math.max(0, dAvail) + WEIGHT_PRICE_USD * Math.max(0, -dPrice);

  const next = physical - Math.min(damage, DAMAGE_CAP) + heal;
  return Math.max(0, Math.min(100, Math.round(next)));
}

// state.py::derive_mood
export function deriveMood(physical: number, mental: number): Mood {
  const avg = (physical + mental) / 2;
  if (avg > 70) return "happy";
  if (avg > 45) return "worried";
  if (avg > 20) return "sick";
  return "dying";
}

export interface PetSnapshot {
  week: number;
  physical: number;
  mental: number;
  price: number;
  rooms: number;
  mood: Mood;
  caption: string;
}

// health.py only defines physical at whole weeks. Precompute those 7 points
// once so stateAtWeek can lerp between them for fractional weeks — lets the
// landing-page slider scrub continuously instead of jumping between 7 fixed
// stops (several of which land in the same sushi/face bucket back to back).
const PHYSICAL_AT_WEEK: number[] = (() => {
  const out = [100];
  let physical = 100;
  let prev = MARKET[0];
  for (let i = 1; i <= MAX_WEEK; i++) {
    physical = applyMarketDelta(physical, prev, MARKET[i]);
    prev = MARKET[i];
    out.push(physical);
  }
  return out;
})();

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

// health.py::scrub_to_week — physical replays the market series 0 → week,
// mental decays linearly with silence. `week` may be fractional; it's
// interpolated between the two neighboring whole-week snapshots.
export function stateAtWeek(week: number): PetSnapshot {
  const w = Math.max(0, Math.min(MAX_WEEK, week));
  const lo = Math.floor(w);
  const hi = Math.min(MAX_WEEK, lo + 1);
  const t = w - lo;

  const physical = Math.round(lerp(PHYSICAL_AT_WEEK[lo], PHYSICAL_AT_WEEK[hi], t));
  const mental = Math.max(0, Math.round(100 - w * MENTAL_DECAY_PER_WEEK));
  const mood = deriveMood(physical, mental);

  return {
    week: w,
    physical,
    mental,
    price: Math.round(lerp(MARKET[lo].price, MARKET[hi].price, t)),
    rooms: Math.round(lerp(MARKET[lo].rooms, MARKET[hi].rooms, t)),
    mood,
    caption: caption(physical, mental, mood),
  };
}

// health.py::commit_trip — both bars back to full, graduated celebration.
export function committedState(): PetSnapshot {
  return {
    week: MAX_WEEK,
    physical: 100,
    mental: 100,
    price: MARKET[0].price, // locked in — booked at the baseline 時価
    rooms: MARKET[0].rooms,
    mood: "graduated",
    caption: caption(100, 100, "graduated"),
  };
}

// pet.py::_caption — Sushi-kun's dialogue for the current state.
export function caption(physical: number, mental: number, mood: Mood): string {
  if (mood === "graduated") return "TRIP BOOKED. i'm free.";
  const lines: string[] = [];
  if (physical < 30) lines.push("prices are killing me");
  else if (physical < 55) lines.push("hotels getting expensive");
  if (mental < 30) lines.push("nobody's talking");
  else if (mental < 55) lines.push("chat's slowing down");
  if (lines.length === 0) {
    if (physical > 80 && mental > 80) return "pet is thriving. keep going.";
    return "pet is stable.";
  }
  return lines.join(", ");
}

// Mood chip colors — aligned with Tabi DS health palette.
export const MOOD_COLOR: Record<Mood, string> = {
  happy: "#3d9a5f",
  worried: "#e08a2e",
  sick: "#d13b2e",
  dying: "#7a7266",
  graduated: "#2f6b4a",
};

/** Same thresholds as webapp/app.js healthColor: ≥70 green, ≥40 orange, else red. */
export function healthColor(val: number): string {
  if (val >= 70) return "#3d9a5f";
  if (val >= 40) return "#e08a2e";
  return "#d13b2e";
}

export function healthLevel(val: number): "good" | "warn" | "bad" {
  if (val >= 70) return "good";
  if (val >= 40) return "warn";
  return "bad";
}

// Real art (public/pet/…) — 18 fully-baked sprites.
// Physical >70 Full, 40–70 Mid, <40 Low.
// Mental >70 Happy, 40–70 Mid, <40 Sad; mental <50 → Rotten_ prefix.
export type PhysicalTier = "Full" | "Mid" | "Low";
export type ExpressionTier = "Happy" | "Mid" | "Sad";

function physicalTier(physical: number): PhysicalTier {
  if (physical > 70) return "Full";
  if (physical >= 40) return "Mid";
  return "Low";
}

function expressionTier(mental: number): ExpressionTier {
  if (mental > 70) return "Happy";
  if (mental >= 40) return "Mid";
  return "Sad";
}

export interface PetArt {
  /** Single fully-baked sprite under public/pet/ */
  src: string;
  /** "{Rotten_?}{Full|Mid|Low}_{Happy|Mid|Sad}" for debugging / keys */
  key: string;
  /** @deprecated dual-layer API — kept so old call sites don't crash */
  sushiSrc: string;
  faceSrc: string;
  faceKey: string;
}

export function petArt(physical: number, mental: number): PetArt {
  const phys = physicalTier(physical);
  const expr = expressionTier(mental);
  const rotten = mental < 50;
  const key = rotten ? `Rotten_${phys}_${expr}` : `${phys}_${expr}`;
  const src = `/pet/${key}.png`;
  return {
    src,
    key,
    sushiSrc: src,
    faceSrc: src,
    faceKey: `${phys}_${expr}`,
  };
}
