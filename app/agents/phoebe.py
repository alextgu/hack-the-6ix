"""Phoebe agent — the diagnose-target-convince loop.

Its own model seam (PIPELINE.md). Provider-swappable via PHOEBE_PROVIDER=
without touching Read's brain.py. Not yet wired to the bot — standalone
__main__ exercises the diagnose → decide_action → compose_message flow
against 3 sample states.

Personality lives here: outreach copy is written in Sushi-kun's voice —
playful, needy, "i'm dying here, help me" — via agent_call().
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


BlockerKind = Literal["person", "timing", "issue", "none"]
ActionKind = Literal[
    "dm_holdout",
    "propose_cheaper_neighborhood",
    "hold_rooms_48h",
    "ask_group",
    "no_action",
]


@dataclass
class Blocker:
    kind: BlockerKind
    subject: str
    detail: str
    source: str


@dataclass
class Action:
    kind: ActionKind
    target: str
    rationale: str
    parameters: dict = field(default_factory=dict)


# ─── agent_call — the AGENT seam. SEPARATE from brain.call_model. ──────────
_DEFAULT_MODEL_BY_PROVIDER = {
    # "gemini-flash-latest" tracks whatever the current fast Flash is. Pinned
    # ids rot: the old default here (gemini-2.5-flash) started 404ing with
    # "no longer available to new users", and because compose_message swallows
    # errors into _canned(), the failure was invisible — Sushi-kun just quietly
    # served the same canned line forever instead of speaking.
    "gemini":    "gemini-flash-latest",
    "anthropic": "claude-haiku-4-5-20251001",  # fast, cheap default
}


def agent_call(prompt: str) -> str:
    """The one place Phoebe hits a model. Selection order:

      1. FREESOLO_AGENT_BASE_URL set → OpenAI-compatible Freesolo endpoint
         (model = FREESOLO_AGENT_MODEL).
      2. PHOEBE_PROVIDER (default "gemini") → dispatch to _call_gemini or
         _call_anthropic; model = PHOEBE_MODEL or the fast default.
      3. Clear error.

    Switching between Gemini and Anthropic is one env change:
      PHOEBE_PROVIDER=anthropic
    """
    fs_url = os.environ.get("FREESOLO_AGENT_BASE_URL", "").strip()
    fs_key = os.environ.get("FREESOLO_API_KEY", "").strip()
    if fs_url and fs_key:
        return _call_freesolo(prompt, fs_url, fs_key)

    provider = (os.environ.get("PHOEBE_PROVIDER") or "gemini").strip().lower()
    if provider == "gemini":
        return _call_gemini(prompt)
    if provider == "anthropic":
        return _call_anthropic(prompt)
    raise RuntimeError(
        f"PHOEBE_PROVIDER={provider!r} not recognised. Use 'gemini' or 'anthropic', "
        "or set FREESOLO_AGENT_BASE_URL for the trained agent path."
    )


def _phoebe_model(provider: str) -> str:
    """PHOEBE_MODEL wins; for gemini, fall back to the same GEMINI_MODEL the
    rest of the app already pins so one env var keeps every surface on a live
    model instead of this one drifting onto a retired id by itself."""
    explicit = os.environ.get("PHOEBE_MODEL", "").strip()
    if explicit:
        return explicit
    if provider == "gemini":
        shared = os.environ.get("GEMINI_MODEL", "").strip()
        if shared:
            return shared
    return _DEFAULT_MODEL_BY_PROVIDER[provider]


def _call_freesolo(prompt: str, base_url: str, api_key: str) -> str:
    from openai import OpenAI
    client = OpenAI(base_url=base_url.rstrip("/"), api_key=api_key, timeout=20)
    resp = client.chat.completions.create(
        model=os.environ.get("FREESOLO_AGENT_MODEL", "phoebe-agent-v1"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=512,
    )
    return (resp.choices[0].message.content or "").strip()


def _call_gemini(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Free key: https://aistudio.google.com/apikey"
        )
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel(_phoebe_model("gemini"))
    resp = model.generate_content(prompt, request_options={"timeout": 20})
    return (resp.text or "").strip()


def _call_anthropic(prompt: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Get one: https://console.anthropic.com/settings/keys"
        )
    from anthropic import Anthropic
    client = Anthropic(api_key=key, timeout=20)
    resp = client.messages.create(
        model=_phoebe_model("anthropic"),
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in resp.content if hasattr(b, "text")]
    return "".join(parts).strip()


# ─── diagnose — flags first, LLM only for what flags miss ──────────────────
_FUZZY_DIAGNOSE_PROMPT = """You read a group chat's reconciled trip state and return the ONE binding blocker.

