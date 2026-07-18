// pet-animate.js — Kamagachi pet animation module
// Vanilla JS. No dependencies. Handles state rendering + ambient life.

const STATES = ['dying', 'sick', 'stable', 'happy', 'golden'];

const STATE_CONFIG = {
  dying:  { breathMs: 6000, breathScale: 1.01, blinkMinMs: 6000, blinkMaxMs: 12000, swayDeg: 0.5, swayMs: 8000, sparkle: false },
  sick:   { breathMs: 4500, breathScale: 1.015, blinkMinMs: 4000, blinkMaxMs: 8000, swayDeg: 1.0, swayMs: 6000, sparkle: false },
  stable: { breathMs: 3000, breathScale: 1.03, blinkMinMs: 2500, blinkMaxMs: 5500, swayDeg: 1.5, swayMs: 5000, sparkle: false },
  happy:  { breathMs: 2200, breathScale: 1.045, blinkMinMs: 2000, blinkMaxMs: 4500, swayDeg: 2.0, swayMs: 4000, sparkle: false },
  golden: { breathMs: 2200, breathScale: 1.05,  blinkMinMs: 2000, blinkMaxMs: 4500, swayDeg: 2.5, swayMs: 4000, sparkle: true }
};

const SVG_PATH = new URL('./pet.svg', import.meta.url).href;

let _svgTextPromise = null;
let _currentState = null;
let _ambientRunning = false;
let _blinkTimer = null;
let _wobbleTimer = null;
let _sparkleTimer = null;
let _rootContainer = null;

// --- helpers ---
function healthToState(health) {
  const h = Math.max(0, Math.min(100, health));
  if (h < 15) return 'dying';
  if (h < 40) return 'sick';
  if (h < 70) return 'stable';
  if (h < 95) return 'happy';
  return 'golden';
}

function fetchSvgText() {
  if (!_svgTextPromise) {
    _svgTextPromise = fetch(SVG_PATH).then(r => r.text());
  }
  return _svgTextPromise;
}

