"""ElevenLabs text-to-speech — mood-aware voice selection + OGG/Opus
conversion for Telegram voice notes.

The voice is chosen by the pet's mood/health so a dying pet sounds different
from a healthy one (emotional inflection):
  - sick / dying (low physical health) → ELEVENLABS_VOICE_DYING
  - happy / worried / graduated        → ELEVENLABS_VOICE_ALIVE
  - if a mood-specific voice is unset, fall back to ELEVENLABS_VOICE_ID
    (legacy single voice), then to whichever voice IS set.

Never raises to callers — returns None on any failure so the bot degrades to
plain text.
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
from typing import Optional


log = logging.getLogger("trippet.voice")

ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Moods (or a low physical bar) that mean the pet is in trouble → dying voice.
_DYING_MOODS = {"sick", "dying"}
_DYING_PHYSICAL = 40


def available() -> bool:
    """Is voice actually configured? Callers use this to decide whether to even
    attempt speech, rather than synthesizing and silently falling back."""
    return bool(os.environ.get("ELEVENLABS_API_KEY", "").strip()
                and _voice_for(None, None))


def _voice_for(mood: Optional[str], physical: Optional[int]) -> str:
    """Pick a voice id from mood/health. Guarantees a non-empty id as long as
    ANY of the three env voices is set — this is what fixes the /api/speak 502
    (the old code only read ELEVENLABS_VOICE_ID, which .env never defined)."""
    alive = os.environ.get("ELEVENLABS_VOICE_ALIVE", "").strip()
    dying = os.environ.get("ELEVENLABS_VOICE_DYING", "").strip()
    legacy = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()  # single-voice fallback

    is_dying = mood in _DYING_MOODS or (physical is not None and physical < _DYING_PHYSICAL)
    if is_dying:
        return dying or legacy or alive
    return alive or legacy or dying


def _tts(text: str, voice: str, api_key: str, model_id: str,
         output_format: Optional[str], accept: str) -> Optional[bytes]:
    """One synthesis call. `output_format` None → the API's mp3 default."""
    url = ENDPOINT.format(voice_id=voice)
    if output_format:
        url += f"?output_format={output_format}"
    body = json.dumps({"text": text, "model_id": model_id}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"xi-api-key": api_key, "Content-Type": "application/json",
                 "Accept": accept},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        log.warning("text_to_speech failed (%s): %s: %s",
                    output_format or "mp3", type(e).__name__, e)
        return None


def text_to_speech(
    text: str,
    voice_id: Optional[str] = None,
    mood: Optional[str] = None,
    physical: Optional[int] = None,
    model_id: str = "eleven_multilingual_v2",
) -> Optional[bytes]:
    """Synthesize `text` → raw MP3 bytes, or None on failure.

    Voice resolution: an explicit `voice_id` wins; otherwise it's picked from
    `mood`/`physical`. ELEVENLABS_API_KEY must be set."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = (voice_id or _voice_for(mood, physical)).strip()
    if not (api_key and voice and text):
        return None
    return _tts(text, voice, api_key, model_id, None, "audio/mpeg")


# Telegram voice notes must be OGG/Opus. ElevenLabs can return exactly that if
# you ask for it — which removes the ffmpeg dependency entirely. That matters:
# the runtime image is python:3.12-slim with no ffmpeg, so to_ogg_opus() has
# been returning None in production since day one and EVERY voice note has
# silently degraded to a plain-text message. Synthesis was never the problem.
OPUS_FORMAT = "opus_48000_64"


def text_to_opus(
    text: str,
    voice_id: Optional[str] = None,
    mood: Optional[str] = None,
    physical: Optional[int] = None,
    model_id: str = "eleven_multilingual_v2",
) -> Optional[bytes]:
    """Synthesize straight to OGG/Opus bytes Telegram can send as a voice note."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = (voice_id or _voice_for(mood, physical)).strip()
    if not (api_key and voice and text):
        return None
    data = _tts(text, voice, api_key, model_id, OPUS_FORMAT, "audio/ogg")
    if data and data[:4] != b"OggS":
        log.warning("expected an OGG container, got %r — discarding", data[:4])
        return None
    return data


