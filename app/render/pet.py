"""Tami pet renderer — Pillow PNG, styled to match the webapp Mini App.

Ports the webapp's design tokens (design-system/tokens.css) straight into
Pillow drawing code — same cream/seigaiha background, white rounded cards,
Unbounded/Geist Sans type, same health-bar colors and layout — so the image
posted to chat looks like the same product as the Mini App, not a separate
placeholder style. Real sushi art (app/render/tami.py — 18 PNGs keyed by
size × mold × feeling) is composited into the pet-card exactly as the
webapp's <img id="pet-sprite"> does. Falls back to a drawn placeholder blob
if a sprite file is missing, so an incomplete art drop never breaks the chat
flow. The image is composed fresh on every state change and returned as
bytes so `bot.py` can call `send_photo(chat_id, InputFile(bytes))` — the
safe visual path (not a link preview) per PROJECT.md.

TODO seams:
  - When the pet talks (ElevenLabs later), add a speech-bubble overlay.
"""
from __future__ import annotations
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.core.state import GroupState, PetState
from app.render import tami


# ─── Design tokens — ported verbatim from design-system/tokens.css ─────────
BG = (237, 232, 208)          # --bg
SURFACE = (255, 255, 255)     # --surface
FG = (42, 36, 28)             # --fg
MUTED = (122, 114, 102)       # --muted
HEALTH_GOOD = (61, 154, 95)   # --health-good
HEALTH_WARN = (224, 138, 46)  # --health-warn
HEALTH_BAD = (209, 59, 46)    # --health-bad
CHIP_BG_ON_SURFACE = (42, 36, 28, 15)   # rgba(42,36,28,0.06) icon chip fill
TRACK_BG = (42, 36, 28, 26)             # rgba(42,36,28,0.1) bar track

RADIUS = 40      # --radius (28px in the 440-wide webapp, scaled to our canvas)
RADIUS_SM = 26   # --radius-sm

CANVAS = (640, 640)   # square, per spec: sprite + bars in one box, no header/caption
PAD = 28              # canvas edge -> card
INNER_PAD = 28         # card edge -> content (title / sprite / bars)

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "assets", "fonts")
PATTERN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "webapp", "assets", "seigaiha.png")


def _font(name: str, size: int) -> ImageFont.ImageFont:
    """`name` is one of the TTFs dropped in assets/fonts/ (Unbounded /
    GeistSans, matching the webapp's @font-face declarations). Falls back to
    a system font so a missing font file degrades, never crashes."""
    path = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:
        for candidate in (
            "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ):
            try:
                return ImageFont.truetype(candidate, size=size)
            except Exception:
                continue
        return ImageFont.load_default()


def _display(size: int) -> ImageFont.ImageFont:
    return _font("Unbounded-Regular.ttf", size)


def _display_medium(size: int) -> ImageFont.ImageFont:
    return _font("Unbounded-Medium.ttf", size)


def _body(size: int) -> ImageFont.ImageFont:
    return _font("GeistSans-Regular.ttf", size)


def _body_medium(size: int) -> ImageFont.ImageFont:
    return _font("GeistSans-Medium.ttf", size)


# ─── Background: cream + tiled seigaiha pattern at 0.14 opacity ────────────
_pattern_cache: Image.Image | None = None


def _tiled_background(size: tuple[int, int]) -> Image.Image:
    """Mirrors webapp/ds.css body::before: seigaiha.png tiled at 220px wide,
    14% opacity, over the cream --bg fill. Cached per-process since the tile
    art never changes at runtime."""
    global _pattern_cache
    img = Image.new("RGB", size, BG)
    if _pattern_cache is None:
        try:
            tile = Image.open(PATTERN_PATH).convert("RGBA")
            tw = 220
            th = max(1, int(tile.height * (tw / tile.width)))
            tile = tile.resize((tw, th), Image.LANCZOS)
            r, g, b, a = tile.split()
            a = a.point(lambda v: int(v * 0.14))
            _pattern_cache = Image.merge("RGBA", (r, g, b, a))
        except (OSError, ValueError):
            _pattern_cache = False  # sentinel: tried, missing — don't retry
    if _pattern_cache:
        tw, th = _pattern_cache.size
        for y in range(0, size[1], th):
            for x in range(0, size[0], tw):
                img.paste(_pattern_cache, (x, y), _pattern_cache)
    return img


# ─── Card chrome: white rounded rect with a soft drop shadow ───────────────
def _card(img: Image.Image, box: tuple[int, int, int, int], radius: int) -> None:
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x0, y0 + 10, x1, y1 + 10], radius=radius, fill=(*FG, 20))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    img.paste(shadow, (0, 0), shadow)
    ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, fill=SURFACE)


