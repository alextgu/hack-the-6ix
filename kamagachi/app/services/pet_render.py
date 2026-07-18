"""Server-side pet SVG composition and chat-message helpers."""
from __future__ import annotations
from pathlib import Path
from ..config import pet_state


PET_SVG_PATH = Path(__file__).parent.parent / "static" / "pet" / "pet.svg"


def health_bar(health: int, width: int = 20) -> str:
    filled = max(0, min(width, round(health / 100 * width)))
    return "▓" * filled + "░" * (width - filled)


PET_EMOJI = {
    "golden": "🌟",
    "happy": "😄",
    "stable": "🙂",
    "sick": "🤒",
    "dying": "💀",
}


def status_line(health: int, phase: str, trigger: str = "") -> str:
    state = pet_state(health)
    emoji = PET_EMOJI.get(state, "🐣")
    bar = health_bar(health)
    tail = f" · {trigger}" if trigger else ""
    return f"{emoji} Pet: {bar} {health}% [{phase}]{tail}"


def render_pet_svg_for_state(state: str) -> str:
    """Return the master SVG with all state groups hidden except `state`."""
    if not PET_SVG_PATH.exists():
        return _fallback_svg(state)
    svg = PET_SVG_PATH.read_text(encoding="utf-8")
    for s in ("dying", "sick", "stable", "happy", "golden"):
        marker = f'id="state-{s}"'
        vis = "inline" if s == state else "none"
        svg = svg.replace(marker, f'{marker} style="display:{vis}"')
    return svg


def _fallback_svg(state: str) -> str:
    color = {
        "golden": "#F5C518", "happy": "#7CD992", "stable": "#F0D47A",
        "sick": "#E89E5E", "dying": "#8F8F9A",
    }.get(state, "#7CD992")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
  <ellipse cx="200" cy="220" rx="140" ry="130" fill="{color}"/>
  <circle cx="150" cy="180" r="14" fill="#1a1a22"/>
  <circle cx="250" cy="180" r="14" fill="#1a1a22"/>
  <path d="M130 260 Q200 300 270 260" stroke="#1a1a22" stroke-width="6" fill="none" stroke-linecap="round"/>
  <text x="200" y="380" text-anchor="middle" font-family="system-ui" fill="#1a1a22">Kamagachi · {state}</text>
</svg>'''
