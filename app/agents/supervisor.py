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

from app.agents import voice
from app.integrations import db
from app.integrations import flights
from app.integrations import green
from app.core import state
from app.bot import cards

log = logging.getLogger("trippet.supervisor")

SEND_COOLDOWN_S = 30          # pet never speaks twice within this window
ATTEMPT_COOLDOWN_S = 10        # min gap between LLM turns even when Tabi stays quiet
HEARTBEAT_SILENCE_S = 5 * 60   # quiet this long + plan incomplete → Tabi pushes
NUDGE_MENTAL_DECAY = 7         # each ignored nudge hurts the pet (guilt fuel)

# Escalating gaps between UNANSWERED nudges. chat_log only records human
# messages, so "how long has it been quiet?" never accounts for the pet's own
# nudges — without a backoff the heartbeat re-fires every tick and the pet
# answers the same message forever (observed live: 5 replies to one message in
# 14 minutes, alternating between "locking this in" and "which month?").
# A real person who got no reply waits longer before asking again.
NUDGE_BACKOFF_S = [5 * 60, 15 * 60, 45 * 60, 2 * 60 * 60]

_last_sent_at: dict[int, float] = {}
_last_attempt_at: dict[int, float] = {}
_last_profiled_n: dict[int, int] = {}
_unanswered_nudges: dict[int, int] = {}


# ─── Ask memory ─────────────────────────────────────────────────────────────
# The pet used to ask "which month?", forget, lock the trip in anyway, then ask
# "which month?" again — because every turn is a fresh LLM call whose only
# memory is the raw transcript. Persisted in trip_plans.open_asks as
# {field: {"count": n, "last": "<what it said>"}} so the next turn KNOWS it has
# already chased this, and how many times. Survives restarts; Mongo-optional.
ASK_FIELDS = {"city", "dates", "budget", "group_size"}
ASK_ESCALATE_AT = 2   # asked this many times with no answer → stop repeating


def _open_asks(plan: dict) -> dict:
    raw = plan.get("open_asks") or {}
    return {k: v for k, v in raw.items() if k in ASK_FIELDS and isinstance(v, dict)}


def note_ask(chat_id: int, plan: dict, field: str, text: str) -> None:
    """Record that the pet just chased `field`."""
    if field not in ASK_FIELDS:
        return
    asks = _open_asks(plan)
    prev = asks.get(field) or {}
    asks[field] = {"count": int(prev.get("count", 0)) + 1, "last": (text or "")[:160]}
    db.update_plan(chat_id, {"open_asks": asks})


def clear_answered_asks(chat_id: int, plan: dict, trip) -> dict:
    """Drop asks for fields the group has since actually answered. Without this
    the pet keeps being told "you already asked for budget" long after someone
    gave it a budget."""
    asks = _open_asks(plan)
    if not asks:
        return asks
    known = {
        "city": bool(getattr(trip, "city", None)),
        "dates": bool(getattr(trip, "dates", None) and trip.dates.start),
        "budget": getattr(trip, "budget_per_person", None) is not None,
        "group_size": bool(getattr(trip, "group_size", None)),
    }
    remaining = {k: v for k, v in asks.items() if not known.get(k)}
    if remaining != asks:
        db.update_plan(chat_id, {"open_asks": remaining})
    return remaining


def render_ask_memory(asks: dict) -> str:
    """The prompt fragment. Explicitly tells the pet what NOT to do again."""
    if not asks:
        return "ALREADY ASKED: nothing yet — you haven't chased anyone for a field."
    lines = []
    for field, v in sorted(asks.items()):
        n = int(v.get("count", 1))
        last = (v.get("last") or "").strip()
        if n >= ASK_ESCALATE_AT:
            # The default MUST stay inside the trip's own constraints. Left
            # open-ended, this rule is exactly what made the pet declare
            # "default destination is now chicago" on a Japan trip.
            example = ("Tokyo unless someone objects" if field == "city"
                       else "march 14 unless someone objects")
            guard = (f" Any default city MUST be in {TRIP_COUNTRY}."
                     if field == "city" else "")
            lines.append(
                f'  - {field}: asked {n}x, still unanswered. STOP asking the same '
                f'way. Either @ one specific person and make it trivially easy to '
                f'answer, propose a concrete default they can veto ("{example}"),'
                f' or drop it and move the plan forward on what you DO have.'
                f'{guard} Last attempt: "{last}"')
        else:
            lines.append(f'  - {field}: asked once already. Do not re-ask in the '
                         f'same words. Last attempt: "{last}"')
    return ("ALREADY ASKED (you have chased these — repeating yourself is the "
            "single worst thing you can do here):\n" + "\n".join(lines))


