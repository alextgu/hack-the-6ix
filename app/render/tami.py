"""Tami the sushi pet — real-art asset resolver.

18 fully-baked PNGs live in `assets/tami/`, one per
(size × mold × feeling) combo:

    sushi_{size}_{mold}_{feeling}.png

    size    : full | half | small  — physical health (booking pressure)
    mold    : clean | moldy        — mental health (group vibe)
    feeling : happy | mid | sad    — sentiment of Tabi's last outgoing
                                      message, classified by Gemini
                                      (see app/agents/face.py)

This module owns the bucket thresholds and the filename convention only —
no PIL here, so both the chat-image renderer (app/render/pet.py) and the
Telegram profile-photo swapper (app/integrations/telegram_avatar.py) resolve
to the exact same file for a given state.
"""
from __future__ import annotations
import logging
import os

log = logging.getLogger("trippet.tami")

TAMI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "assets", "tami")

SIZES = ("full", "half", "small")
MOLDS = ("clean", "moldy")
FEELINGS = ("happy", "mid", "sad")


def size_tier(physical: int) -> str:
    """70+ full, 40-70 half, 40 and below small (PROJECT.md pet art spec)."""
    if physical >= 70:
        return "full"
    if physical > 40:
        return "half"
    return "small"


def mold_tier(mental: int) -> str:
    """Below 50 mental -> moldy; 50+ -> clean."""
    return "clean" if mental >= 50 else "moldy"


def normalize_feeling(feeling: str | None) -> str:
    return feeling if feeling in FEELINGS else "mid"


def sushi_filename(physical: int, mental: int, feeling: str | None) -> str:
    return (f"sushi_{size_tier(physical)}_{mold_tier(mental)}_"
            f"{normalize_feeling(feeling)}.png")


def sushi_path(physical: int, mental: int, feeling: str | None) -> str:
    return os.path.join(TAMI_DIR, sushi_filename(physical, mental, feeling))


def load_sushi_image(physical: int, mental: int, feeling: str | None):
    """Return a Pillow RGBA Image for this state, or None if the asset is
    missing/unreadable. Never raises — callers fall back to placeholder art."""
    from PIL import Image
    path = sushi_path(physical, mental, feeling)
    try:
        return Image.open(path).convert("RGBA")
    except (OSError, ValueError) as e:
        log.warning("tami asset missing/unreadable: %s (%s)", path, e)
        return None