def to_ogg_opus(mp3_bytes: bytes) -> Optional[bytes]:
    """Convert MP3 → OGG/Opus (the format Telegram send_voice wants) via
    ffmpeg. Returns None if ffmpeg is missing or the conversion fails, so the
    caller can fall back to a plain-text message."""
    if not mp3_bytes:
        return None
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", "pipe:0", "-c:a", "libopus", "-b:a", "48k", "-f", "ogg", "pipe:1"],
            input=mp3_bytes,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        log.warning("ffmpeg not found — cannot build a Telegram voice note; caller falls back to text")
        return None
    except Exception as e:
        log.warning("ogg conversion failed: %s: %s", type(e).__name__, e)
        return None
    if proc.returncode != 0 or not proc.stdout:
        log.warning("ffmpeg exit=%s: %s", proc.returncode, proc.stderr[:200].decode("utf-8", "replace"))
        return None
    return proc.stdout


def synthesize_voice_note(
    text: str, mood: Optional[str] = None, physical: Optional[int] = None
) -> Optional[bytes]:
    """text → mood-appropriate OGG/Opus voice-note bytes, or None on any
    failure (missing key/voice, ElevenLabs error). The bot posts plain text
    when this returns None.

    Asks ElevenLabs for Opus directly; only falls back to mp3+ffmpeg if that
    request fails, so a host without ffmpeg (which includes ours) still gets
    voice notes."""
    opus = text_to_opus(text, mood=mood, physical=physical)
    if opus:
        return opus
    log.info("native opus unavailable — trying mp3 + ffmpeg")
    mp3 = text_to_speech(text, mood=mood, physical=physical)
    if not mp3:
        return None
    return to_ogg_opus(mp3)


STT_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"


def transcribe(audio_bytes: bytes, mime: str = "audio/ogg",
               model_id: str = "scribe_v1") -> Optional[str]:
    """Speech-to-text via ElevenLabs Scribe. Telegram voice notes are OGG/Opus.
    Returns the transcript, or None on any failure (missing key, network, empty
    result) so the caller can fall back to a text reply. Never raises."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not (api_key and audio_bytes):
        return None

    boundary = "----trippetvoiceboundary7a1b2c3d"
    pre = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model_id"\r\n\r\n{model_id}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="audio.ogg"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    body = pre + audio_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        STT_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "xi-api-key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        log.warning("transcribe failed: %s: %s", type(e).__name__, e)
        return None
    return (str(data.get("text") or "").strip()) or None


if __name__ == "__main__":
    # Standalone check: generate one clip in each voice so you can play them
    # and confirm the dying vs alive voices sound different. Saves local files;
    # prints the result. No doc files written.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    cases = [
        ("dying", "i'm fading... the prices are eating me alive. please, just book something."),
        ("happy", "we did it — i'm free! pack your bags, we're going to japan."),
    ]
    for mood, line in cases:
        vid = _voice_for(mood, None)
        mp3 = text_to_speech(line, mood=mood)
        if mp3:
            with open(f"voice_{mood}.mp3", "wb") as f:
                f.write(mp3)
            line_out = f"[{mood:5}] voice_id={vid or 'UNSET'} → voice_{mood}.mp3 ({len(mp3)} bytes)"
            ogg = to_ogg_opus(mp3)
            if ogg:
                with open(f"voice_{mood}.ogg", "wb") as f:
                    f.write(ogg)
                line_out += f"  |  ogg ok ({len(ogg)} bytes)"
            else:
                line_out += "  |  ogg conversion unavailable (ffmpeg?)"
            print(line_out)
        else:
            print(f"[{mood:5}] FAILED voice_id={vid or 'UNSET'} — check ELEVENLABS_API_KEY / "
                  "ELEVENLABS_VOICE_ALIVE / ELEVENLABS_VOICE_DYING")

    a, d = _voice_for("happy", None), _voice_for("dying", None)
    if a and d and a == d:
        print("⚠  ALIVE and DYING resolve to the SAME voice id — they will sound identical. "
              "Set ELEVENLABS_VOICE_ALIVE and ELEVENLABS_VOICE_DYING to different voices.")
    elif a and d:
        print(f"✓ two distinct voices — alive={a}  dying={d}")