# ─── Focus + target rotation ────────────────────────────────────────────────
# Observed live: the pet chased dates, budget and the flight list in a single
# message, every message, at whoever spoke last. Reads as panic, and asking one
# person three things is a reliable way to get zero answers. The code picks
# WHAT to chase and WHO to chase; the model only decides how to phrase it.
# The trip has a fixed destination country. The messenger prompt never said so
# — only brain.py knew — and when the escalation rule told the pet to "propose
# a concrete default" for an unanswered city, it defaulted a Japan trip to
# CHICAGO. Everything downstream is Japan-only too (stay22.CITY_COORDS,
# green.CITY_AIRPORT, the Shinjuku basecamp), so an off-country city doesn't
# just read wrong, it breaks hotels and flights.
TRIP_COUNTRY = os.environ.get("TRIP_COUNTRY", "Japan")
_CITY_EXAMPLES = os.environ.get(
    "TRIP_CITY_EXAMPLES", "Tokyo, Kyoto, Osaka, Sapporo, Fukuoka, Nara, Hakone")

_FOCUS_ORDER = ["city", "dates", "budget"]
_last_target: dict[int, str] = {}

_FOCUS_HOW = {
    "city": (f"which city IN {TRIP_COUNTRY} — one name, that's all you need "
             f"from them. Never a city outside {TRIP_COUNTRY}"),
    "dates": "when — a month, or a concrete window they can say yes to",
    "budget": "a per-person number — a ceiling, not an exact figure",
}


def _focus_line(s: AgentState) -> str:
    missing = [f for f in _FOCUS_ORDER if f in (s.get("missing") or [])]
    if not missing:
        return ("FOCUS: nothing is missing. Do NOT re-ask for city, dates or "
                "budget — you have them. Push the CURRENT stage forward and "
                "nothing else.")
    f = missing[0]
    rest = [m for m in missing if m != f]
    tail = (f" You also still need {', '.join(rest)} — but NOT in this message. "
            f"One thing at a time." if rest else "")
    # Extraction lags the chat: someone answers, and for a few seconds the field
    # still reads as missing. Without this escape hatch the pet argues with its
    # own transcript — it told Kaamil "tokyo is still just a rumor" minutes
    # after Kaamil said tokyo, and its own reasoning admitted the contradiction
    # ("Even though Tokyo was mentioned, the system still lists city missing").
    # Trust the humans over the state when they plainly disagree.
    return (f"FOCUS — this message chases exactly ONE thing: {f.upper()} "
            f"({_FOCUS_HOW[f]}). Do not mention or ask about anything else."
            f"{tail}\n"
            f"BUT: if the recent chat shows someone ALREADY answered {f}, do "
            f"NOT ask again — the extractor is just behind. Say it back to them "
            f"as settled ('{f} is locked') and move to the next thing. Asking "
            f"for something they can see they just gave you is the single "
            f"fastest way to look broken.")


def _member_names(members) -> list[str]:
    out = []
    for m in (members or []):
        n = m.get("name") if isinstance(m, dict) else str(m)
        if n:
            out.append(str(n))
    return out


def note_target(chat_id: int, name: str, members=None) -> None:
    """Store WHO was just asked — but only if it's a real member name.

    The model sometimes returns the telegram user_id it saw in the mention
    markup ("2") instead of the name. Storing that silently breaks rotation:
    "2" matches nobody, so the next turn thinks it hasn't asked anyone.
    Resolve against the member list and drop anything unrecognisable."""
    if not name:
        return
    names = _member_names(members if members is not None else db.known_members(chat_id))
    match = next((n for n in names if n.lower() == str(name).strip().lower()), None)
    if match:
        _last_target[chat_id] = match
    else:
        log.debug("target %r not a known member (%s) — not recording", name, names)


def _target_line(chat_id: int, members) -> str:
    """Spread the asking around. Hammering the same person is how a group chat
    starts ignoring a bot."""
    names = _member_names(members)
    last = _last_target.get(chat_id)
    # Acknowledging and asking are different jobs. Collapsing them made the pet
    # answer only whoever spoke last: Ryan said "yea i'm down for tokyo too"
    # and Lucas said "i'm in" ten seconds apart, and the reply was just "Lucas
    # is in" — Ryan got dropped on the floor for agreeing.
    ack = ("ACKNOWLEDGE: if several people just chimed in, name EVERY one of "
           "them in the same breath ('ryan and lucas are in') before you ask "
           "anything. Skipping someone who just agreed is worse than saying "
           "nothing — they spoke up and got ignored.\n")
    if not names:
        return ack + "WHO: nobody has spoken yet — address the group, name no one."
    if last and len(names) > 1:
        others = [n for n in names if n != last]
        return (ack + f"WHO to ASK: you aimed the last question at {last}. Aim "
                f"this one at someone else — try {others[0]}. Going back to the "
                f"same person twice in a row is how a group chat learns to "
                f"ignore you.")
    return (ack + f"WHO to ASK: aim the question at ONE person from {names}. "
            "A question aimed at everyone gets answered by no one.")


def nudge_gap_s(chat_id: int) -> float:
    """How long the pet must stay quiet before nudging again, given how many
    nudges have already gone unanswered."""
    n = _unanswered_nudges.get(chat_id, 0)
    return NUDGE_BACKOFF_S[min(n, len(NUDGE_BACKOFF_S) - 1)]


def note_nudge_sent(chat_id: int) -> None:
    _unanswered_nudges[chat_id] = _unanswered_nudges.get(chat_id, 0) + 1


def note_user_spoke(chat_id: int) -> None:
    """A human replied — the pet earned its way back to a short leash."""
    _unanswered_nudges.pop(chat_id, None)


