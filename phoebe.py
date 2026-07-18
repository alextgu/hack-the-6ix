"""Phoebe agent — scaffold. Diagnose the ONE binding blocker, resolve it.

Its own model seam, independent of `brain.py::call_model`. See PIPELINE.md:
  Read seam  = Gemini (brain.py)
  Agent seam = Freesolo — plugs in here via FREESOLO_AGENT_BASE_URL.

Not wired into the bot yet. Rule-based stubs run without any API key so the
demo below is walkable today. Every stub carries a TODO seam for the real
Freesolo-trained agent to slot into later.
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from typing import Literal, Optional


BlockerKind = Literal["person", "timing", "issue", "none"]
ActionKind = Literal[
    "dm_holdout",
    "propose_cheaper_neighborhood",
    "hold_rooms_48h",
    "ask_group",
    "no_action",
]


# ─── Typed shapes ───────────────────────────────────────────────────────────
@dataclass
class Blocker:
    kind: BlockerKind           # person | timing | issue | none
    subject: str                # user name, "dates", "city", "budget", "none"
    detail: str                 # human-readable one-liner
    source: str                 # which brain.py flag or which rule fired


@dataclass
class Action:
    kind: ActionKind
    target: str                 # user name | city | "group"
    rationale: str
    parameters: dict = field(default_factory=dict)


# ─── agent_call — the AGENT seam. SEPARATE from brain.py's call_model. ─────
def agent_call(prompt: str) -> str:
    """The one place Phoebe hits its own model. Do NOT reuse `brain.call_model`.

    Precedence:
      1. Freesolo agent adapter — FREESOLO_AGENT_BASE_URL + FREESOLO_API_KEY
         (this is what wins the Freesolo track once we've trained + deployed).
      2. LLM fallback — Gemini via GEMINI_API_KEY, so this file works today.
      3. Error — surfaced clearly with instructions.
    """
    fs_url = os.environ.get("FREESOLO_AGENT_BASE_URL", "").strip()
    fs_key = os.environ.get("FREESOLO_API_KEY", "").strip()
    if fs_url and fs_key:
        return _agent_call_freesolo(prompt, fs_url, fs_key)

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        return _agent_call_gemini(prompt, gemini_key)

    raise RuntimeError(
        "No agent model configured. Either deploy a Freesolo agent adapter and set "
        "FREESOLO_AGENT_BASE_URL + FREESOLO_AGENT_MODEL, or set GEMINI_API_KEY "
        "(free at https://aistudio.google.com/apikey) for the interim path."
    )


def _agent_call_freesolo(prompt: str, base_url: str, api_key: str) -> str:
    from openai import OpenAI
    client = OpenAI(base_url=base_url.rstrip("/"), api_key=api_key)
    resp = client.chat.completions.create(
        model=os.environ.get("FREESOLO_AGENT_MODEL", "phoebe-agent-v1"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content or ""


def _agent_call_gemini(prompt: str, api_key: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp"))
    resp = model.generate_content(prompt)
    return resp.text or ""


# ─── diagnose — pick the ONE binding blocker ───────────────────────────────
def diagnose(reconciled_state: dict) -> Blocker:
    """Rule-based stub. Reads brain.py's reconciled output + the `blockers`
    list wire.py stashes there. Returns the single highest-priority blocker.

    TODO(freesolo-agent): replace with an `agent_call` that reads richer
    context (full chat window, per_person history, prior Phoebe actions)
    and identifies WHICH specific person is silently stalling, not just
    which field is missing.
    """
    blockers: list[str] = reconciled_state.get("blockers", []) or []
    per_person: dict = reconciled_state.get("per_person", {}) or {}

    # P1 — city TIE: can't even shop hotels
    for b in blockers:
        if b.startswith("city_tie"):
            return Blocker(kind="issue", subject="city", detail=b, source="brain.city_tie")

    # P2 — no date overlap: even if city is known, no dates → no market call
    for b in blockers:
        if b.startswith("date_no_overlap"):
            return Blocker(kind="timing", subject="dates", detail=b, source="brain.date_no_overlap")

    # P3 — a single person's budget is well below group median (blocking hotel search)
    stated = [(name, p.get("budget")) for name, p in per_person.items() if p.get("budget")]
    if len(stated) >= 2:
        stated.sort(key=lambda x: x[1])
        lo_name, lo_amount = stated[0]
        median = stated[len(stated) // 2][1]
        if lo_amount < 0.7 * median:
            return Blocker(
                kind="person",
                subject=lo_name,
                detail=f"{lo_name}'s ${lo_amount} cap is <70% of group median ${median}",
                source="rule.low_budget_person",
            )

    # P4 — budget missing entirely
    for b in blockers:
        if b.startswith("budget_missing"):
            return Blocker(kind="issue", subject="budget", detail=b, source="brain.budget_missing")

    # P5 — silent holdout: someone who spoke but stated no budget/city/dates
    silent = [n for n, p in per_person.items()
              if not any(p.get(k) for k in ("budget", "city"))
              and not (p.get("dates") or {}).get("start")]
    if silent:
        return Blocker(
            kind="person",
            subject=silent[0],
            detail=f"{silent[0]} hasn't stated anything concrete",
            source="rule.silent_person",
        )

    return Blocker(kind="none", subject="none",
                   detail="no binding blocker — trip is on track", source="rule.no_blocker")


# ─── decide_action — map blocker → concrete resolution ─────────────────────
def _extract_tie_candidates(detail: str) -> list[str]:
    m = re.search(r"between (.+?)(?: \(| \d|$)", detail)
    if not m:
        return []
    return [c.strip() for c in m.group(1).split(",") if c.strip()]


def decide_action(blocker: Blocker, state: dict) -> Action:
    """Rule-based stub mapping each blocker kind → the right move (per
    PROJECT.md §6: remove the objection, don't push on it).

    TODO(freesolo-agent): replace with `agent_call` that reads what the
    low-budget person actually likes, then proposes a specific neighborhood.
    """
    if blocker.source == "rule.low_budget_person":
        return Action(
            kind="propose_cheaper_neighborhood",
            target=state.get("city") or "the trip",
            rationale=f"{blocker.subject}'s cap won't fit standard picks — shift area rather than ask them to spend more",
            parameters={"low_budget_person": blocker.subject},
        )
    if blocker.source == "rule.silent_person":
        return Action(
            kind="dm_holdout",
            target=blocker.subject,
            rationale=f"DM {blocker.subject} privately for their budget + date window",
            parameters={"channel": "dm"},
        )
    if blocker.subject == "city":
        return Action(
            kind="hold_rooms_48h",
            target="group",
            rationale="City split — hold one room in each candidate for 48h; opt-out mechanic forces a decision",
            parameters={"hold_hours": 48, "candidates": _extract_tie_candidates(blocker.detail)},
        )
    if blocker.subject == "dates":
        return Action(
            kind="dm_holdout",
            target="group",
            rationale="No date overlap — DM each person individually for their must-hold days",
            parameters={"channel": "dm_each"},
        )
    if blocker.subject == "budget":
        return Action(
            kind="ask_group",
            target="group",
            rationale="Nobody stated a budget — ask directly in the chat",
            parameters={},
        )
    return Action(kind="no_action", target="group", rationale="nothing to resolve")


# ─── compose_message — the outreach copy (uses agent_call) ─────────────────
_PROMPT = """You are Phoebe, an in-chat agent helping a group plan a Japan trip.
Write ONE short, friendly message (max 240 characters) executing this action.
Don't add preamble, quotes, or emoji spam. Just the message text.

Action: {action_kind}
Target: {target}
Rationale: {rationale}
Extra: {parameters}

Trip so far:
  city:   {city}
  dates:  {dates}
  budget: ${budget}
"""


def compose_message(action: Action, state: dict) -> str:
    """Generate the outreach message via agent_call().

    STUB: builds a prompt for the eventual Freesolo agent. Until a model is
    configured we fall back to a hand-written canned line so the demo runs.
    """
    prompt = _PROMPT.format(
        action_kind=action.kind,
        target=action.target,
        rationale=action.rationale,
        parameters=json.dumps(action.parameters or {}),
        city=state.get("city"),
        dates=state.get("dates"),
        budget=state.get("budget_per_person"),
    )
    try:
        return agent_call(prompt).strip()
    except RuntimeError:
        return _canned_message(action)


def _canned_message(action: Action) -> str:
    if action.kind == "dm_holdout":
        return f"hey {action.target} — quick one: what's your rough budget and which days can you actually go? the group's waiting on you."
    if action.kind == "propose_cheaper_neighborhood":
        low = action.parameters.get("low_budget_person", "one of us")
        return f"heads up: shifting the hotel search to a cheaper area of {action.target} so {low}'s budget fits. new picks coming."
    if action.kind == "hold_rooms_48h":
        cands = action.parameters.get("candidates") or ["both cities"]
        return f"we can't agree on a city. i'm holding one room in each of {' + '.join(cands)} for 48h — first to say 'no' vetoes."
    if action.kind == "ask_group":
        return "quick check — what's the top-end budget per person? need a ceiling before i can shop hotels."
    return "trip's on track. nothing i need from you right now."


# ─── Demo runner (rule-based, no API key required) ─────────────────────────
_SAMPLES: dict[str, dict] = {
    "city_tie": {
        "city": None,
        "dates": {"start": "2027-05-01", "end": "2027-05-07"},
        "budget_per_person": 2000,
        "group_size": 4,
        "per_person": {
            "alice": {"budget": 2000, "city": "Tokyo", "dates": {"start": "2027-05-01", "end": "2027-05-07"}},
            "bob":   {"budget": None, "city": "Kyoto", "dates": {}},
            "carla": {"budget": 2000, "city": "Tokyo", "dates": {}},
            "dave":  {"budget": 2200, "city": "Kyoto", "dates": {"start": "2027-05-01", "end": "2027-05-31"}},
        },
        "blockers": ["city_tie: TIE between Tokyo, Kyoto (2 votes each)"],
        "notes":    {"city": "TIE between Tokyo, Kyoto (2 votes each)"},
    },
    "no_date_overlap": {
        "city": "Tokyo",
        "dates": {"start": None, "end": None},
        "budget_per_person": 1800,
        "group_size": 4,
        "per_person": {
            "alice": {"budget": None, "city": "Tokyo", "dates": {"start": "2027-05-25", "end": "2027-06-07"}},
            "bob":   {"budget": None, "city": "Tokyo", "dates": {"start": "2027-05-25", "end": "2027-06-07"}},
            "carla": {"budget": 1800, "city": "Tokyo", "dates": {"start": "2027-05-25", "end": "2027-05-31"}},
            "dave":  {"budget": 1800, "city": "Tokyo", "dates": {"start": "2027-06-01", "end": "2027-06-07"}},
        },
        "blockers": ["date_no_overlap: no overlap (carla:2027-05-25→2027-05-31, dave:2027-06-01→2027-06-07)"],
        "notes":    {"dates": "no overlap ..."},
    },
    "low_budget_person": {
        "city": "Tokyo",
        "dates": {"start": "2027-04-12", "end": "2027-04-18"},
        "budget_per_person": 800,
        "group_size": 4,
        "per_person": {
            "alice": {"budget": None, "city": "Tokyo", "dates": {"start": "2027-04-12", "end": "2027-04-18"}},
            "bob":   {"budget": None, "city": "Tokyo", "dates": {}},
            "carla": {"budget": 1500, "city": "Tokyo", "dates": {}},
            "dave":  {"budget": 800,  "city": "Tokyo", "dates": {}},
        },
        "blockers": [],
        "notes":    {},
    },
}


def _print_run(name: str, state: dict, b: Blocker, a: Action, msg: str) -> None:
    print(f"\n{'=' * 62}\n{name}\n{'=' * 62}")
    print(f"blocker: {b.kind:8s} subject={b.subject!r} source={b.source}")
    print(f"         detail: {b.detail}")
    print(f"action : {a.kind:32s} target={a.target!r}")
    print(f"         rationale: {a.rationale}")
    if a.parameters:
        print(f"         params: {a.parameters}")
    print(f"phoebe → {msg}")


def main() -> None:
    for name, state in _SAMPLES.items():
        b = diagnose(state)
        a = decide_action(b, state)
        msg = compose_message(a, state)
        _print_run(name, state, b, a, msg)


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    main()
