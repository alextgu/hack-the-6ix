"""Swap the bot's own Telegram profile photo to match the pet's mood, via a
raw call to `setMyProfilePhoto` (Bot API 8.2+). python-telegram-bot is
pinned to <22 (see requirements.txt) and doesn't expose this method yet, so
this goes straight to the HTTP API with urllib instead of bumping a major
dependency version for one call.

IMPORTANT: this is the bot ACCOUNT's avatar — one photo, shared by every chat
the bot is in. There is no per-chat avatar in the Bot API. If the bot is ever
running in more than one active group at once, whichever group's mood changes
last wins the avatar for all of them. Fine for a single-demo-chat bot; would
need rethinking (e.g. stop auto-swapping, or scope to "primary" chat only) if
that changes.

Never raises to callers — returns False on any failure so a Telegram hiccup
or missing asset never breaks the chat flow.
"""
from __future__ import annotations
import json
import logging
import mimetypes
import os
import urllib.error
import urllib.request
import uuid

log = logging.getLogger("trippet.avatar")

FACES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "assets", "faces")

# pet.py's 5 mood tiers -> the 4 face files the user asked for.
# "graduated" (celebration) reuses the happy face — no separate asset yet.
_FACE_FOR_MOOD = {
    "happy":     "happy.jpg",
    "worried":   "alright.jpg",
    "sick":      "sad.jpg",
    "dying":     "death.jpg",
    "graduated": "happy.jpg",
}

_last_set_mood: str | None = None  # process-wide: one avatar for the whole bot


def _encode_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """Minimal multipart/form-data encoder — stdlib has no built-in one."""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
            .encode("utf-8")
        )
    for name, (filename, content) in files.items():
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'.encode("utf-8")
            + content + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def set_avatar_for_mood(token: str, mood: str, force: bool = False) -> bool:
    """POST the mood's face as the bot's profile photo. Deduped process-wide
    (skips the API call if `mood` is already the last one set) unless
    `force=True`. Returns True only on a confirmed Telegram success."""
    global _last_set_mood
    if not token or not mood:
        return False
    if mood == _last_set_mood and not force:
        return True

    filename = _FACE_FOR_MOOD.get(mood, _FACE_FOR_MOOD["happy"])
    path = os.path.join(FACES_DIR, filename)
    try:
        with open(path, "rb") as f:
            photo_bytes = f.read()
    except OSError as e:
        log.warning("avatar face missing (mood=%s path=%s): %s", mood, path, e)
        return False

    body, boundary = _encode_multipart(
        fields={"photo": json.dumps({"type": "static", "photo": "attach://photo_file"})},
        files={"photo_file": (filename, photo_bytes)},
    )
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/setMyProfilePhoto",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        log.warning("setMyProfilePhoto request failed (mood=%s): %s", mood, e)
        return False
    except Exception as e:
        log.warning("setMyProfilePhoto unexpected error (mood=%s): %s", mood, e)
        return False

    if not result.get("ok"):
        log.warning("setMyProfilePhoto rejected (mood=%s): %s", mood, result)
        return False

    _last_set_mood = mood
    log.info("bot avatar -> %s (%s)", mood, filename)
    return True
