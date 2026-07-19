"""Multimodal message pipeline — Telegram messages (text + photos) → structured
per-message JSON for the Phoebe diagnose-target-convince agent (PROJECT.md §6).

Distinct from brain.py: brain.py reconciles the WHOLE chat transcript into
trip constraints (city/dates/budget). This module looks at messages ONE AT A
TIME, multimodally (text and/or an attached photo — a screenshot of prices, an
itinerary, a calendar), timestamps each one, extracts/OCRs its content, and
classifies it as a blocker signal so Phoebe can see *who* said *what*, *when*,
and whether it's the thing keeping the trip stuck.

`call_model()` is the ONE place the LLM is called — swap for Freesolo later
without touching analyze_message / analyze_batch / to_phoebe_payload.

Usage:
    GEMINI_API_KEY=xxx python gemini.py

Get a free Gemini key: https://aistudio.google.com/apikey

If the key is missing the script still runs against FIXTURE_ANALYSES so you
can see the batching / Phoebe-payload shape work.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Optional, TypedDict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ─── ONE place the model is called ──────────────────────────────────────────
# "gemini-flash-latest" tracks the current fast Flash. Pinned ids rot:
# gemini-2.0-flash-exp is retired and 404s, so this default only ever
# worked because GEMINI_MODEL happened to be set in the environment.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def call_model(parts: list) -> str:
    """The only place we hit the model. `parts` is a list of Gemini content
    parts (str for text, {"mime_type": ..., "data": bytes} for an image).
    Returns raw JSON string.

    Later: swap the body for a Freesolo call. Keep the signature identical."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/apikey"
        )
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel(MODEL_NAME)
    resp = model.generate_content(
        parts,
        generation_config={"response_mime_type": "application/json"},
    )
    return resp.text


# ─── Input shape ────────────────────────────────────────────────────────────
class InMessage(TypedDict, total=False):
    sender: str
    text: Optional[str]
    image_bytes: Optional[bytes]
    mime_type: str            # e.g. "image/jpeg" — required if image_bytes set
    timestamp: str            # ISO8601; defaults to "now" if omitted


# ─── Prompt ─────────────────────────────────────────────────────────────────
_ANALYZE_PROMPT = """You analyze ONE message from a group chat that is planning a
trip to Japan, for a downstream agent (nicknamed "Phoebe") whose job is to find
the single blocker stalling the trip and resolve it.

The message may include a photo (a screenshot of hotel prices, a flight
itinerary, a calendar, a map, etc). If a photo is present, read any text in it
(OCR) and describe what it shows.

Return ONLY valid JSON matching this EXACT shape (all keys required, null/empty
if not applicable):

{
  "modality": "text" | "image" | "text+image",
  "extracted_text": <string>,
  "on_topic": <bool>,
  "mentions": {
    "city": [<string>, ...],
    "dates": [<string>, ...],
    "budget": <int USD or null>
  },
  "engagement": {
    "is_decision": <bool>,
    "is_question": <bool>,
    "sentiment": "positive" | "neutral" | "negative"
  },
  "blocker_signal": {
    "type": "person" | "timing" | "issue" | null,
    "detail": <string or null>
  }
}

RULES:
- "on_topic": false for off-topic chatter (memes, cats, unrelated banter) —
  this is a privacy/noise filter, same as the chat-level extractor.
- "extracted_text": the message's own text plus, if a photo is attached, what
  you read/see in it — concatenated into one plain-language string.
- "blocker_signal.type":
    "person"  — this message is (or names) a holdout, or a binding personal
                constraint (e.g. a budget cap far below the rest).
    "timing"  — this message signals a scheduling conflict or a stall/defer.
    "issue"   — this message signals a concrete disagreement (budget, city,
                dates) or pure decision paralysis (agreement without action).
    null      — no blocker signal in this message.
- Only set engagement.is_decision true if the message commits to something
  concrete (a date, a city, "I'm in"), not just discussion.

MESSAGE (sender: {sender}):
"""


# ─── analyze ────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def analyze_message(msg: InMessage) -> dict:
    """One Telegram message (text and/or photo) → structured, timestamped JSON."""
    sender = msg.get("sender") or "someone"
    text = msg.get("text") or ""
    image_bytes = msg.get("image_bytes")
    mime_type = msg.get("mime_type", "image/jpeg")
    timestamp = msg.get("timestamp") or _now_iso()

    parts: list = [_ANALYZE_PROMPT.format(sender=sender) + text]
    if image_bytes:
        parts.append({"mime_type": mime_type, "data": image_bytes})

    raw = call_model(parts)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"model returned non-JSON: {e}\n---\n{raw}") from e

    return _normalize(data, sender=sender, timestamp=timestamp, had_image=bool(image_bytes))


