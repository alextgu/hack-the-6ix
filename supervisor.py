"""LangGraph supervisor — Tabi stops being passive (SUPERVISOR_PLAN.md).

Supervisor pattern: a deterministic supervisor node routes to workers and is
the ONLY gate on what reaches the chat. Workers come back to it every time.

    on_message / on_heartbeat
            │
       ┌────▼───────┐
       │ supervisor │◄────────────┐   routing = code (debuggable);
       └┬─────┬─────┘             │   workers = Gemini (extraction + voice)
        ├→ stage_tracker ─────────┤   deterministic stage from TripState
        ├→ profile_tracker ───────┤   per-user facts → Mongo user_profiles
        ├→ messenger ─────────────┘   Tabi decides {send?, message, action}
        └→ END

Entry points (both BLOCKING — call via asyncio.to_thread from the bot):
    run_turn(chat_id, trigger)  → Decision(send, message, action)

bot.py executes the Decision (send text / deal cards / post flights).
Model seam: Gemini via langchain-google-genai — swap FREESOLO here later.
"""
from __future__ import annotations
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, END

import db
import state
import cards
import flights

log = logging.getLogger("trippet.supervisor")

SEND_COOLDOWN_S = 45          # pet never speaks twice within this window
HEARTBEAT_SILENCE_S = 45 * 60  # heartbeat nudges only after this much quiet

_last_sent_at: dict[int, float] = {}
_last_profiled_n: dict[int, int] = {}


# ─── LLM (lazy; one client per process) ──────────────────────────────────────
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        from langchain_google_genai import ChatGoogleGenerativeAI
        _llm = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL", "gemini-flash-latest"),
            google_api_key=os.environ.get("GEMINI_API_KEY"),
            temperature=0.6,
        )
    return _llm


def _llm_json(prompt: str) -> Optional[dict]:
    """One model call → parsed JSON dict (None on any failure)."""
    try:
        raw = _get_llm().invoke(prompt).content
        if isinstance(raw, list):  # newer langchain: list of content blocks
            raw = "".join(p.get("text", "") if isinstance(p, dict) else str(p)
                          for p in raw)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group(0)) if m else None
    except Exception as e:
        log.warning("llm_json failed: %s", e)
        return None


# ─── Graph state ─────────────────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    chat_id: int
    trigger: str          # "message" | "heartbeat"
    transcript: list      # recent chat_log rows
    profiles: list
    trip: dict
    plan: dict
    stage: str            # GATHER | FLIGHTS | HOTELS | BOOK
    missing: list
    done: list            # worker names that have run
    send: bool
    message: Optional[str]
    action: str           # none | deal_cards | post_flights


@dataclass
class Decision:
    send: bool = False
    message: Optional[str] = None
    action: str = "none"


# ─── Workers ─────────────────────────────────────────────────────────────────
def stage_tracker(s: AgentState) -> AgentState:
    """Deterministic: where is the plan? (LLMs don't get to do this math.)"""
    g = state.get_or_create(s["chat_id"])
    trip = g.trip
    plan = s["plan"]
    missing = []
    if not trip.city:
        missing.append("city")
    if not (trip.dates and trip.dates.start):
        missing.append("dates")
    if trip.budget_per_person is None:
        missing.append("budget")

    if missing:
        stage = "GATHER"
    elif not plan.get("flight_locked"):
        stage = "FLIGHTS"
    else:
        session = cards.get_session(s["chat_id"]) or db.load_session(s["chat_id"])
        stage = "BOOK" if (session and session.get("winner")) else "HOTELS"

    if plan.get("stage") != stage:
        db.update_plan(s["chat_id"], {"stage": stage})
    return {**s, "stage": stage, "missing": missing, "done": s["done"] + ["stage"]}


def profile_tracker(s: AgentState) -> AgentState:
    """Gemini: extract per-user facts from messages we haven't profiled yet."""
    chat_id = s["chat_id"]
    transcript = s["transcript"]
    seen = _last_profiled_n.get(chat_id, 0)
    fresh = transcript[seen:]
    _last_profiled_n[chat_id] = len(transcript)
    if fresh:
        convo = "\n".join(f"{m['name']}: {m['text']}" for m in fresh)
        out = _llm_json(
            "Extract per-person trip facts from this group chat snippet. "
            'Return ONLY JSON: {"people": [{"name": str, "budget": int|null, '
            '"dates": str|null, "cities": [str], "vibe": str|null, '
            '"objection": str|null}]}. Omit people who said nothing factual.\n\n'
            + convo
        )
        for p in (out or {}).get("people", []):
            if p.get("name"):
                db.upsert_profile(chat_id, p["name"], {k: v for k, v in p.items() if k != "name"})
    return {**s, "profiles": db.get_profiles(chat_id), "done": s["done"] + ["profiles"]}