def _pill(img: Image.Image, box, radius: int, fill) -> None:
    """Rounded rect, alpha-composited through a transparent layer — drawing
    an RGBA fill directly on `img` (RGB) would silently drop the alpha and
    paint it fully opaque instead of blending."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=fill)
    img.paste(layer, (0, 0), layer)


# ─── Small vector icons (no icon font dependency — drawn directly) ─────────
def _icon_chip(img: Image.Image, cx: int, cy: int, size: int, draw_glyph) -> None:
    box = [cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=size // 3, fill=CHIP_BG_ON_SURFACE)
    img.paste(layer, (0, 0), layer)
    draw_glyph(ImageDraw.Draw(img), cx, cy, size)


def _heart_glyph(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    r = size * 0.19
    draw.ellipse([cx - 2 * r, cy - r * 1.1, cx, cy + r * 0.9], fill=FG)
    draw.ellipse([cx, cy - r * 1.1, cx + 2 * r, cy + r * 0.9], fill=FG)
    draw.polygon([(cx - 2 * r, cy + r * 0.15), (cx + 2 * r, cy + r * 0.15),
                  (cx, cy + r * 2.3)], fill=FG)


def _chat_glyph(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    w, h = size * 0.46, size * 0.34
    box = [cx - w, cy - h - size * 0.05, cx + w, cy + h - size * 0.05]
    draw.rounded_rectangle(box, radius=int(h * 0.6), fill=FG)
    tail_y = box[3]
    draw.polygon([(cx - w * 0.35, tail_y - 2), (cx - w * 0.05, tail_y - 2),
                  (cx - w * 0.35, tail_y + size * 0.16)], fill=FG)


# ─── Health color + bar ──────────────────────────────────────────────────
def _health_color(val: int) -> tuple[int, int, int]:
    if val >= 70:
        return HEALTH_GOOD
    if val >= 40:
        return HEALTH_WARN
    return HEALTH_BAD


def _bar_minimal(img: Image.Image, x: int, y: int, w: int, *, icon_glyph, val: int,
                 h: int = 28) -> int:
    """One health bar, no label/number — an icon chip (visual, not text) plus
    a colored pill track. Returns the y just past this bar."""
    icon_size = h + 6
    _icon_chip(img, x + icon_size // 2, y + h // 2, icon_size, icon_glyph)

    track_x0 = x + icon_size + 14
    track_x1 = x + w
    _pill(img, (track_x0, y, track_x1, y + h), h // 2, TRACK_BG)
    fill_w = int((track_x1 - track_x0) * max(0, min(100, val)) / 100)
    if fill_w > h:
        _pill(img, (track_x0, y, track_x0 + fill_w, y + h), h // 2, _health_color(val))

    return y + h


# ─── Sushi stage: shadow ellipse + sprite, matches webapp #stage/#pet-shadow
def _draw_sprite(img: Image.Image, cx: int, cy: int, pet: PetState, box: int) -> None:
    """`box` is the max width/height the sprite is scaled into, centered on
    (cx, cy) — sized by the caller to whatever room is left after the title
    and bars."""
    sprite = tami.load_sushi_image(pet.physical, pet.mental, pet.feeling)
    if sprite is None:
        _draw_pet_placeholder(ImageDraw.Draw(img), cx, cy, pet)
        return

    shadow_w, shadow_h = box * 0.29, box * 0.09
    shadow_y = cy + box * 0.39
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow_layer).ellipse(
        [cx - shadow_w, shadow_y, cx + shadow_w, shadow_y + shadow_h],
        fill=(20, 16, 10, 130))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(8))
    img.paste(shadow_layer, (0, 0), shadow_layer)

    w, h = sprite.size
    scale = min(box / w, box / h)
    sprite = sprite.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    sw, sh = sprite.size
    img.paste(sprite, (cx - sw // 2, cy - sh // 2), sprite)


def _draw_pet_placeholder(draw: ImageDraw.ImageDraw, cx: int, cy: int, pet: PetState) -> None:
    """Simple blob with face — used only if a tami asset file is missing."""
    mood_colors = {
        "happy":     HEALTH_GOOD,
        "worried":   HEALTH_WARN,
        "sick":      (232, 158, 94),
        "dying":     (143, 143, 154),
        "graduated": (245, 197, 24),
    }
    color = mood_colors.get(pet.mood, HEALTH_GOOD)
    body_w, body_h = 260, 220
    draw.ellipse([cx - body_w // 2, cy - body_h // 2,
                  cx + body_w // 2, cy + body_h // 2], fill=color)
    eye_l = (cx - 42, cy - 30); eye_r = (cx + 42, cy - 30)
    for (ex, ey) in (eye_l, eye_r):
        draw.ellipse([ex - 10, ey - 10, ex + 10, ey + 10], fill=(26, 26, 34))
    draw.arc([cx - 50, cy + 10, cx + 50, cy + 70], start=0, end=180,
             fill=(26, 26, 34), width=6)


# ─── Telegram-caption-only text (never drawn ON the image — see bot.py) ────
def pet_caption(g: GroupState) -> str:
    p, m = g.pet.physical, g.pet.mental
    mood = g.pet.mood
    if mood == "graduated":
        return "pet has graduated. touch grass, book the flight."
    if mood == "dying":
        return "it's over. the group chat has flatlined."
    if p < 30 and m < 30:
        return "prices are killing me AND chat's slowing down"
    if p < 30:
        return "prices are killing me — someone find a cheaper hotel"
    if m < 30:
        return "chat's slowing down… where did everyone go"
    if p < 55 and m < 55:
        return "kinda vibing, kinda dying, hard to say"
    if p > 80 and m > 80:
        return "pet is thriving. trip is on."
    if m > 75:
        return "the group is locked in"
    if p > 75:
        return "wallet is happy today"
    return "just hanging out. keep talking, keep booking."


def render_pet_png(g: GroupState) -> bytes:
    """Square card: 'Tabi' label, the sprite, then the two health bars
    stacked below it — all inside one box. No caption, no trip stats, no
    week chip; the only text anywhere is the word 'Tabi'. (Tabi's chat line
    still rides as the Telegram message's own caption — see bot.py — this
    function only controls what's drawn INTO the image.)"""
    img = _tiled_background(CANVAS).convert("RGB")

    card_box = (PAD, PAD, CANVAS[0] - PAD, CANVAS[1] - PAD)
    _card(img, card_box, RADIUS)
    inner_x0, inner_y0, inner_x1, inner_y1 = (
        card_box[0] + INNER_PAD, card_box[1] + INNER_PAD,
        card_box[2] - INNER_PAD, card_box[3] - INNER_PAD,
    )

    draw = ImageDraw.Draw(img)
    title_font = _display(34)
    draw.text((inner_x0, inner_y0), "Tabi", fill=FG, font=title_font, anchor="la")
    title_bottom = inner_y0 + title_font.getbbox("Tabi")[3] + 20

    bar_h = 28
    bars_gap = 14
    bars_h = bar_h * 2 + bars_gap
    bars_y0 = inner_y1 - bars_h

    sprite_top = title_bottom
    sprite_bottom = bars_y0 - 24
    sprite_box = max(80, min(inner_x1 - inner_x0, sprite_bottom - sprite_top))
    sprite_cx = (inner_x0 + inner_x1) // 2
    sprite_cy = sprite_top + (sprite_bottom - sprite_top) // 2
    _draw_sprite(img, cx=sprite_cx, cy=sprite_cy, pet=g.pet, box=sprite_box)

    bars_y = _bar_minimal(img, inner_x0, bars_y0, inner_x1 - inner_x0,
                          icon_glyph=_heart_glyph, val=g.pet.physical, h=bar_h) + bars_gap
    _bar_minimal(img, inner_x0, bars_y, inner_x1 - inner_x0,
                icon_glyph=_chat_glyph, val=g.pet.mental, h=bar_h)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
