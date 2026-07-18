"""Tiny async event bus. Zero deps, isolates plugin services from core state."""
from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    def on(self, topic: str, handler: Handler) -> None:
        self._subs[topic].append(handler)

    async def emit(self, topic: str, payload: dict[str, Any]) -> None:
        handlers = list(self._subs.get(topic, ()))
        if not handlers:
            return
        # Fire concurrently but don't let one failure kill the others.
        async def _safe(h: Handler) -> None:
            try:
                await h(payload)
            except Exception as e:
                print(f"[eventbus] handler for {topic} failed: {e}")
        await asyncio.gather(*[_safe(h) for h in handlers])


bus = EventBus()

# Topic names used across the codebase
T_HEALTH_CHANGED = "health.changed"
T_PHASE_CHANGED = "phase.changed"
T_UNANIMOUS_MATCH = "swipe.unanimous_match"
T_MARKET_PRESSURE = "market.pressure"
T_BOOKING_VERIFIED = "stay22.booking_verified"
T_VOICE_ESCALATE = "voice.escalate"
T_ONBOARD_REQUEST = "voice.onboard_request"