function injectStylesOnce() {
  if (document.getElementById('kamagachi-pet-styles')) return;
  const style = document.createElement('style');
  style.id = 'kamagachi-pet-styles';
  style.textContent = `
    :root {
      --pet-dying-1: #6b7482;
      --pet-dying-2: #c8ccd4;
      --pet-sick-1: #a8b76a;
      --pet-sick-2: #e6f0b8;
      --pet-stable-1: #c9a06a;
      --pet-stable-2: #f5e2b8;
      --pet-happy-1: #ffb454;
      --pet-happy-2: #ffe6a8;
      --pet-golden-1: #ffd24a;
      --pet-golden-2: #fff6c2;
      --pet-flash: #ff3a3a;
    }
    .kamagachi-wrap { position: relative; width: 400px; height: 400px; display: inline-block; }
    .kamagachi-wrap svg { width: 100%; height: 100%; display: block; overflow: visible; }
    .pet-body-group {
      transform-origin: 200px 230px;
      transform-box: fill-box;
      animation: pet-breathe var(--breath-ms, 3s) ease-in-out infinite,
                 pet-sway var(--sway-ms, 5s) ease-in-out infinite;
    }
    @keyframes pet-breathe {
      0%, 100% { transform: scale(1); }
      50%      { transform: scale(var(--breath-scale, 1.03)); }
    }
    @keyframes pet-sway {
      0%, 100% { transform: rotate(calc(var(--sway-deg, 1.5deg) * -1)); }
      50%      { transform: rotate(var(--sway-deg, 1.5deg)); }
    }
    /* Combine transforms cleanly by using separate wrapper groups isn't easy in inline SVG;
       browsers merge these two animations on transform. Modern browsers composite. */
    .kamagachi-wrap.celebrate .pet-body-group {
      animation: pet-celebrate 1.2s cubic-bezier(.3,1.4,.5,1) 1;
    }
    @keyframes pet-celebrate {
      0%   { transform: scale(1)   rotate(0deg); }
      20%  { transform: scale(1.15) rotate(-15deg); }
      50%  { transform: scale(1.25) rotate(20deg); }
      80%  { transform: scale(1.05) rotate(-8deg); }
      100% { transform: scale(1)    rotate(0deg); }
    }
    .kamagachi-wrap.damage .pet-body-group {
      animation: pet-shake 0.45s ease-in-out 1;
    }
    .kamagachi-wrap.damage .pet-body {
      filter: drop-shadow(0 0 8px var(--pet-flash));
    }
    @keyframes pet-shake {
      0%, 100% { transform: translate(0,0) rotate(0); }
      15% { transform: translate(-8px, 2px) rotate(-3deg); }
      30% { transform: translate(7px, -1px) rotate(3deg); }
      45% { transform: translate(-5px, 2px) rotate(-2deg); }
      60% { transform: translate(4px, 0) rotate(2deg); }
      75% { transform: translate(-2px, 1px) rotate(-1deg); }
    }
    .kamagachi-wrap.damage::after {
      content: '';
      position: absolute; inset: 0;
      background: var(--pet-flash);
      opacity: 0.35;
      pointer-events: none;
      animation: pet-flash 0.45s ease-out 1;
      border-radius: 8px;
    }
    @keyframes pet-flash {
      0%   { opacity: 0.5; }
      100% { opacity: 0; }
    }
    .eyelid { transition: height 140ms ease-in; }
    .confetti { animation: confetti-float 3s ease-in-out infinite; transform-origin: 200px 200px; transform-box: fill-box; }
    @keyframes confetti-float {
      0%, 100% { transform: translateY(0); opacity: 0.9; }
      50%      { transform: translateY(-6px); opacity: 1; }
    }
    .pet-sparkles { animation: sparkle-pulse 1.6s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
    @keyframes sparkle-pulse {
      0%, 100% { opacity: 0.4; transform: scale(0.9); }
      50%      { opacity: 1;   transform: scale(1.15); }
    }
    .suitcase { animation: suitcase-wiggle 4s ease-in-out infinite; transform-origin: 320px 285px; transform-box: fill-box; }
    @keyframes suitcase-wiggle {
      0%, 100% { transform: rotate(-2deg); }
      50%      { transform: rotate(3deg); }
    }
    .sparkle-particle {
      position: absolute;
      width: 8px; height: 8px;
      background: radial-gradient(circle, #fff6c2 0%, #ffd24a 60%, transparent 100%);
      border-radius: 50%;
      pointer-events: none;
      animation: sparkle-particle 1.8s ease-out forwards;
    }
    @keyframes sparkle-particle {
      0%   { opacity: 1; transform: translate(0,0) scale(0.4); }
      100% { opacity: 0; transform: translate(var(--dx,0), var(--dy,-40px)) scale(1.2); }
    }
  `;
  document.head.appendChild(style);
}

function setStateVars(wrap, state) {
  const cfg = STATE_CONFIG[state];
  wrap.style.setProperty('--breath-ms', `${cfg.breathMs}ms`);
  wrap.style.setProperty('--breath-scale', cfg.breathScale);
  wrap.style.setProperty('--sway-ms', `${cfg.swayMs}ms`);
  wrap.style.setProperty('--sway-deg', `${cfg.swayDeg}deg`);
}

function showState(wrap, state) {
  const svg = wrap.querySelector('svg');
  if (!svg) return;
  STATES.forEach(s => {
    const g = svg.querySelector(`#state-${s}`);
    if (g) g.style.display = (s === state) ? 'inline' : 'none';
  });
  _currentState = state;
  setStateVars(wrap, state);
}

// --- public API ---

export async function renderPet(container, health) {
  if (!container) throw new Error('renderPet: container required');
  injectStylesOnce();
  _rootContainer = container;

  // Reuse wrap if it exists
  let wrap = container.querySelector('.kamagachi-wrap');
  if (!wrap) {
    wrap = document.createElement('div');
    wrap.className = 'kamagachi-wrap';
    container.appendChild(wrap);
    const svgText = await fetchSvgText();
    wrap.innerHTML = svgText;
  }

  const state = healthToState(health);
  showState(wrap, state);
  return wrap;
}

export function startAmbient() {
  if (_ambientRunning) return;
  _ambientRunning = true;
  scheduleBlink();
  scheduleWobble();
  scheduleSparkles();
}