def messenger(s: AgentState) -> AgentState:
    """Gemini-as-Tabi decides whether to speak, what to say, what to do."""
    g = state.get_or_create(s["chat_id"])
    convo = "\n".join(f"{m['name']}: {m['text']}" for m in s["transcript"][-25:])
    profiles = json.dumps(s["profiles"], default=str)[:1500]
    already_flights = bool(s["plan"].get("flights_posted"))
    silent_trigger = s["trigger"] == "heartbeat"

    out = _llm_json(f"""You are Tabi, a tamagotchi trip-pet living in a Telegram group chat.
Personality: lowercase, brief (max 3 short lines), warm but a little dramatic
about your health — the group's indecision is literally killing you.
Your job: walk the group through stages: GATHER (lock city+dates+budget) →
FLIGHTS (pick a mock flight) → HOTELS (swipe the card deck) → BOOK.

Current stage: {s['stage']}. Missing fields: {s['missing']}.
Pet health: physical {g.pet.physical}, mental {g.pet.mental} ({g.pet.mood}).
Trigger: {"the chat has been silent a while — you may nudge" if silent_trigger else "new messages arrived"}.
Known per-person facts: {profiles}
Recent chat:
{convo}

Decide. Rules:
- Speak ONLY if you add value: a missing field to chase, a specific person to
  ask (by name), a conflict to call out, a stage to advance, or a nudge after
  silence. If the humans are mid-flow and nothing is needed from you: silent.
- Stage FLIGHTS and flights not posted yet → action "post_flights".
- Stage HOTELS and no deck dealt this stage → action "deal_cards".
- Never repeat what you said in the recent chat. Never use hashtags.

Return ONLY JSON: {{"send": bool, "message": str|null, "action": "none"|"post_flights"|"deal_cards", "why": str}}""")

    out = out or {"send": False, "message": None, "action": "none"}
    # deterministic overrides so stage actions can't be forgotten by the model
    if s["stage"] == "FLIGHTS" and not already_flights:
        out["action"] = "post_flights"
        out["send"] = True
    if s["stage"] == "HOTELS" and s["plan"].get("cards_dealt_stage") != "HOTELS":
        out["action"] = "deal_cards"
        out["send"] = True
    log.info("messenger chat=%s stage=%s send=%s action=%s why=%s",
             s["chat_id"], s["stage"], out.get("send"), out.get("action"),
             str(out.get("why", ""))[:120])
    return {**s, "send": bool(out.get("send")), "message": out.get("message"),
            "action": out.get("action") or "none", "done": s["done"] + ["messenger"]}


# ─── Supervisor (routing + the only send-gate) ───────────────────────────────
def supervisor_node(s: AgentState) -> AgentState:
    return s  # pure router; logic lives in _route


def _route(s: AgentState) -> str:
    done = s["done"]
    if "stage" not in done:
        return "stage_tracker"
    if "profiles" not in done and s["trigger"] == "message":
        return "profile_tracker"
    if "messenger" not in done:
        return "messenger"
    return END


def _gate(chat_id: int, d: Decision) -> Decision:
    """Final supervisor gate: cooldown + empty-message guard."""
    now = time.time()
    if d.send and (now - _last_sent_at.get(chat_id, 0)) < SEND_COOLDOWN_S:
        log.info("gate: cooldown swallowed a send (chat=%s)", chat_id)
        return Decision()
    if d.send and not (d.message or d.action != "none"):
        return Decision()
    if d.send:
        _last_sent_at[chat_id] = now
    return d


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        g = StateGraph(AgentState)
        g.add_node("supervisor", supervisor_node)
        g.add_node("stage_tracker", stage_tracker)
        g.add_node("profile_tracker", profile_tracker)
        g.add_node("messenger", messenger)
        g.set_entry_point("supervisor")
        g.add_conditional_edges("supervisor", _route)
        g.add_edge("stage_tracker", "supervisor")
        g.add_edge("profile_tracker", "supervisor")
        g.add_edge("messenger", "supervisor")
        _graph = g.compile()
    return _graph


# ─── Entry points (blocking; wrap in asyncio.to_thread) ─────────────────────
def run_turn(chat_id: int, trigger: str = "message") -> Decision:
    try:
        init: AgentState = {
            "chat_id": chat_id,
            "trigger": trigger,
            "transcript": db.recent_chat(chat_id, 40),
            "profiles": [],
            "trip": {},
            "plan": db.get_plan(chat_id),
            "stage": "GATHER",
            "missing": [],
            "done": [],
            "send": False,
            "message": None,
            "action": "none",
        }
        out = _get_graph().invoke(init)
        return _gate(chat_id, Decision(send=out.get("send", False),
                                       message=out.get("message"),
                                       action=out.get("action", "none")))
    except Exception as e:
        log.warning("run_turn failed (chat=%s): %s", chat_id, e)
        return Decision()


def try_lock_flight(chat_id: int, text: str) -> Optional[str]:
    """'flight 2' in chat locks the mock flight. Returns confirmation text."""
    m = re.search(r"\bflight\s*([123])\b", text, re.IGNORECASE)
    if not m:
        return None
    plan = db.get_plan(chat_id)
    if plan.get("flight_locked"):
        return None
    g = state.get_or_create(chat_id)
    opts = flights.mock_options(chat_id, g.trip.city, g.trip.budget_per_person)
    pick = opts[int(m.group(1)) - 1]
    db.update_plan(chat_id, {"flight_locked": pick, "stage": "HOTELS"})
    return (f"✈️ locked: {pick['airline']} {pick['route']} at ${pick['price']}/person. "
            "now the fun part — hotels.")


def note_flights_posted(chat_id: int) -> None:
    db.update_plan(chat_id, {"flights_posted": True})


def note_cards_dealt(chat_id: int) -> None:
    db.update_plan(chat_id, {"cards_dealt_stage": "HOTELS"})