State (JSON):
{state}

The deterministic flags below have ALREADY been checked and NONE fired:
city_tie, date_no_overlap, budget_missing, low_budget_person, silent_person.

Only look for FUZZY blockers those miss:
- someone hinted "not really my vibe" / lukewarm agreement / conditional yes
- keeps adding conditions ("if…", "maybe if…")
- verbal yes but no concrete date/city/budget commitment
- vibe mismatch (party crowd vs quiet crowd)

Return ONLY JSON, no prose or preamble:
{{"kind":"person|timing|issue|none","subject":"<name|dates|city|vibe|budget|none>","detail":"<one-line human>","source":"llm.<slug>"}}

If nothing binding: {{"kind":"none","subject":"none","detail":"trip on track","source":"llm.no_blocker"}}"""


def diagnose(reconciled_state: dict) -> Blocker:
    """Return the ONE binding blocker. Uses brain.py's deterministic flags
    first (no LLM); escalates to agent_call() only when flags say clean."""
    blockers: list[str] = reconciled_state.get("blockers", []) or []
    per_person: dict = reconciled_state.get("per_person", {}) or {}

    # P1 — city TIE
    for b in blockers:
        if b.startswith("city_tie"):
            return Blocker(kind="issue", subject="city", detail=b, source="brain.city_tie")

    # P2 — no date overlap
    for b in blockers:
        if b.startswith("date_no_overlap"):
            return Blocker(kind="timing", subject="dates", detail=b, source="brain.date_no_overlap")

    # P3 — a single person's budget is well below the group median
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

    # P5 — silent holdout
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

    # P6 — flags say clean. Ask the LLM about fuzzy blockers we might miss.
    try:
        raw = agent_call(_FUZZY_DIAGNOSE_PROMPT.format(
            state=json.dumps(reconciled_state, default=str)[:4000]
        ))
        data = _first_json_object(raw)
        if data and data.get("kind") in ("person", "timing", "issue", "none"):
            return Blocker(
                kind=data["kind"],
                subject=str(data.get("subject", "none")),
                detail=str(data.get("detail", "")),
                source=str(data.get("source", "llm.unknown")),
            )
    except Exception:
        # LLM unavailable is fine — the flags said we're clean.
        pass

    return Blocker(kind="none", subject="none",
                   detail="no binding blocker — trip is on track",
                   source="rule.no_blocker")


def _first_json_object(text: str) -> dict | None:
    """Pull the first {...} from the model's response — some backends wrap in prose."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ─── decide_action — pure rules, no LLM ────────────────────────────────────
def _tie_candidates(detail: str) -> list[str]:
    m = re.search(r"between (.+?)(?: \(| \d|$)", detail)
    if not m:
        return []
    return [c.strip() for c in m.group(1).split(",") if c.strip()]


def decide_action(blocker: Blocker, state: dict) -> Action:
    """Map blocker → resolution move. PROJECT.md §6: remove the objection,
    don't push on it."""
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
            parameters={"hold_hours": 48, "candidates": _tie_candidates(blocker.detail)},
        )
    if blocker.subject == "dates":
        return Action(
            kind="dm_holdout",
            target="group",
            rationale="No date overlap — ask each person for their must-hold days",
            parameters={"channel": "dm_each"},
        )
    if blocker.subject == "budget":
        return Action(
            kind="ask_group",
            target="group",
            rationale="Nobody stated a budget — ask directly in the chat",
        )
    return Action(kind="no_action", target="group", rationale="nothing to resolve")


# ─── compose_message — Sushi-kun's voice via agent_call ────────────────────
_SUSHI_VOICE = """You are Sushi-kun, the little pet living in a group chat that's trying to plan a trip to Japan.
You are charming, never a sad-sack, and you have real stakes: this group's
indecision is killing you.

{voice_block}

Write ONE message (max 220 chars) that executes this action.
Reply with ONLY the message text — no quotes, no preamble.

Action: {action_kind}
Target: {target}
Rationale: {rationale}
Extra: {parameters}

Trip so far:
  city:   {city}
  dates:  {dates}
  budget: ${budget}"""