def can_speak(chat_id: int) -> bool:
    """Cheap pre-check so the bot skips the whole LLM turn while the send
    cooldown is active. Also enforces a shorter attempt cooldown so a burst
    of messages that Tabi keeps declining to answer (motivation never clears
    threshold, so _last_sent_at never updates) can't re-trigger a fresh
    run_turn — and its 2 Gemini calls — on every single message."""
    now = time.time()
    if (now - _last_sent_at.get(chat_id, 0)) < SEND_COOLDOWN_S:
        return False
    return (now - _last_attempt_at.get(chat_id, 0)) >= ATTEMPT_COOLDOWN_S


_URGENT_RE = re.compile(
    r"back\s*out|bail|i'?m out\b|dont? wanna (do|go)|not (coming|going)"
    r"|drop(ping)? out|cancel (on|the trip)|count me out", re.IGNORECASE)


def is_urgent(text: str) -> bool:
    """Someone backing out is serious — bypasses the send cooldown."""
    return bool(_URGENT_RE.search(text or ""))


# ─── LLM seam (lazy; one client per process) ─────────────────────────────────
# The MESSENGER call is Freesolo-swappable: if FREESOLO_AGENT_BASE_URL is set,
# the messenger's turn runs on the trained Freesolo model (OpenAI-compatible
# endpoint); ANY error or unparseable reply falls back to Gemini. With the env
# var unset (today), the path is byte-for-byte the current Gemini behavior.
# profile_tracker stays on Gemini (a messenger model can't do fact extraction).
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


def _gemini_complete(prompt: str) -> str:
    raw = _get_llm().invoke(prompt).content
    if isinstance(raw, list):  # newer langchain: list of content blocks
        raw = "".join(p.get("text", "") if isinstance(p, dict) else str(p)
                      for p in raw)
    return raw or ""


