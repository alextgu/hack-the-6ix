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

// health.py::scrub_to_week — physical replays the market series 0 → week,
// mental decays linearly with silence. Idempotent recompute per week.
export function stateAtWeek(week: number): PetSnapshot {
  const w = Math.max(0, Math.min(MAX_WEEK, week));

  let physical = 100;
  let prev = MARKET[0];
  for (let i = 1; i <= w; i++) {
    physical = applyMarketDelta(physical, prev, MARKET[i]);
    prev = MARKET[i];
  }
  const mental = Math.max(0, 100 - w * MENTAL_DECAY_PER_WEEK);
  const mood = deriveMood(physical, mental);

  return {
    week: w,
    physical,
    mental,
    price: MARKET[w].price,
    rooms: MARKET[w].rooms,
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
  return lines.join(" — ");
}

// pet.py::MOOD_COLORS (RGB → hex).
export const MOOD_COLOR: Record<Mood, string> = {
  happy: "#7CD992",
  worried: "#F0D47A",
  sick: "#E89E5E",
  dying: "#8F8F9A",
  graduated: "#F5C518",
};

// Bar colors: physical (green) + mental (purple), matching pet.py's bars.
export const PHYSICAL_COLOR = "#7CD992";
export const MENTAL_COLOR = "#B28CFF";

// How spoiled the 🍣 looks per mood — CSS filter + transform on the placeholder.
// (Replace the emoji with a Lottie animation later; these map cleanly to mood.)
export const MOOD_SUSHI_STYLE: Record<Mood, { filter: string; transform: string; opacity: number }> = {
  happy: { filter: "none", transform: "translateY(0) rotate(0deg) scale(1)", opacity: 1 },
  worried: { filter: "grayscale(0.25) saturate(0.9)", transform: "translateY(4px) rotate(-4deg) scale(0.98)", opacity: 1 },
  sick: { filter: "grayscale(0.5) sepia(0.35) saturate(0.8)", transform: "translateY(10px) rotate(-8deg) scale(0.94)", opacity: 0.9 },
  dying: { filter: "grayscale(0.85) brightness(0.8) blur(0.4px)", transform: "translateY(18px) rotate(-12deg) scale(0.9)", opacity: 0.55 },
  graduated: { filter: "saturate(1.35) brightness(1.1) drop-shadow(0 0 14px #F5C518)", transform: "translateY(-6px) rotate(0deg) scale(1.1)", opacity: 1 },
};
