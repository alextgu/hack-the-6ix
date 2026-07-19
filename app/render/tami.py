"""Tami the sushi pet — real-art asset resolver.

18 fully-baked PNGs live in `assets/tami/`, one per
(physical × expression × rotten) combo:

    {Rotten_?}{Full|Mid|Low}_{Happy|Mid|Sad}.png

    physical  : Full | Mid | Low   — physical health (hotel market pressure)
                  >70 Full, 40–70 Mid, <40 Low
    expression: Happy | Mid | Sad  — mental health
                  >70 Happy, 40–70 Mid, <40 Sad
    rotten    : prefix when mental < 50

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

# Public aliases kept for the /api/pet preview grid + callers.
SIZES = ("Full", "Mid", "Low")
EXPRESSIONS = ("Happy", "Mid", "Sad")
# Legacy names some callers still import
FEELINGS = ("happy", "mid", "sad")
MOLDS = ("clean", "rotten")


def physical_tier(physical: int) -> str:
    """Above 70 Full, 40–70 Mid, below 40 Low."""
    if physical > 70:
        return "Full"
    if physical >= 40:
        return "Mid"
    return "Low"


def expression_tier(mental: int) -> str:
    """Above 70 Happy, 40–70 Mid, below 40 Sad."""
    if mental > 70:
        return "Happy"
    if mental >= 40:
        return "Mid"
    return "Sad"


def is_rotten(mental: int) -> bool:
    """Mental below 50 → rotten sprite."""
    return mental < 50


def normalize_feeling(feeling: str | None) -> str:
    """Legacy helper — Gemini face buckets map onto expression filenames."""
    if feeling in FEELINGS:
        return feeling.capitalize() if feeling != "mid" else "Mid"
    if feeling in EXPRESSIONS:
        return feeling
    return "Mid"


def sushi_filename(physical: int, mental: int, feeling: str | None = None) -> str:
    """Resolve the PNG name. Expression is driven by mental health (art spec).
    `feeling` is accepted for call-site compatibility but ignored — the
    attached 18-sprite set encodes Happy/Mid/Sad from the mental bar."""
    del feeling  # reserved; mental bar owns expression
    phys = physical_tier(physical)
    expr = expression_tier(mental)
    if is_rotten(mental):
        return f"Rotten_{phys}_{expr}.png"
    return f"{phys}_{expr}.png"


def sushi_path(physical: int, mental: int, feeling: str | None = None) -> str:
    return os.path.join(TAMI_DIR, sushi_filename(physical, mental, feeling))


def load_sushi_image(physical: int, mental: int, feeling: str | None = None):
    """Return a Pillow RGBA Image for this state, or None if the asset is
    missing/unreadable. Never raises — callers fall back to placeholder art."""
    from PIL import Image
    path = sushi_path(physical, mental, feeling)
    try:
        return Image.open(path).convert("RGBA")
    except (OSError, ValueError) as e:
        log.warning("tami asset missing/unreadable: %s (%s)", path, e)
        return None
