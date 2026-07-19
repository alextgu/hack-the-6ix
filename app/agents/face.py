"""Face seam — Gemini only, permanently.

Classifies the feeling of ONE outgoing Tabi message into exactly one of the
3 face expressions the art supports (happy/mid/sad — see app/render/tami.py),
so the pet's face in the chat image AND its Telegram profile photo both
match how the message it just sent actually reads.

`call_model()` is the ONE place the LLM is called here — isolated and
swappable (a Freesolo model could replace it later) per CLAUDE.md. Kept
separate from supervisor.py's messenger call (which IS Freesolo-swappable)
so the face read is always Gemini, never whatever model wrote the message.

Usage:
    GEMINI_API_KEY=xxx python -m app.agents.face
"""
from __future__ import annotations
import json
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger("trippet.face")

# "gemini-flash-latest" tracks the current fast Flash. Pinned ids rot:
# gemini-2.0-flash-exp is retired and 404s, so this default only ever
# worked because GEMINI_MODEL happened to be set in the environment.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
FEELINGS = ("happy", "mid", "sad")


def call_model(text: str) -> str:
    """The only place we hit a model for the Face layer. Returns raw JSON string."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    resp = model.generate_content(
        _PROMPT + text,
        generation_config={"response_mime_type": "application/json"},
        request_options={"timeout": 10},  # face pick must never stall a send
    )
    return resp.text


_PROMPT = """You are picking a facial expression for a tamagotchi sushi pet
named Tabi, based on the feeling of ONE message it is about to send to its
group chat. Read the message's tone (not its topic) and classify it into
exactly one of three buckets:

  "happy" — upbeat, celebratory, warmly excited, proud of the group
  "mid"   — neutral, businesslike, just asking/informing, mildly concerned
  "sad"   — guilt-tripping, worried, frustrated, pleading, health is low

Return ONLY valid JSON: {"feeling": "happy" | "mid" | "sad"}

MESSAGE:
"""


def classify_feeling(text: str) -> str:
    """Best-effort sentiment bucket for `text`. Never raises — falls back to
    "mid" on a missing key, network error, or unparseable reply, so a Gemini
    hiccup never blocks a send."""
    if not text or not text.strip():
        return "mid"
    try:
        raw = call_model(text)
        data = json.loads(raw)
        feeling = data.get("feeling")
        return feeling if feeling in FEELINGS else "mid"
    except Exception as e:
        log.info("face classification failed, defaulting to mid: %s", e)
        return "mid"


if __name__ == "__main__":
    import sys
    sample = " ".join(sys.argv[1:]) or "we did it — i'm free! pack your bags."
    print(classify_feeling(sample))
