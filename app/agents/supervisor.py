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

from app.integrations import db
from app.integrations import flights
from app.core import state
from app.bot import cards

log = logging.getLogger("trippet.supervisor")

SEND_COOLDOWN_S = 30          # pet never speaks twice within this window
HEARTBEAT_SILENCE_S = 5 * 60   # quiet this long + plan incomplete → Tabi pushes
NUDGE_MENTAL_DECAY = 7         # each ignored nudge hurts the pet (guilt fuel)

_last_sent_at: dict[int, float] = {}
_last_profiled_n: dict[int, int] = {}


def can_speak(chat_id: int) -> bool:
    """Cheap pre-check so the bot skips the whole LLM turn while the send
    cooldown is active — this, not a message-count debounce, paces Tabi."""
    return (time.time() - _last_sent_at.get(chat_id, 0)) >= SEND_COOLDOWN_S


_URGENT_RE = re.compile(
    r"back\s*out|bail|i'?m out\b|dont? wanna (do|go)|not (coming|going)"
    r"|drop(ping)? out|cancel (on|the trip)|count me out", re.IGNORECASE)


def is_urgent(text: str) -> bool:
    """Someone backing out is serious — bypasses the send cooldown."""
    return bool(_URGENT_RE.search(text or ""))


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
    show_health: bool     # attach the pet health card (guilt trip)


@dataclass
class Decision:
    send: bool = False
    message: Optional[str] = None
    action: str = "none"
    show_health: bool = False


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
    members = json.dumps(db.known_members(s["chat_id"]))[:600]
    already_flights = bool(s["plan"].get("flights_posted"))
    trigger_line = {
        "kickoff": "you JUST hatched — introduce yourself in one line, then "
                   "immediately start the plan: ask everyone for their dates, "
                   "budget and city. mention people by name. you always send "
                   "on kickoff.",
        "heartbeat": "the chat has gone quiet and the plan is NOT done — push. "
                     "pick the most-missing field, @ the person who owes an "
                     "answer (or everyone), and guilt-trip with your health. "
                     "show_health=true when you reference it.",
    }.get(s["trigger"], "new messages arrived")

    out = _llm_json(f"""You are Tabi, a tamagotchi trip-pet living in a Telegram group chat.
You are the +1 member of this friend group whose whole job is getting the
trip planned. Personality: lowercase, brief (max 3 short lines), warm but
dramatic about your health — the group's indecision is literally killing you.
Stages: GATHER (lock city+dates+budget — the first 50%) → FLIGHTS (pick a
mock flight) → HOTELS (swipe the card deck) → BOOK.

Current stage: {s['stage']}. Missing fields: {s['missing']}.
Pet health: physical {g.pet.physical}, mental {g.pet.mental} ({g.pet.mood}).
Trigger: {trigger_line}
Group members (for mentions): {members}
To @ someone use a Telegram mention: [their name](tg://user?id=<user_id>).
Known per-person facts: {profiles}
Recent chat:
{convo}

Decide. Rules:
- Speak when you can push the plan forward: a missing field to chase, a
  specific person who hasn't answered (mention them!), a conflict to call
  out, a stage to advance, or a nudge after silence. Stay silent only when
  the humans are actively mid-flow and need nothing from you.
- KEEP PERSUADING: until the current stage's needs are met you do not give
  up — vary your angle each time (ask a person, show your health, summarize
  what's agreed vs missing) instead of repeating yourself.
- SERIOUS OVERRIDE: if anyone sounds like they're backing out, bailing, or
  losing interest in the trip, you MUST respond immediately — mention them,
  use what you know about what they wanted (profiles), remind them the group
  needs them, and be a little heartbroken about it. Retention is your top
  priority; your life literally depends on this trip happening.
- Stage FLIGHTS and flights not posted yet → action "post_flights".
- Stage HOTELS and no deck dealt this stage → action "deal_cards".
- set show_health=true whenever you reference your health bars — the group
  then sees your health card. don't overuse it (max ~1 in 3 sends).
- Never repeat what you said in the recent chat. Never use hashtags.

Return ONLY JSON: {{"send": bool, "message": str|null, "action": "none"|"post_flights"|"deal_cards", "show_health": bool, "why": str}}""")

    out = out or {"send": False, "message": None, "action": "none"}
    if s["trigger"] == "kickoff":
        out["send"] = True  # hatch always opens the conversation
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
            "action": out.get("action") or "none",
            "show_health": bool(out.get("show_health")),
            "done": s["done"] + ["messenger"]}


# ─── Supervisor (routing + the only send-gate) ───────────────────────────────
def supervisor_node(s: AgentState) -> AgentState:
    return s  # pure router; logic lives in _route


def _route(s: AgentState) -> str:
    done = s["done"]
    if "stage" not in done:
        return "stage_tracker"
    if "profiles" not in done and s["trigger"] in ("message", "kickoff"):
        return "profile_tracker"
    if "messenger" not in done:
        return "messenger"
    return END


def _gate(chat_id: int, d: Decision, urgent: bool = False) -> Decision:
    """Final supervisor gate: cooldown + empty-message guard. Urgent turns
    (someone backing out) skip the cooldown."""
    now = time.time()
    if d.send and not urgent and (now - _last_sent_at.get(chat_id, 0)) < SEND_COOLDOWN_S:
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


def s_trigger_hurts(trigger: str, out: dict) -> bool:
    """A heartbeat nudge that actually fires = the group left Tabi hanging."""
    return trigger == "heartbeat" and bool(out.get("send"))


# ─── Entry points (blocking; wrap in asyncio.to_thread) ─────────────────────
def run_turn(chat_id: int, trigger: str = "message", urgent: bool = False) -> Decision:
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
            "show_health": False,
        }
        out = _get_graph().invoke(init)
        # heartbeat nudges wound the pet — silence has a visible cost, and the
        # worsening bars are what the guilt-trip shows off
        if s_trigger_hurts(trigger, out):
            g = state.get_or_create(chat_id)
            g.pet.mental = max(0, g.pet.mental - NUDGE_MENTAL_DECAY)
            g.pet.refresh_mood()
            state.persist_pet(g)
        return _gate(chat_id, Decision(send=out.get("send", False),
                                       message=out.get("message"),
                                       action=out.get("action", "none"),
                                       show_health=bool(out.get("show_health"))),
                     urgent=urgent or trigger == "kickoff")
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