def compose_message(action: Action, state: dict,
                    chat_id: Optional[int] = None) -> str:
    """Sushi-kun's outreach in-character. LLM writes it; canned fallback only
    when no model is configured at all."""
    from app.agents import voice   # local: keeps the agent seam import-light
    prompt = _SUSHI_VOICE.format(
        voice_block=voice.persona_block(chat_id=chat_id, name="Sushi-kun"),
        action_kind=action.kind,
        target=action.target,
        rationale=action.rationale,
        parameters=json.dumps(action.parameters or {}),
        city=state.get("city"),
        dates=state.get("dates"),
        budget=state.get("budget_per_person"),
    )
    try:
        out = agent_call(prompt).strip()
        # some models return wrapped in quotes — strip once.
        if out.startswith(('"', "'")) and out.endswith(('"', "'")):
            out = out[1:-1].strip()
        if out and chat_id is not None:
            voice.note_line(chat_id, out)
        return out or _canned(action)
    except Exception as e:
        print(f"[phoebe] agent_call failed ({type(e).__name__}: {e}); using canned line")
        return _canned(action)


def _canned(action: Action) -> str:
    """Offline fallback when no model is configured. Several options per action
    and a random pick, because the fallback firing twice in one demo used to
    print the exact same sentence both times."""
    import random
    t = action.target
    if action.kind == "dm_holdout":
        return random.choice([
            f"@{t} — quick one. what days can you actually go, and what's your ceiling",
            f"@{t}. two numbers. dates and a budget. that's the whole ask",
            f"everyone's waiting on you, {t}. when can you go and for how much",
        ])
    if action.kind == "propose_cheaper_neighborhood":
        low = action.parameters.get("low_budget_person", "someone")
        return random.choice([
            f"rerouting to a cheaper part of {t} so {low}'s budget actually fits. new picks incoming",
            f"{low}'s number doesn't work in central {t}. pulling options a few stops out",
            f"same {t}, cheaper postcode. give me a second and {low} can afford it too",
        ])
    if action.kind == "hold_rooms_48h":
        cands = action.parameters.get("candidates") or ["both"]
        joined = " + ".join(cands)
        return random.choice([
            f"you can't pick a city. holding a room in each of {joined} for 48h — someone object",
            f"fine. {joined}. one room each, 48 hours, then i pick for you",
            f"nobody's deciding, so i am: rooms held in {joined} till thursday",
        ])
    if action.kind == "ask_group":
        return random.choice([
            "what's the top-end budget per person. i can't shop hotels blind",
            "give me a ceiling. any number. i'll work with anything",
            "one budget figure and i can actually start being useful",
        ])
    return random.choice([
        "trip's on track. i'll nap till you need me",
        "nothing for me to do. suspicious. i'll be here",
        "we're actually fine right now. weird feeling",
    ])


# ─── Demo runner ───────────────────────────────────────────────────────────
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
    },
}


def _print_run(name: str, b: Blocker, a: Action, msg: str) -> None:
    print(f"\n{'=' * 62}\n{name}\n{'=' * 62}")
    print(f"blocker: {b.kind:8s} subject={b.subject!r} source={b.source}")
    print(f"         detail: {b.detail}")
    print(f"action : {a.kind:32s} target={a.target!r}")
    print(f"         rationale: {a.rationale}")
    if a.parameters:
        print(f"         params: {a.parameters}")
    print(f"sushi → {msg}")


def main() -> None:
    provider = os.environ.get("PHOEBE_PROVIDER", "gemini")
    fs_url = os.environ.get("FREESOLO_AGENT_BASE_URL", "").strip()
    print(f"[phoebe] provider = {'freesolo' if fs_url else provider}  "
          f"model = {_phoebe_model('gemini') if provider == 'gemini' else _phoebe_model('anthropic') if provider == 'anthropic' else 'freesolo:' + os.environ.get('FREESOLO_AGENT_MODEL', 'phoebe-agent-v1')}")
    for name, state in _SAMPLES.items():
        b = diagnose(state)
        a = decide_action(b, state)
        msg = compose_message(a, state)
        _print_run(name, b, a, msg)


if __name__ == "__main__":
    main()
