# Kamagachi Pet Visual

Living pet visual for the Kamagachi Telegram bot. Health (0-100) drives one of five
states: `dying`, `sick`, `stable`, `happy`, `golden`.

## Files
- `pet.svg` — master SVG, all 5 states as `<g id="state-*">` (only one shown at a time).
- `pet-animate.js` — vanilla JS module (breathing, blinks, sway, celebrate, damage flash).
- `pet.html` — standalone slider test bench. Open in a browser served over HTTP.

## Usage

```js
import { renderPet, startAmbient, celebrate, damageFlash, updateHealth }
  from './pet-animate.js';

await renderPet(document.getElementById('pet'), 42); // sick
startAmbient();       // breathing + blinks + sway + sparkles
updateHealth(95);     // swap to happy without re-fetching SVG
celebrate();          // 1.2s bounce + sparkle burst
damageFlash();        // red flash + shake when hp drops
```

## Notes
- Serve over HTTP (fetch loads `pet.svg`). Opening `pet.html` via `file://` may fail CORS.
- State thresholds: <15 dying, <40 sick, <70 stable, <95 happy, >=95 golden.
- Palette exposed via CSS vars (`--pet-happy-1`, etc.) on `:root` for easy tweaks.
