"""ElevenLabs text-to-speech client.

Not wired into the bot yet — bot.py's TODO seams call this once the
mood → voice cooldown lane is built.
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Optional


ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def text_to_speech(
    text: str,
    voice_id: Optional[str] = None,
    model_id: str = "eleven_multilingual_v2",
) -> Optional[bytes]:
    """Synthesize `text` and return raw MP3 bytes, or None on failure.

    voice_id defaults to ELEVENLABS_VOICE_ID; ELEVENLABS_API_KEY must be set."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = (voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")).strip()
    if not (api_key and voice and text):
        return None

    url = ENDPOINT.format(voice_id=voice)
    body = json.dumps({
        "text": text,
        "model_id": model_id,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"[elevenlabs] text_to_speech failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    audio = text_to_speech("The group chat has gone quiet. Someone say something.")
    if audio:
        with open("elevenlabs_test.mp3", "wb") as f:
            f.write(audio)
        print(f"wrote elevenlabs_test.mp3 ({len(audio)} bytes)")
    else:
        print("failed — check ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID")
