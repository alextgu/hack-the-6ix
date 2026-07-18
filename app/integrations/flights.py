"""Mock flight stage — deliberately fake (PLAN: 'keep this a mock up').

Generates 3 plausible options seeded by chat_id so they're stable across
calls, priced around the group's budget. The group locks one by saying
"flight 1/2/3" in chat (regex in bot.py); the supervisor moves the stage on.
"""
from __future__ import annotations
import random
from typing import Optional

AIRLINES = ["ANA", "Japan Airlines", "Air Canada", "Zipair", "United"]


def mock_options(chat_id: int, city: Optional[str], budget: Optional[int]) -> list[dict]:
    rng = random.Random(chat_id)  # stable per group
    base = min(max((budget or 1200) * 0.55, 450), 1400)
    dest = (city or "Tokyo").split(",")[0]
    opts = []
    for i, style in enumerate(["cheapest", "balanced", "comfy"], start=1):
        mult = {"cheapest": 0.82, "balanced": 1.0, "comfy": 1.28}[style]
        price = int(base * mult / 10) * 10
        stops = {"cheapest": 1, "balanced": 1 if rng.random() < 0.5 else 0, "comfy": 0}[style]
        opts.append({
            "n": i,
            "airline": rng.choice(AIRLINES),
            "route": f"YYZ → {dest[:3].upper()}",
            "price": price,
            "stops": stops,
            "style": style,
        })
    return opts


def render_options(opts: list[dict]) -> str:
    lines = ["✈️ flights (mock for now — real ones later). reply \"flight 1/2/3\":"]
    for o in opts:
        stops = "nonstop" if o["stops"] == 0 else f"{o['stops']} stop"
        lines.append(f"  {o['n']}. {o['airline']} {o['route']} — ${o['price']}/person · {stops} · {o['style']}")
    return "\n".join(lines)