export function stopAmbient() {
  _ambientRunning = false;
  clearTimeout(_blinkTimer);
  clearTimeout(_wobbleTimer);
  clearInterval(_sparkleTimer);
  _blinkTimer = _wobbleTimer = _sparkleTimer = null;
}

function currentWrap() {
  return _rootContainer && _rootContainer.querySelector('.kamagachi-wrap');
}

function scheduleBlink() {
  if (!_ambientRunning) return;
  const cfg = STATE_CONFIG[_currentState] || STATE_CONFIG.stable;
  const delay = cfg.blinkMinMs + Math.random() * (cfg.blinkMaxMs - cfg.blinkMinMs);
  _blinkTimer = setTimeout(() => {
    doBlink();
    scheduleBlink();
  }, delay);
}

function doBlink() {
  const wrap = currentWrap();
  if (!wrap) return;
  const activeGroup = wrap.querySelector(`#state-${_currentState}`);
  if (!activeGroup) return;
  const lids = activeGroup.querySelectorAll('.eyelid');
  if (!lids.length) return;
  // Close
  lids.forEach(l => l.setAttribute('height', '28'));
  setTimeout(() => {
    lids.forEach(l => l.setAttribute('height', '0'));
  }, 130);
}

function scheduleWobble() {
  if (!_ambientRunning) return;
  const delay = 4000 + Math.random() * 4000;
  _wobbleTimer = setTimeout(() => {
    doMouthWobble();
    scheduleWobble();
  }, delay);
}

function doMouthWobble() {
  const wrap = currentWrap();
  if (!wrap) return;
  const activeGroup = wrap.querySelector(`#state-${_currentState}`);
  if (!activeGroup) return;
  const mouth = activeGroup.querySelector('.pet-mouth');
  if (!mouth) return;
  const orig = mouth.getAttribute('d');
  // Nudge control point Y using a tiny path re-parse: shift a couple digits.
  // Simpler: apply a brief transform via requestAnimationFrame.
  const start = performance.now();
  const dur = 500;
  function frame(t) {
    const p = Math.min(1, (t - start) / dur);
    const wob = Math.sin(p * Math.PI) * 2.5;
    mouth.setAttribute('transform', `translate(0 ${wob})`);
    if (p < 1) requestAnimationFrame(frame);
    else mouth.removeAttribute('transform');
  }
  requestAnimationFrame(frame);
  // orig is kept via attribute; nothing to restore for d.
  void orig;
}

function scheduleSparkles() {
  if (!_ambientRunning) return;
  _sparkleTimer = setInterval(() => {
    const cfg = STATE_CONFIG[_currentState];
    if (!cfg || !cfg.sparkle) return;
    spawnSparkle();
  }, 700);
}

function spawnSparkle() {
  const wrap = currentWrap();
  if (!wrap) return;
  const s = document.createElement('div');
  s.className = 'sparkle-particle';
  const x = 100 + Math.random() * 200;
  const y = 140 + Math.random() * 160;
  s.style.left = `${x}px`;
  s.style.top = `${y}px`;
  s.style.setProperty('--dx', `${(Math.random() - 0.5) * 60}px`);
  s.style.setProperty('--dy', `${-30 - Math.random() * 40}px`);
  wrap.appendChild(s);
  setTimeout(() => s.remove(), 1900);
}

export function celebrate() {
  const wrap = currentWrap();
  if (!wrap) return;
  wrap.classList.remove('celebrate');
  // Force reflow to restart animation
  void wrap.offsetWidth;
  wrap.classList.add('celebrate');
  // Burst of sparkles regardless of state
  for (let i = 0; i < 12; i++) {
    setTimeout(() => spawnSparkle(), i * 60);
  }
  setTimeout(() => wrap.classList.remove('celebrate'), 1250);
}

export function damageFlash() {
  const wrap = currentWrap();
  if (!wrap) return;
  wrap.classList.remove('damage');
  void wrap.offsetWidth;
  wrap.classList.add('damage');
  setTimeout(() => wrap.classList.remove('damage'), 500);
}

// Convenience: update health without full re-render
export function updateHealth(health) {
  const wrap = currentWrap();
  if (!wrap) return;
  const next = healthToState(health);
  if (next !== _currentState) {
    showState(wrap, next);
  }
}

export { healthToState, STATES };