def _normalize(d: dict, *, sender: str, timestamp: str, had_image: bool) -> dict:
    """Fill missing keys with defaults; timestamp/sender/modality come from us,
    never the model, so downstream code can trust them."""
    mentions = d.get("mentions") or {}
    engagement = d.get("engagement") or {}
    blocker = d.get("blocker_signal") or {}
    modality = d.get("modality") or ("text+image" if had_image else "text")
    return {
        "sender": sender,
        "timestamp": timestamp,
        "modality": modality,
        "extracted_text": d.get("extracted_text") or "",
        "on_topic": bool(d.get("on_topic", True)),
        "mentions": {
            "city": mentions.get("city") or [],
            "dates": mentions.get("dates") or [],
            "budget": mentions.get("budget"),
        },
        "engagement": {
            "is_decision": bool(engagement.get("is_decision", False)),
            "is_question": bool(engagement.get("is_question", False)),
            "sentiment": engagement.get("sentiment") or "neutral",
        },
        "blocker_signal": {
            "type": blocker.get("type"),
            "detail": blocker.get("detail"),
        },
    }


def analyze_batch(messages: list[InMessage]) -> list[dict]:
    """Analyze each message independently (order preserved). One failure
    doesn't sink the batch — it's dropped with a printed warning."""
    out = []
    for msg in messages:
        try:
            out.append(analyze_message(msg))
        except Exception as e:
            print(f"⚠ skipping message from {msg.get('sender')}: {type(e).__name__}: {e}")
    return out


# ─── Phoebe payload ─────────────────────────────────────────────────────────
def to_phoebe_payload(chat_id: int, analyzed: list[dict]) -> dict:
    """Wrap analyzed messages into the envelope Phoebe (§6) consumes: a
    timeline plus a rollup of blocker signals ready for diagnose-target-convince."""
    on_topic = [m for m in analyzed if m["on_topic"]]
    blockers = [
        {"sender": m["sender"], "timestamp": m["timestamp"], **m["blocker_signal"]}
        for m in analyzed
        if m["blocker_signal"]["type"] is not None
    ]
    return {
        "chat_id": chat_id,
        "generated_at": _now_iso(),
        "message_count": len(analyzed),
        "on_topic_count": len(on_topic),
        "messages": analyzed,
        "blockers": blockers,
    }


# ─── Sample messages (text-only; image demo needs real bytes) ──────────────
SAMPLE_MESSAGES: list[InMessage] = [
    {"sender": "alice", "text": "yo japan when", "timestamp": "2027-03-01T10:00:00+00:00"},
    {"sender": "bob", "text": "down for tokyo, second week of april", "timestamp": "2027-03-01T10:01:00+00:00"},
    {"sender": "carla", "text": "i can only do $800 max, sorry", "timestamp": "2027-03-01T10:02:00+00:00"},
    {"sender": "dave", "text": "lol my cat knocked over a plant", "timestamp": "2027-03-01T10:03:00+00:00"},
    {"sender": "alice", "text": "carla you still thinking about it? we need your yes", "timestamp": "2027-03-02T09:00:00+00:00"},
]

FIXTURE_ANALYSES: list[dict] = [
    {"sender": "alice", "timestamp": "2027-03-01T10:00:00+00:00", "modality": "text",
     "extracted_text": "yo japan when", "on_topic": True,
     "mentions": {"city": [], "dates": [], "budget": None},
     "engagement": {"is_decision": False, "is_question": True, "sentiment": "neutral"},
     "blocker_signal": {"type": None, "detail": None}},
    {"sender": "bob", "timestamp": "2027-03-01T10:01:00+00:00", "modality": "text",
     "extracted_text": "down for tokyo, second week of april", "on_topic": True,
     "mentions": {"city": ["Tokyo"], "dates": ["2027-04-12/2027-04-18"], "budget": None},
     "engagement": {"is_decision": True, "is_question": False, "sentiment": "positive"},
     "blocker_signal": {"type": None, "detail": None}},
    {"sender": "carla", "timestamp": "2027-03-01T10:02:00+00:00", "modality": "text",
     "extracted_text": "i can only do $800 max, sorry", "on_topic": True,
     "mentions": {"city": [], "dates": [], "budget": 800},
     "engagement": {"is_decision": False, "is_question": False, "sentiment": "negative"},
     "blocker_signal": {"type": "person", "detail": "carla's $800 cap is likely below group median"}},
    {"sender": "dave", "timestamp": "2027-03-01T10:03:00+00:00", "modality": "text",
     "extracted_text": "lol my cat knocked over a plant", "on_topic": False,
     "mentions": {"city": [], "dates": [], "budget": None},
     "engagement": {"is_decision": False, "is_question": False, "sentiment": "neutral"},
     "blocker_signal": {"type": None, "detail": None}},
    {"sender": "alice", "timestamp": "2027-03-02T09:00:00+00:00", "modality": "text",
     "extracted_text": "carla you still thinking about it? we need your yes", "on_topic": True,
     "mentions": {"city": [], "dates": [], "budget": None},
     "engagement": {"is_decision": False, "is_question": True, "sentiment": "neutral"},
     "blocker_signal": {"type": "person", "detail": "group is waiting on carla to confirm"}},
]


# ─── main ───────────────────────────────────────────────────────────────────
def main() -> None:
    have_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    chat_id = 12345

    if not have_key:
        print("⚠  GEMINI_API_KEY not set — using FIXTURE_ANALYSES so you can")
        print("   still see the batching / Phoebe-payload shape. Get a free key at:")
        print("   https://aistudio.google.com/apikey\n")
        payload = to_phoebe_payload(chat_id, FIXTURE_ANALYSES)
    else:
        analyzed = analyze_batch(SAMPLE_MESSAGES)
        payload = to_phoebe_payload(chat_id, analyzed)

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