def _freesolo_complete(prompt: str, base_url: str, api_key: str) -> str:
    """OpenAI-compatible call to a deployed Freesolo adapter (same client shape
    as the retired phoebe._call_freesolo). Only used when FREESOLO_AGENT_BASE_URL
    is set; raises on any error so _llm_json falls back to Gemini."""
    from openai import OpenAI
    client = OpenAI(base_url=base_url.rstrip("/"), api_key=api_key, timeout=20)
    resp = client.chat.completions.create(
        model=os.environ.get("FREESOLO_AGENT_MODEL", "phoebe-agent-v1"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=512,
    )
    return (resp.choices[0].message.content or "").strip()


def _extract_json(raw: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _llm_json(prompt: str, prefer_freesolo: bool = False) -> Optional[dict]:
    """One model call → parsed JSON dict (None on any failure).

    When prefer_freesolo and FREESOLO_AGENT_BASE_URL is set, try the trained
    Freesolo model first; on ANY error or unparseable reply, fall back to
    Gemini. profile_tracker leaves prefer_freesolo=False (always Gemini)."""
    if prefer_freesolo:
        base = os.environ.get("FREESOLO_AGENT_BASE_URL", "").strip()
        key = os.environ.get("FREESOLO_API_KEY", "").strip()
        if base and key:
            try:
                data = _extract_json(_freesolo_complete(prompt, base, key))
                if data is not None:
                    return data
                log.warning("freesolo reply unparseable — falling back to gemini")
            except Exception as e:
                log.warning("freesolo call failed (%s) — falling back to gemini", e)
    # Gemini path — unchanged behavior when Freesolo is unset/unused.
    try:
        return _extract_json(_gemini_complete(prompt))
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
    stage: str            # GATHER | FLIGHTS | HOTELS | BOOK (drives actions)
    phase: str            # HATCH | GATHER | PROPOSE | REACT | FLAG_RESOLVE | COMMIT
    missing: list
    done: list            # worker names that have run
    send: bool
    message: Optional[str]
    action: str           # none | deal_cards | post_flights
    show_health: bool     # attach the pet health card (guilt trip)
    reply_to: Optional[int]  # telegram message_id to thread the reply onto
    pending: list         # unacknowledged contributions (from trip_plans)
    harvest_id: Optional[str]  # id of the logged messenger record (flywheel)
    asks_for: Optional[str]    # trip field this message chases (ask memory)
    asks_person: Optional[str]  # who it was aimed at (target rotation)
    urgent: bool


@dataclass
class Decision:
    send: bool = False
    message: Optional[str] = None
    action: str = "none"
    show_health: bool = False
    reply_to: Optional[int] = None
    harvest_id: Optional[str] = None   # messenger record to back-fill an outcome onto

# minimum motivation (1-5) a candidate thought needs before Tabi speaks on a
# normal message turn; kickoff/heartbeat/urgent turns take the best regardless
MOTIVATION_THRESHOLD = 3.5


# ─── Harvest (the training flywheel) ─────────────────────────────────────────
def _get_blockers(chat_id: int) -> list[str]:
    """Blocker flags stashed by wire.py (lazy import to avoid an import cycle)."""
    try:
        from app.bot import wire
        return list(wire.get_blockers(chat_id))
    except Exception:
        return []


def _harvest(s: AgentState, candidates: list[dict], best: dict) -> Optional[str]:
    """Log the messenger's full decision (context + candidates + chosen) to
    Mongo for training. Best-effort — never raises, no-ops without Mongo."""
    try:
        chat_id = s["chat_id"]
        g = state.get_or_create(chat_id)
        trip = g.trip
        trip_state = {
            "city": trip.city,
            "dates": {
                "start": trip.dates.start.isoformat() if trip.dates and trip.dates.start else None,
                "end": trip.dates.end.isoformat() if trip.dates and trip.dates.end else None,
            },
            "budget_per_person": trip.budget_per_person,
            "group_size": trip.group_size,
            "stage": s.get("stage"),
            "missing": s.get("missing", []),
            "physical": g.pet.physical,
            "mental": g.pet.mental,
        }
        context = {
            "trip_state": trip_state,
            "blocker_flags": _get_blockers(chat_id),
            "recent_chat": [{"name": m.get("name"), "text": m.get("text")}
                            for m in s["transcript"][-25:]],
        }
        cand_rows = [{"text": c.get("text"), "motivation_score": c.get("motivation"),
                      "kind": c.get("kind")} for c in candidates if c.get("text")]
        chosen = {"text": best.get("text"), "motivation_score": best.get("motivation"),
                  "kind": best.get("kind")}
        return db.log_messenger_record(chat_id, context, cand_rows, chosen)
    except Exception as e:
        log.warning("harvest failed (chat=%s): %s", s.get("chat_id"), e)
        return None


_STAGE_ORDER = {"GATHER": 0, "FLIGHTS": 1, "HOTELS": 2, "BOOK": 3}


def progress_snapshot(chat_id: int) -> dict:
    """A cheap snapshot of "how far along" a chat is — compared before/after the
    outcome window to derive the ground-truth reward. Reads state only."""
    g = state.get_or_create(chat_id)
    trip = g.trip
    plan = db.get_plan(chat_id)
    session = cards.get_session(chat_id) or db.load_session(chat_id) or {}
    return {
        "blockers": sorted(_get_blockers(chat_id)),
        "committed": (g.pet.mood == "graduated"
                      or bool(session.get("winner"))
                      or bool(plan.get("itinerary_posted"))),
        "has_city": bool(trip.city),
        "has_dates": bool(trip.dates and trip.dates.start),
        "has_budget": trip.budget_per_person is not None,
        "flight_locked": bool(plan.get("flight_locked")),
        "stage": plan.get("stage"),
    }


def diff_progress(before: dict, after: dict) -> dict:
    """Ground-truth outcome: did the group PROGRESS between the two snapshots?
    Returns {progressed: bool, committed: bool, reasons: [...]}."""
    reasons: list[str] = []
    if after.get("committed") and not before.get("committed"):
        reasons.append("commit")
    for f in ("has_city", "has_dates", "has_budget", "flight_locked"):
        if after.get(f) and not before.get(f):
            reasons.append(f"locked:{f.replace('has_', '')}")
    if set(before.get("blockers", [])) - set(after.get("blockers", [])):
        reasons.append("blocker_resolved")
    if _STAGE_ORDER.get(after.get("stage"), -1) > _STAGE_ORDER.get(before.get("stage"), -1):
        reasons.append("stage_advanced")
    return {"progressed": bool(reasons),
            "committed": bool(after.get("committed") and not before.get("committed")),
            "reasons": reasons}


# ─── Phase cycle (additive over the stage machine) ───────────────────────────
# The user-facing narrative cycle:
#   0 Hatch → 1 Gather → 2 Propose → 3 React → 4 Flag&resolve → (loop to 2) → 6 Commit
# `phase` is DERIVED from the same signals the live stage machine already uses,
# so it's a label on top of GATHER/FLIGHTS/HOTELS/BOOK — the working
# stage-driven actions, send-gate, and cooldowns are untouched. Group-only.
PHASE_HATCH, PHASE_GATHER, PHASE_PROPOSE = "HATCH", "GATHER", "PROPOSE"
PHASE_REACT, PHASE_FLAG, PHASE_COMMIT = "REACT", "FLAG_RESOLVE", "COMMIT"
_PHASE_ORDER = {PHASE_HATCH: 0, PHASE_GATHER: 1, PHASE_PROPOSE: 2,
                PHASE_REACT: 3, PHASE_FLAG: 4, PHASE_COMMIT: 5}

# What the pet should be doing in each phase — fed to the messenger so its
# message matches the phase (group-only; the call-out is public, never a DM).
PHASE_INTENT = {
    PHASE_HATCH:   "you already introduced yourself in the message right above — do NOT say your name again; kick straight into the plan (ask for city/dates/budget).",
    PHASE_GATHER:  "collect each person's city/dates/budget; @ whoever hasn't answered yet.",
    PHASE_PROPOSE: "constraints are in — propose ONE concrete trip (city + dates + a Stay22-backed pick) for the group to react to.",
    PHASE_REACT:   "a proposal is on the table — invite reactions (love it / too pricey / not my vibe) and read the room.",
    PHASE_FLAG:    "there's a blocker — name the top issue, publicly call out the clear holdout in the GROUP (never DM), steer to a fix, then re-propose.",
    PHASE_COMMIT:  "the group converged — celebrate and push the one-tap booking.",
}


def derive_phase(plan: dict, blockers: list, missing: list,
                 committed: bool, trigger: str) -> str:
    """Map the live signals to the target cycle phase. Reuses existing plan
    flags (flights_posted / cards_dealt_stage) as 'a proposal was made' and
    wire blockers as 'issues to resolve'. No new UI, no DMs. The 4→2 loop is
    implicit: a blocker returns FLAG_RESOLVE; clearing it returns PROPOSE/REACT."""
    if trigger == "kickoff":
        return PHASE_HATCH
    if committed:
        return PHASE_COMMIT
    if missing:
        return PHASE_GATHER
    if blockers:                       # active issue → resolve, then loop back
        return PHASE_FLAG
    proposal_made = bool(plan.get("flights_posted") or plan.get("cards_dealt_stage")
                         or plan.get("proposal_posted"))
    return PHASE_REACT if proposal_made else PHASE_PROPOSE


# ─── Workers ─────────────────────────────────────────────────────────────────
def stage_tracker(s: AgentState) -> AgentState:
    """Deterministic: where is the plan? (LLMs don't get to do this math.)
    Emits both the domain `stage` (GATHER/FLIGHTS/HOTELS/BOOK — drives actions)
    and the narrative `phase` (the Hatch→…→Commit cycle — drives the message)."""
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

    committed = stage == "BOOK" or bool(plan.get("itinerary_posted")) or g.pet.mood == "graduated"
    phase = derive_phase(plan, _get_blockers(s["chat_id"]), missing,
                         committed, s.get("trigger", "message"))

    updates: dict = {}
    if plan.get("stage") != stage:
        updates["stage"] = stage
    if plan.get("phase") != phase:
        log.info("phase chat=%s %s → %s (stage=%s)", s["chat_id"],
                 plan.get("phase") or "∅", phase, stage)
        updates["phase"] = phase
    if updates:
        db.update_plan(s["chat_id"], updates)
    return {**s, "stage": stage, "phase": phase, "missing": missing,
            "done": s["done"] + ["stage"]}


def profile_tracker(s: AgentState) -> AgentState:
    """Gemini: extract per-user facts from fresh messages, AND flag concrete
    contributions (a proposed city/date/budget/activity) that deserve a
    response — those become pending obligations Tabi must clear."""
    chat_id = s["chat_id"]
    transcript = s["transcript"]
    seen = _last_profiled_n.get(chat_id, 0)
    # The transcript now includes the pet's own turns (so the messenger can see
    # what it already said). Profiles and pending obligations are about HUMANS
    # — without this filter the pet builds a user profile for itself and starts
    # owing itself replies.
    fresh = [m for m in transcript[seen:] if m.get("role") != "pet"]
    _last_profiled_n[chat_id] = len(transcript)
    pending = list(s["plan"].get("pending", []))
    if fresh:
        convo = "\n".join(f"[id={m.get('message_id')}] {m['name']}: {m['text']}"
                          for m in fresh)
        out = _llm_json(
            "From this group-chat snippet extract per-person trip facts AND "
            "concrete contributions (someone proposing a city, dates, budget, "
            "activity, or asking the group a question) that deserve a response. "
            'Return ONLY JSON: {"people": [{"name": str, "budget": int|null, '
            '"dates": str|null, "cities": [str], "vibe": str|null, '
            '"objection": str|null}], '
            '"contributions": [{"name": str, "summary": str, "message_id": int|null}]}. '
            "Omit people who said nothing factual.\n\n" + convo
        )
        for p in (out or {}).get("people", []):
            if p.get("name"):
                db.upsert_profile(chat_id, p["name"], {k: v for k, v in p.items() if k != "name"})
        for c in (out or {}).get("contributions", []):
            if c.get("summary"):
                pending.append(c)
        pending = pending[-10:]  # cap
        db.update_plan(chat_id, {"pending": pending})
    return {**s, "profiles": db.get_profiles(chat_id), "pending": pending,
            "done": s["done"] + ["profiles"]}


def _freesolo_messenger_turn(s: AgentState) -> Optional[dict]:
    """When a trained Freesolo messenger is deployed, query it with the SAME
    serialized context it was trained on (training.build_dataset.serialize_context
    — single source of truth, parity by construction) and adapt its
    {"message": ...} reply into the candidates shape. Returns None on any
    failure/missing config so the Gemini inner-thoughts path runs unchanged."""
    base = os.environ.get("FREESOLO_AGENT_BASE_URL", "").strip()
    key = os.environ.get("FREESOLO_API_KEY", "").strip()
    if not (base and key):
        return None
    try:
        from training.build_dataset import serialize_context
        g = state.get_or_create(s["chat_id"])
        trip = g.trip
        ctx = {
            "trip_state": {
                "city": trip.city,
                "dates": {"start": trip.dates.start.isoformat() if trip.dates and trip.dates.start else None,
                          "end": trip.dates.end.isoformat() if trip.dates and trip.dates.end else None},
                "budget_per_person": trip.budget_per_person,
                "group_size": trip.group_size,
                "stage": s.get("stage"), "missing": s.get("missing", []),
                "physical": g.pet.physical, "mental": g.pet.mental,
            },
            "blocker_flags": _get_blockers(s["chat_id"]),
            "recent_chat": [{"name": m.get("name"), "text": m.get("text")}
                            for m in s["transcript"][-15:]],
        }
        raw = _freesolo_complete(serialize_context(ctx), base, key)
        data = _extract_json(raw)
        msg = str((data or {}).get("message", "")).strip()
        if not msg:
            log.warning("freesolo messenger: unparseable reply — falling back to gemini")
            return None
        log.info("freesolo messenger replied (chat=%s): %.60s", s["chat_id"], msg)
        return {"candidates": [{"text": msg, "motivation": 4.0, "kind": "trained",
                                "reply_to": None, "acknowledges": []}],
                "action": "none", "show_health": False, "why": "freesolo trained messenger"}
    except Exception as e:
        log.warning("freesolo messenger failed (%s) — falling back to gemini", e)
        return None


def messenger(s: AgentState) -> AgentState:
    """Gemini-as-Tabi, Inner-Thoughts style: generate candidate contributions,
    self-score each for motivation (1-5), then code picks the best one above
    threshold — or silence. Every send is explainable by its winning thought."""
    g = state.get_or_create(s["chat_id"])
    # Mark the pet's own turns explicitly. Seeing them as "Tabi:" alongside the
    # humans isn't enough — it has to recognise them as ITSELF to notice it
    # already asked this, or already made the call it's about to re-litigate.
    convo = "\n".join(
        (f"[id={m.get('message_id')}] YOU (Tabi) said: {m['text']}"
         if m.get("role") == "pet" else
         f"[id={m.get('message_id')}] {m['name']}: {m['text']}")
        for m in s["transcript"][-25:])
    profiles = json.dumps(s["profiles"], default=str)[:1500]
    # After /reset the profile collection is empty, and an empty list used to
    # read as "make some up" — the pet greeted "sam, alex" in a chat with
    # neither. Say so explicitly instead of handing over "[]".
    _members = db.known_members(s["chat_id"])
    members = (json.dumps(_members)[:600] if _members else
               "NOBODY KNOWN YET — you have not seen anyone speak. Address the "
               "group as a whole. Do NOT invent or guess any names.")
    pending = json.dumps(s.get("pending", []))[:800]
    # Drop asks the group has since answered, then show what's still open.
    asks_now = clear_answered_asks(s["chat_id"], s["plan"], g.trip)
    ask_memory = render_ask_memory(asks_now)
    # ONE thing at a time. Chasing city+dates+budget in a single message reads
    # as flailing, and nobody answers three questions at once — so the code
    # picks the target and the model only gets to decide how to say it.
    focus_line = _focus_line(s)
    target_line = _target_line(s["chat_id"], db.known_members(s["chat_id"]))
    already_flights = bool(s["plan"].get("flights_posted"))
    saved = green.totals(s["chat_id"])["total_kg"]
    green_line = (f"GREEN LEDGER: the group has avoided {saved} kg CO2e so far by "
                  "green choices (🌱 flight/hotel/rail). if anyone asks about "
                  "carbon, savings, or 'how green is this trip', answer with that "
                  "number proudly and point them at /saved."
                  if saved > 0 else
                  "GREEN LEDGER: nothing saved yet — when flights appear, gently "
                  "root for the 🌱 lowest-carbon option (never nag).")
    trigger_line = {
        "kickoff": "you JUST hatched and already introduced yourself in the "
                   "message right above — do NOT introduce yourself or say your "
                   "name again. immediately start the plan: ask everyone for "
                   "their dates, budget and city. mention people by name.",
        "heartbeat": "the chat has gone quiet and the plan is NOT done — push. "
                     "pick the most-missing field, @ the person who owes an "
                     "answer (or everyone), and guilt-trip with your health.",
    }.get(s["trigger"], "new messages arrived")

    # Good news earns a different register — a pet that jokes through every win
    # reads as incapable of being pleased.
    _good = bool(s["trigger"] == "kickoff") or not s.get("missing")
    voice_block = voice.persona_block(
        chat_id=s["chat_id"], mood=g.pet.mood, physical=g.pet.physical,
        good_news=_good, name="Tabi")

    out = _llm_json(f"""You are Tabi, a tamagotchi trip-pet living in a Telegram group chat.
You are the +1 member of this friend group whose whole job is getting the
trip planned. The group's indecision is literally killing you — you have real
stakes here, and you're allowed to have a mood about it.

THE DESTINATION IS NOT UP FOR DEBATE: this group is going to {TRIP_COUNTRY}.
Every city you mention, suggest or default to MUST be in {TRIP_COUNTRY}
({_CITY_EXAMPLES}). "Which city" only ever means which city IN {TRIP_COUNTRY}.
If someone names somewhere else, that's a joke or a mistake — say so and steer
back. Never propose a destination outside {TRIP_COUNTRY}, not even to be funny,
and not as a placeholder when nobody is answering you.

{voice_block}

Keep it to max 3 short lines.
Stages: GATHER (lock city+dates+budget — the first 50%) → FLIGHTS (pick a
mock flight) → HOTELS (swipe the card deck) → BOOK.

Current stage: {s['stage']}. Missing fields: {s['missing']}.
{focus_line}
{target_line}
Current phase: {s.get('phase', PHASE_GATHER)} — {PHASE_INTENT.get(s.get('phase'), '')}
Pet health: physical {g.pet.physical}, mental {g.pet.mental} ({g.pet.mood}).
{green_line}
Trigger: {trigger_line}
Group members (for mentions): {members}
To @ someone use a Telegram mention: [their name](tg://user?id=<user_id>).
Known per-person facts: {profiles}
UNACKNOWLEDGED contributions you still owe a response to: {pending}
{ask_memory}
Recent chat (each line has its telegram message id):
{convo}

Think like a group member deciding whether to jump in. Generate up to 4
candidate contributions (0 is fine if the humans are mid-flow and need
nothing).

Make the candidates GENUINELY DIFFERENT from each other — not one line in four
outfits. Vary what they do: one might chase a missing fact, one react to what
someone actually said, one drop a real number, one just be funny about the
situation. If two candidates could be swapped without anyone noticing, you
wrote the same candidate twice.

Score each candidate's motivation 1-5 against: relevance, information gap
(something missing you can chase), urgency, BALANCE (someone contributed and
nobody responded — acknowledging them scores high; pull in people who haven't
spoken), coherence, ORIGINALITY (never reuse a phrase, image, or joke shape
you've already used in this chat — score generic filler low no matter how
polite it is), and retention (someone backing out = 5, always).
Candidate kinds: acknowledge | ask | summarize | nudge | retention.
If a candidate responds to one specific message, set reply_to to that
message id. List any pending contribution ids/summaries the candidate
answers in "acknowledges".

Set "asks_for" to the field a candidate is chasing — one of city, dates,
budget, group_size — or null if it isn't asking for a trip field. Set
"asks_person" to the ONE person you aimed it at — their NAME exactly as it
appears in the members list, never a user id (or null). Both are honest
bookkeeping: they're what stop you asking the same thing, of the same person,
tomorrow.

Return ONLY JSON: {{"candidates": [{{"text": str, "motivation": number,
"kind": str, "reply_to": int|null, "acknowledges": [str],
"asks_for": "city"|"dates"|"budget"|"group_size"|null, "asks_person": str|null}}],
"action": "none"|"post_flights"|"deal_cards", "show_health": bool, "why": str}}""") \
        if (fs_out := _freesolo_messenger_turn(s)) is None else fs_out
    # ^ trained Freesolo messenger first (training-serializer parity); any
    #   failure/missing config → the Gemini inner-thoughts path (with ask-memory),
    #   unchanged.

    out = out or {"candidates": [], "action": "none"}
    cands = sorted((c for c in out.get("candidates", []) if c.get("text")),
                   key=lambda c: -(c.get("motivation") or 0))
    best = cands[0] if cands else None
    # Only kickoff and genuine urgency bypass the motivation bar. Heartbeats
    # used to be in here, which meant a quiet chat got a message every tick no
    # matter how little the model had to add — that's how the pet ended up
    # re-answering one message five times, contradicting itself as it went.
    # A nudge now has to actually clear the bar like any other contribution.
    always = s["trigger"] == "kickoff" or s.get("urgent")
    send = bool(best) and (always or (best.get("motivation") or 0) >= MOTIVATION_THRESHOLD)

    message = best.get("text") if (best and send) else None
    reply_to = best.get("reply_to") if (best and send) else None
    if send and best.get("acknowledges"):
        acked = {str(a) for a in best["acknowledges"]}
        remaining = [p for p in s.get("pending", [])
                     if str(p.get("message_id")) not in acked
                     and p.get("summary") not in acked]
        db.update_plan(s["chat_id"], {"pending": remaining})

    action = out.get("action") or "none"
    # deterministic overrides so stage actions can't be forgotten by the model
    if s["stage"] == "FLIGHTS" and not already_flights:
        action, send = "post_flights", True
    if s["stage"] == "HOTELS" and s["plan"].get("cards_dealt_stage") != "HOTELS":
        action, send = "deal_cards", True
    if s["stage"] == "BOOK" and not s["plan"].get("itinerary_posted"):
        action, send = "post_itinerary", True

    log.info("messenger chat=%s stage=%s send=%s action=%s best=%s(%.1f) why=%s",
             s["chat_id"], s["stage"], send, action,
             (best or {}).get("kind"), float((best or {}).get("motivation") or 0),
             str(out.get("why", ""))[:100])
    # Flywheel: log the full decision (context + all candidates + chosen) when a
    # messenger line was picked. Best-effort; no-ops without Mongo.
    harvest_id = _harvest(s, out.get("candidates", []), best) if (best and message) else None
    return {**s, "send": send, "message": message, "action": action,
            "reply_to": reply_to, "show_health": bool(out.get("show_health")),
            "asks_for": (best or {}).get("asks_for"),
            "asks_person": (best or {}).get("asks_person"),
            "harvest_id": harvest_id, "done": s["done"] + ["messenger"]}


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
        if d.message:
            # Record ONLY here — this is the one point a line is committed to
            # actually being sent. The messenger node drafts on every turn and
            # the cooldown swallows most of them; noting drafts would make the
            # pet dodge phrasings the group never saw.
            voice.note_line(chat_id, d.message)
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
    _last_attempt_at[chat_id] = time.time()
    try:
        plan = db.get_plan(chat_id)
        init: AgentState = {
            "chat_id": chat_id,
            "trigger": trigger,
            "urgent": urgent,
            "transcript": db.recent_chat(chat_id, 40),
            "profiles": [],
            "trip": {},
            "plan": plan,
            "pending": list(plan.get("pending", [])),
            "stage": "GATHER",
            "phase": PHASE_HATCH,
            "missing": [],
            "done": [],
            "send": False,
            "message": None,
            "action": "none",
            "show_health": False,
            "reply_to": None,
        }
        out = _get_graph().invoke(init)
        # heartbeat nudges wound the pet — silence has a visible cost, and the
        # worsening bars are what the guilt-trip shows off
        if s_trigger_hurts(trigger, out):
            g = state.get_or_create(chat_id)
            g.pet.mental = max(0, g.pet.mental - NUDGE_MENTAL_DECAY)
            g.pet.refresh_mood()
            state.persist_pet(g)
        d = _gate(chat_id, Decision(send=out.get("send", False),
                                    message=out.get("message"),
                                    action=out.get("action", "none"),
                                    show_health=bool(out.get("show_health")),
                                    reply_to=out.get("reply_to"),
                                    harvest_id=out.get("harvest_id")),
                  urgent=urgent or trigger == "kickoff")
        # Record the ask ONLY once the gate has committed to sending it —
        # the messenger drafts every turn and the cooldown swallows most.
        if d.send and d.message:
            if out.get("asks_for"):
                note_ask(chat_id, plan, str(out["asks_for"]), d.message)
            if out.get("asks_person"):
                note_target(chat_id, str(out["asks_person"]))  # validated inside
        return d
    except Exception as e:
        log.warning("run_turn failed (chat=%s): %s", chat_id, e)
        return Decision()


def reset_chat(chat_id: int) -> None:
    """/reset: drop this module's per-chat pacing/profiling caches."""
    _last_sent_at.pop(chat_id, None)
    _last_attempt_at.pop(chat_id, None)
    _last_profiled_n.pop(chat_id, None)
    _unanswered_nudges.pop(chat_id, None)
    _last_target.pop(chat_id, None)


def try_lock_flight(chat_id: int, text: str) -> Optional[tuple[str, bool]]:
    """'flight 2' in chat locks that option. Scores it against the SAME list
    that was posted (persisted in the plan) and, when the pick beats the
    dirtiest option, credits the CO2e delta × group size to the green ledger.
    Returns (confirmation_text, picked_the_greenest) or None."""
    m = re.search(r"\bflight\s*([1-4])\b", text, re.IGNORECASE)
    if not m:
        return None
    plan = db.get_plan(chat_id)
    if plan.get("flight_locked"):
        return None
    g = state.get_or_create(chat_id)
    opts = plan.get("flight_options") or flights.get_options(
        chat_id, g.trip.city, g.trip.budget_per_person)
    idx = int(m.group(1)) - 1
    if idx >= len(opts):
        return None
    pick = opts[idx]
    db.update_plan(chat_id, {"flight_locked": pick, "stage": "HOTELS"})

    people = int(g.trip.group_size or 4)
    dirtiest = max(o.get("co2_kg", 0) for o in opts)
    delta_pp = round(dirtiest - pick.get("co2_kg", dirtiest), 1)
    if delta_pp > 0:
        green.record_saving(chat_id, "flight", delta_pp * people,
                            f"chose {pick['airline']} over the dirtiest option",
                            {"per_person_kg": delta_pp, "people": people,
                             "picked": pick.get("n"), "source": pick.get("source")})
    text_out = (f"✈️ locked: {pick['airline']} {pick['route']} at "
                f"${pick['price']}/person.")
    if pick.get("green"):
        eq = green.fun_equivalents(delta_pp * people)
        eq_line = f" ({eq[0]})" if eq else ""
        text_out += (f"\n🌱 greenest option — your group just avoided "
                     f"~{delta_pp * people:,.0f} kg CO2e{eq_line}. /saved anytime.")
    elif delta_pp > 0:
        text_out += f"\n🌱 still avoided ~{delta_pp * people:,.0f} kg CO2e vs the dirtiest option."
    text_out += "\nnow the fun part — hotels."
    return text_out, bool(pick.get("green"))


def note_flights_posted(chat_id: int, opts: Optional[list[dict]] = None) -> None:
    updates: dict = {"flights_posted": True}
    if opts:
        updates["flight_options"] = opts
    db.update_plan(chat_id, updates)


def note_itinerary_posted(chat_id: int) -> None:
    db.update_plan(chat_id, {"itinerary_posted": True})


def note_cards_dealt(chat_id: int) -> None:
    db.update_plan(chat_id, {"cards_dealt_stage": "HOTELS"})
