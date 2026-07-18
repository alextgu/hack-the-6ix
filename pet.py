"""Placeholder pet renderer — Pillow PNG.

Simple blob creature whose face changes with mood, plus two labelled bars
(physical / mental) and a status caption. Designer replaces the art later.
The image is composed fresh on every state change and returned as bytes so
`bot.py` can call `send_photo(chat_id, InputFile(bytes))` — the safe visual
path (not a link preview) per PROJECT.md.

TODO seams:
  - Swap the shape drawing for the designer's real sprites (5 mood tiers).
  - When the pet talks (ElevenLabs later), add a speech-bubble overlay.
"""
from __future__ import annotations
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from state import GroupState, PetState


CANVAS = (600, 640)
BG = (18, 20, 26)
INK = (238, 241, 246)
DIM = (138, 146, 165)
BAR_BG = (38, 42, 53)

MOOD_COLORS = {
    "happy":      (124, 217, 146),
    "worried":    (240, 212, 122),
    "sick":       (232, 158, 94),
    "dying":      (143, 143, 154),
    "graduated":  (245, 197, 24),
}


def _load_font(size: int) -> ImageFont.ImageFont:
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


def _draw_bar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, pct: int,
              fill: tuple[int, int, int], label: str) -> None:
    r = h // 2
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=BAR_BG)
    fill_w = int(w * max(0, min(100, pct)) / 100)
    if fill_w >= h:
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=r, fill=fill)
    font_label = _load_font(20)
    font_val = _load_font(20)
    draw.text((x, y - 26), label, fill=DIM, font=font_label)
    draw.text((x + w - 44, y - 26), f"{pct}%", fill=INK, font=font_val, anchor="la")


def _draw_pet(draw: ImageDraw.ImageDraw, cx: int, cy: int, pet: PetState) -> None:
    """Simple blob with face — placeholder for real sprites."""
    color = MOOD_COLORS.get(pet.mood, MOOD_COLORS["happy"])
    # body (ellipse)
    body_w, body_h = 260, 220
    draw.ellipse([cx - body_w // 2, cy - body_h // 2,
                  cx + body_w // 2, cy + body_h // 2], fill=color)
    # ground shadow
    draw.ellipse([cx - 100, cy + body_h // 2 - 6, cx + 100, cy + body_h // 2 + 10],
                 fill=(0, 0, 0, 40))
    # cheeks
    cheek_col = tuple(max(0, c - 30) for c in color)
    draw.ellipse([cx - 100, cy + 20, cx - 70, cy + 50], fill=cheek_col)
    draw.ellipse([cx + 70, cy + 20, cx + 100, cy + 50], fill=cheek_col)

    # eyes + mouth by mood tier
    eye_l = (cx - 42, cy - 30); eye_r = (cx + 42, cy - 30)
    if pet.mood == "dying":
        # X eyes
        for (ex, ey) in (eye_l, eye_r):
            draw.line([ex - 12, ey - 12, ex + 12, ey + 12], fill=(26, 26, 34), width=5)
            draw.line([ex + 12, ey - 12, ex - 12, ey + 12], fill=(26, 26, 34), width=5)
        # wavy mouth
        for i, dx in enumerate([-30, -10, 10, 30]):
            offset = 8 if i % 2 == 0 else -8
            draw.line([cx + dx - 10, cy + 40 + offset, cx + dx + 10, cy + 40 - offset],
                      fill=(26, 26, 34), width=4)
    elif pet.mood == "sick":
        for (ex, ey) in (eye_l, eye_r):
            draw.ellipse([ex - 8, ey - 4, ex + 8, ey + 4], fill=(26, 26, 34))
        draw.arc([cx - 40, cy + 30, cx + 40, cy + 80], start=180, end=360,
                 fill=(26, 26, 34), width=5)
        # sweat drop
        draw.ellipse([cx + 100, cy - 20, cx + 120, cy + 8], fill=(124, 195, 255))
    elif pet.mood == "worried":
        for (ex, ey) in (eye_l, eye_r):
            draw.ellipse([ex - 8, ey - 8, ex + 8, ey + 8], fill=(26, 26, 34))
        draw.line([cx - 30, cy + 44, cx + 30, cy + 44], fill=(26, 26, 34), width=5)
    elif pet.mood == "graduated":
        # sunglasses
        draw.rectangle([eye_l[0] - 20, eye_l[1] - 8, eye_r[0] + 20, eye_r[1] + 8],
                       fill=(26, 26, 34))
        # big smile
        draw.arc([cx - 60, cy + 5, cx + 60, cy + 75], start=0, end=180,
                 fill=(26, 26, 34), width=6)
        # sparkles
        for (sx, sy) in [(cx - 140, cy - 100), (cx + 140, cy - 90),
                         (cx - 130, cy + 60), (cx + 130, cy + 70)]:
            draw.text((sx, sy), "*", fill=(245, 197, 24), font=_load_font(36))
    else:  # happy
        for (ex, ey) in (eye_l, eye_r):
            draw.ellipse([ex - 10, ey - 10, ex + 10, ey + 10], fill=(26, 26, 34))
            draw.ellipse([ex - 3, ey - 8, ex + 3, ey - 2], fill=(255, 255, 255))
        draw.arc([cx - 50, cy + 10, cx + 50, cy + 70], start=0, end=180,
                 fill=(26, 26, 34), width=6)


def _caption(g: GroupState) -> str:
    p, m = g.pet.physical, g.pet.mental
    if g.pet.mood == "graduated":
        return "TRIP BOOKED. i'm free."
    lines = []
    if p < 30: lines.append("prices are killing me")
    elif p < 55: lines.append("hotels getting expensive")
    if m < 30: lines.append("nobody's talking")
    elif m < 55: lines.append("chat's slowing down")
    if not lines:
        if p > 80 and m > 80: return "pet is thriving. keep going."
        return "pet is stable."
    return " — ".join(lines)


def render_pet_png(g: GroupState) -> bytes:
    img = Image.new("RGB", CANVAS, BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # title
    font_title = _load_font(22)
    draw.text((28, 20), f"trippet — week {g.sim_week} — {g.pet.mood}",
              fill=DIM, font=font_title)

    _draw_pet(draw, cx=CANVAS[0] // 2, cy=280, pet=g.pet)

    # bars
    bar_x, bar_w, bar_h = 40, CANVAS[0] - 80, 22
    _draw_bar(draw, bar_x, 470, bar_w, bar_h, g.pet.physical,
              (124, 217, 146), "Physical (booking pressure)")
    _draw_bar(draw, bar_x, 540, bar_w, bar_h, g.pet.mental,
              (178, 140, 255), "Mental (group vibe)")

    # caption
    draw.text((28, 590), _caption(g), fill=INK, font=_load_font(20))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
