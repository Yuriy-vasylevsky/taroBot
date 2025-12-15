# # modules/tarot_spread_image.py
# # Відповідає за:
# # - підготовку карт (обрізка, поворот, скруглення, тінь)
# # - збирання розкладів 3/4/5/10 в одну картинку
# # - Celtic Cross: карта 2 поверх, центральні менші + більші відступи

# import os
# import tempfile
# from typing import List

# from PIL import Image, ImageDraw, ImageFilter, ImageFont


# # ======================
# #   IMAGE HELPERS
# # ======================
# def _safe_background(path: str) -> Image.Image:
#     if path and os.path.exists(path):
#         return Image.open(path).convert("RGBA")
#     return Image.new("RGBA", (1400, 900), (20, 20, 20, 255))


# def _load_font(size: int) -> ImageFont.ImageFont:
#     # Linux
#     candidates = [
#         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
#         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
#         # Windows (часто)
#         "C:/Windows/Fonts/arialbd.ttf",
#         "C:/Windows/Fonts/arial.ttf",
#         # fallback local
#         "DejaVuSans-Bold.ttf",
#         "DejaVuSans.ttf",
#         "Arial.ttf",
#     ]
#     for p in candidates:
#         try:
#             return ImageFont.truetype(p, size)
#         except Exception:
#             continue
#     return ImageFont.load_default()


# def _draw_label(base: Image.Image, text: str, x: int, y: int, font_size: int = 26):
#     overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
#     draw = ImageDraw.Draw(overlay)
#     font = _load_font(font_size)

#     bbox = draw.textbbox((0, 0), text, font=font)
#     tw = bbox[2] - bbox[0]
#     th = bbox[3] - bbox[1]

#     pad_x, pad_y = 10, 6
#     rw = tw + pad_x * 2
#     rh = th + pad_y * 2

#     draw.rounded_rectangle((x, y, x + rw, y + rh), radius=10, fill=(0, 0, 0, 160))
#     draw.text((x + pad_x, y + pad_y), text, font=font, fill=(255, 255, 255, 255))
#     base.alpha_composite(overlay)


# def _crop_1mm(img: Image.Image) -> Image.Image:
#     dpi = img.info.get("dpi", (300, 300))[0]
#     mm_to_px = dpi / 25.4
#     px = int(1 * mm_to_px)
#     w, h = img.size
#     if px <= 0 or px * 2 >= min(w, h):
#         return img
#     return img.crop((px, px, w - px, h - px))


# def _round_corners(img: Image.Image, radius: int = 45) -> Image.Image:
#     mask = Image.new("L", img.size, 0)
#     draw = ImageDraw.Draw(mask)
#     draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius, fill=255)
#     out = Image.new("RGBA", img.size)
#     out.paste(img, (0, 0), mask)
#     return out


# def _add_3d_shadow(
#     img: Image.Image,
#     offset=(12, 18),
#     blur: int = 38,
#     shadow_opacity: int = 140,
#     corner_radius: int = 45,
# ) -> Image.Image:
#     w, h = img.size

#     shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
#     mask = Image.new("L", (w, h), 0)
#     draw = ImageDraw.Draw(mask)
#     draw.rounded_rectangle((0, 0, w, h), corner_radius, fill=shadow_opacity)

#     shadow.paste((0, 0, 0, shadow_opacity), (0, 0), mask)
#     shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

#     layer = Image.new("RGBA", (w + offset[0], h + offset[1]), (0, 0, 0, 0))
#     layer.alpha_composite(shadow, offset)
#     layer.alpha_composite(img, (0, 0))
#     return layer


# def _prepare_card(path: str, upright: bool) -> Image.Image:
#     img = Image.open(path).convert("RGBA")
#     img = _crop_1mm(img)
#     if not upright:
#         img = img.rotate(180, expand=True)
#     img = _round_corners(img)
#     img = _add_3d_shadow(img)
#     return img


# def _save_temp_png(img: Image.Image) -> str:
#     tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
#     tmp.close()  # важливо для Windows
#     img.save(tmp.name, "PNG", optimize=True)
#     return tmp.name


# # ======================
# #   COMBINE: 3 / 4 / 5
# # ======================
# def _combine_3_cards(paths: List[str], uprights: List[bool], background_path: str) -> str:
#     bg = _safe_background(background_path)
#     W, H = bg.size
#     cards = [_prepare_card(p, u) for p, u in zip(paths, uprights)]

#     base_w, base_h = cards[0].size
#     ratio = base_h / base_w
#     h_factor = 1.05

#     margin = max(30, int(W * 0.05))
#     spacing = int(W * 0.03)

#     cw_by_w = (W - 2 * margin - 2 * spacing) / 3
#     cw_by_h = (H - 2 * margin) / (ratio * h_factor)
#     cw = int(max(90, min(cw_by_w, cw_by_h, W * 0.30)))
#     ch = int(cw * ratio * h_factor)

#     cards = [c.resize((cw, ch), Image.LANCZOS) for c in cards]

#     total_width = cw * 3 + spacing * 2
#     start_x = (W - total_width) // 2
#     y = (H - ch) // 2
#     xs = [start_x, start_x + cw + spacing, start_x + (cw + spacing) * 2]

#     for i, (img, x) in enumerate(zip(cards, xs), start=1):
#         bg.alpha_composite(img, (x, y))
#         _draw_label(bg, str(i), x + 14, y + 14, font_size=26)

#     return _save_temp_png(bg)


# def _combine_4_cards(paths: List[str], uprights: List[bool], background_path: str) -> str:
#     bg = _safe_background(background_path)
#     W, H = bg.size
#     cards = [_prepare_card(p, u) for p, u in zip(paths, uprights)]

#     base_w, base_h = cards[0].size
#     ratio = base_h / base_w
#     h_factor = 1.05

#     margin = max(30, int(W * 0.05))
#     spacing = int(W * 0.03)

#     cw_by_w = (W - 2 * margin - spacing) / 2
#     cw_by_h = (H - 2 * margin - spacing) / (2 * ratio * h_factor)
#     cw = int(max(90, min(cw_by_w, cw_by_h, W * 0.28)))
#     ch = int(cw * ratio * h_factor)

#     cards = [c.resize((cw, ch), Image.LANCZOS) for c in cards]

#     total_w = 2 * cw + spacing
#     total_h = 2 * ch + spacing
#     start_x = (W - total_w) // 2
#     start_y = (H - total_h) // 2

#     positions = [
#         (start_x, start_y),
#         (start_x + cw + spacing, start_y),
#         (start_x, start_y + ch + spacing),
#         (start_x + cw + spacing, start_y + ch + spacing),
#     ]

#     for i, (img, (x, y)) in enumerate(zip(cards, positions), start=1):
#         bg.alpha_composite(img, (x, y))
#         _draw_label(bg, str(i), x + 14, y + 14, font_size=26)

#     return _save_temp_png(bg)


# def _combine_5_cards(paths: List[str], uprights: List[bool], background_path: str) -> str:
#     bg = _safe_background(background_path)
#     W, H = bg.size
#     cards = [_prepare_card(p, u) for p, u in zip(paths, uprights)]

#     base_w, base_h = cards[0].size
#     ratio = base_h / base_w
#     h_factor = 1.05

#     margin = max(30, int(W * 0.05))
#     spacing = int(W * 0.025)

#     cw_by_w = (W - 2 * margin - 2 * spacing) / 3
#     cw_by_h = (H - 2 * margin - spacing) / (2 * ratio * h_factor)
#     cw = int(max(90, min(cw_by_w, cw_by_h, W * 0.24)))
#     ch = int(cw * ratio * h_factor)

#     cards = [c.resize((cw, ch), Image.LANCZOS) for c in cards]

#     top_total_w = cw * 3 + spacing * 2
#     top_x = (W - top_total_w) // 2
#     bottom_total_w = cw * 2 + spacing
#     bottom_x = (W - bottom_total_w) // 2

#     total_h = ch * 2 + spacing
#     start_y = (H - total_h) // 2

#     pos = [
#         (top_x + 0 * (cw + spacing), start_y),
#         (top_x + 1 * (cw + spacing), start_y),
#         (top_x + 2 * (cw + spacing), start_y),
#         (bottom_x + 0 * (cw + spacing), start_y + ch + spacing),
#         (bottom_x + 1 * (cw + spacing), start_y + ch + spacing),
#     ]

#     for i, (img, (x, y)) in enumerate(zip(cards, pos), start=1):
#         bg.alpha_composite(img, (x, y))
#         _draw_label(bg, str(i), x + 14, y + 14, font_size=26)

#     return _save_temp_png(bg)


# # ======================
# #   COMBINE: CELTIC CROSS (10)
# # ======================
# def _combine_celtic_cross(paths: List[str], uprights: List[bool], background_path: str) -> str:
#     bg = _safe_background(background_path)
#     W, H = bg.size

#     margin = max(18, int(W * 0.035))
#     spacing = max(10, int(W * 0.014))

#     column_left = int(W * 0.72)
#     cross_left = margin
#     cross_right = column_left - spacing
#     cross_width = cross_right - cross_left
#     col_width = (W - margin) - column_left

#     prepared = [_prepare_card(p, u) for p, u in zip(paths, uprights)]
#     base_w, base_h = prepared[0].size
#     ratio = base_h / base_w
#     h_factor = 1.05

#     cw_by_w = (cross_width - 2 * spacing) / 3
#     cw_by_h = (H - 2 * margin - 2 * spacing) / (3 * ratio * h_factor)
#     cw_main = int(max(110, min(cw_by_w, cw_by_h, W * 0.33)))
#     ch_main = int(cw_main * ratio * h_factor)

#     cw_col_by_w = max(95, col_width)
#     cw_col_by_h = (H - 2 * margin - 3 * spacing) / (4 * ratio * h_factor)
#     cw_col = int(max(95, min(cw_col_by_w, cw_col_by_h, cw_main * 0.92)))
#     ch_col = int(cw_col * ratio * h_factor)

#     cards_col = [img.resize((cw_col, ch_col), Image.LANCZOS) for img in prepared[6:]]

#     center_x = (cross_left + cross_right) // 2
#     center_y = H // 2

#     CENTER_SCALE = 0.92
#     CENTER_SPACING_EXTRA = int(spacing * 1.45)

#     cw_c = int(cw_main * CENTER_SCALE)
#     ch_c = int(ch_main * CENTER_SCALE)
#     cards_center = [img.resize((cw_c, ch_c), Image.LANCZOS) for img in prepared[:6]]

#     x_center = center_x - cw_c // 2
#     y_center = center_y - ch_c // 2

#     x_left = x_center - cw_c - CENTER_SPACING_EXTRA
#     x_right = x_center + cw_c + CENTER_SPACING_EXTRA
#     y_top = y_center - ch_c - CENTER_SPACING_EXTRA
#     y_bottom = y_center + ch_c + CENTER_SPACING_EXTRA

#     # 3–6
#     bg.alpha_composite(cards_center[2], (x_center, y_bottom)); _draw_label(bg, "3", x_center + 14, y_bottom + 14, 26)
#     bg.alpha_composite(cards_center[3], (x_left, y_center));  _draw_label(bg, "4", x_left + 14, y_center + 14, 26)
#     bg.alpha_composite(cards_center[4], (x_center, y_top));   _draw_label(bg, "5", x_center + 14, y_top + 14, 26)
#     bg.alpha_composite(cards_center[5], (x_right, y_center)); _draw_label(bg, "6", x_right + 14, y_center + 14, 26)

#     # 1 центр
#     bg.alpha_composite(cards_center[0], (x_center, y_center)); _draw_label(bg, "1", x_center + 14, y_center + 14, 26)

#     # 2 перехрестя — ОСТАННЄ (поверх)
#     cross_card = cards_center[1].rotate(90, expand=True)
#     w2, h2 = cross_card.size
#     cross_x = center_x - w2 // 2
#     cross_y = center_y - h2 // 2
#     bg.alpha_composite(cross_card, (cross_x, cross_y))
#     _draw_label(bg, "2", cross_x + 14, cross_y + 14, 26)

#     # Колонка 7–10 (10 зверху)
#     col_total_h = 4 * ch_col + 3 * spacing
#     col_start_y = (H - col_total_h) // 2
#     col_x = column_left + max(0, (col_width - cw_col) // 2)

#     y_positions = [col_start_y + i * (ch_col + spacing) for i in range(4)]
#     order = [3, 2, 1, 0]
#     labels = ["10", "9", "8", "7"]

#     for y, idx, lab in zip(y_positions, order, labels):
#         bg.alpha_composite(cards_col[idx], (col_x, y))
#         _draw_label(bg, lab, col_x + 14, y + 14, 26)

#     return _save_temp_png(bg)


# # ======================
# #   PUBLIC API
# # ======================
# def combine_spread_image(
#     paths: List[str],
#     uprights: List[bool],
#     amount: int,
#     background_path: str = "background.png",
#     background_path10: str = "bg.png",
# ) -> str:
#     """
#     Повертає шлях до тимчасового PNG (його можна потім os.remove()).
#     """
#     if amount == 3:
#         return _combine_3_cards(paths, uprights, background_path)
#     if amount == 4:
#         return _combine_4_cards(paths, uprights, background_path)
#     if amount == 5:
#         return _combine_5_cards(paths, uprights, background_path)
#     if amount == 10:
#         return _combine_celtic_cross(paths, uprights, background_path10)

#     # fallback
#     return _combine_3_cards(paths[:3], uprights[:3], background_path)







# modules/tarot_spread_image.py
import os
import tempfile
from typing import List
from PIL import Image, ImageDraw, ImageFont, ImageFilter

DEFAULT_BG_3_5 = "background.png"
DEFAULT_BG_10 = "bg.png"


def _safe_background(path: str) -> Image.Image:
    if path and os.path.exists(path):
        return Image.open(path).convert("RGBA")
    return Image.new("RGBA", (1400, 900), (20, 20, 20, 255))


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _draw_label(base: Image.Image, text: str, x: int, y: int, font_size: int = 26):
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_x, pad_y = 10, 6
    rw = tw + pad_x * 2
    rh = th + pad_y * 2

    draw.rounded_rectangle((x, y, x + rw, y + rh), radius=10, fill=(0, 0, 0, 160))
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=(255, 255, 255, 255))
    base.alpha_composite(overlay)


def _crop_1mm(img: Image.Image) -> Image.Image:
    dpi = img.info.get("dpi", (300, 300))[0]
    mm_to_px = dpi / 25.4
    px = int(1 * mm_to_px)
    w, h = img.size
    if px <= 0 or px * 2 >= min(w, h):
        return img
    return img.crop((px, px, w - px, h - px))


def _round_corners(img: Image.Image, radius: int = 45) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out


def _add_3d_shadow(
    img: Image.Image,
    offset=(12, 18),
    blur: int = 38,
    shadow_opacity: int = 140,
    corner_radius: int = 45,
) -> Image.Image:
    w, h = img.size
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, w, h), corner_radius, fill=shadow_opacity)
    shadow.paste((0, 0, 0, shadow_opacity), (0, 0), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

    layer = Image.new("RGBA", (w + offset[0], h + offset[1]), (0, 0, 0, 0))
    layer.alpha_composite(shadow, offset)
    layer.alpha_composite(img, (0, 0))
    return layer


def _prepare_card(path: str, upright: bool) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    img = _crop_1mm(img)
    if not upright:
        img = img.rotate(180, expand=True)
    img = _round_corners(img)
    img = _add_3d_shadow(img)
    return img


def _save_temp_png(img: Image.Image) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.close()
    img.save(tmp.name, "PNG", optimize=True)
    return tmp.name


def combine_3_cards(paths: List[str], uprights: List[bool], background_path: str) -> str:
    bg = _safe_background(background_path)
    W, H = bg.size
    cards = [_prepare_card(p, u) for p, u in zip(paths, uprights)]

    base_w, base_h = cards[0].size
    ratio = base_h / base_w
    h_factor = 1.05

    margin = max(30, int(W * 0.05))
    spacing = int(W * 0.03)

    cw_by_w = (W - 2 * margin - 2 * spacing) / 3
    cw_by_h = (H - 2 * margin) / (ratio * h_factor)
    cw = int(max(90, min(cw_by_w, cw_by_h, W * 0.30)))
    ch = int(cw * ratio * h_factor)

    cards = [c.resize((cw, ch), Image.LANCZOS) for c in cards]

    total_width = cw * 3 + spacing * 2
    start_x = (W - total_width) // 2
    y = (H - ch) // 2
    xs = [start_x, start_x + cw + spacing, start_x + (cw + spacing) * 2]

    for i, (img, x) in enumerate(zip(cards, xs), start=1):
        bg.alpha_composite(img, (x, y))
        _draw_label(bg, str(i), x + 14, y + 14, font_size=26)

    return _save_temp_png(bg)


def combine_4_cards(paths: List[str], uprights: List[bool], background_path: str) -> str:
    bg = _safe_background(background_path)
    W, H = bg.size
    cards = [_prepare_card(p, u) for p, u in zip(paths, uprights)]

    base_w, base_h = cards[0].size
    ratio = base_h / base_w
    h_factor = 1.05

    margin = max(30, int(W * 0.05))
    spacing = int(W * 0.03)

    cw_by_w = (W - 2 * margin - spacing) / 2
    cw_by_h = (H - 2 * margin - spacing) / (2 * ratio * h_factor)
    cw = int(max(90, min(cw_by_w, cw_by_h, W * 0.28)))
    ch = int(cw * ratio * h_factor)

    cards = [c.resize((cw, ch), Image.LANCZOS) for c in cards]

    total_w = 2 * cw + spacing
    total_h = 2 * ch + spacing
    start_x = (W - total_w) // 2
    start_y = (H - total_h) // 2

    positions = [
        (start_x, start_y),
        (start_x + cw + spacing, start_y),
        (start_x, start_y + ch + spacing),
        (start_x + cw + spacing, start_y + ch + spacing),
    ]

    for i, (img, (x, y)) in enumerate(zip(cards, positions), start=1):
        bg.alpha_composite(img, (x, y))
        _draw_label(bg, str(i), x + 14, y + 14, font_size=26)

    return _save_temp_png(bg)


def combine_5_cards(paths: List[str], uprights: List[bool], background_path: str) -> str:
    bg = _safe_background(background_path)
    W, H = bg.size
    cards = [_prepare_card(p, u) for p, u in zip(paths, uprights)]

    base_w, base_h = cards[0].size
    ratio = base_h / base_w
    h_factor = 1.05

    margin = max(30, int(W * 0.05))
    spacing = int(W * 0.025)

    cw_by_w = (W - 2 * margin - 2 * spacing) / 3
    cw_by_h = (H - 2 * margin - spacing) / (2 * ratio * h_factor)
    cw = int(max(90, min(cw_by_w, cw_by_h, W * 0.24)))
    ch = int(cw * ratio * h_factor)

    cards = [c.resize((cw, ch), Image.LANCZOS) for c in cards]

    top_total_w = cw * 3 + spacing * 2
    top_x = (W - top_total_w) // 2
    bottom_total_w = cw * 2 + spacing
    bottom_x = (W - bottom_total_w) // 2

    total_h = ch * 2 + spacing
    start_y = (H - total_h) // 2

    pos = [
        (top_x + 0 * (cw + spacing), start_y),
        (top_x + 1 * (cw + spacing), start_y),
        (top_x + 2 * (cw + spacing), start_y),
        (bottom_x + 0 * (cw + spacing), start_y + ch + spacing),
        (bottom_x + 1 * (cw + spacing), start_y + ch + spacing),
    ]

    for i, (img, (x, y)) in enumerate(zip(cards, pos), start=1):
        bg.alpha_composite(img, (x, y))
        _draw_label(bg, str(i), x + 14, y + 14, font_size=26)

    return _save_temp_png(bg)


def combine_celtic_cross(paths: List[str], uprights: List[bool], background_path: str) -> str:
    bg = _safe_background(background_path)
    W, H = bg.size

    margin = max(18, int(W * 0.035))
    spacing = max(10, int(W * 0.014))

    column_left = int(W * 0.72)
    cross_left = margin
    cross_right = column_left - spacing
    cross_width = cross_right - cross_left
    col_width = (W - margin) - column_left

    prepared = [_prepare_card(p, u) for p, u in zip(paths, uprights)]
    base_w, base_h = prepared[0].size
    ratio = base_h / base_w
    h_factor = 1.05

    cw_by_w = (cross_width - 2 * spacing) / 3
    cw_by_h = (H - 2 * margin - 2 * spacing) / (3 * ratio * h_factor)
    cw_main = int(max(110, min(cw_by_w, cw_by_h, W * 0.33)))
    ch_main = int(cw_main * ratio * h_factor)

    cw_col_by_w = max(95, col_width)
    cw_col_by_h = (H - 2 * margin - 3 * spacing) / (4 * ratio * h_factor)
    cw_col = int(max(95, min(cw_col_by_w, cw_col_by_h, cw_main * 0.92)))
    ch_col = int(cw_col * ratio * h_factor)

    cards_col = [img.resize((cw_col, ch_col), Image.LANCZOS) for img in prepared[6:]]

    center_x = (cross_left + cross_right) // 2
    center_y = H // 2

    CENTER_SCALE = 0.92
    CENTER_SPACING_EXTRA = int(spacing * 1.45)

    cw_c = int(cw_main * CENTER_SCALE)
    ch_c = int(ch_main * CENTER_SCALE)
    cards_center = [img.resize((cw_c, ch_c), Image.LANCZOS) for img in prepared[:6]]

    x_center = center_x - cw_c // 2
    y_center = center_y - ch_c // 2

    x_left = x_center - cw_c - CENTER_SPACING_EXTRA
    x_right = x_center + cw_c + CENTER_SPACING_EXTRA
    y_top = y_center - ch_c - CENTER_SPACING_EXTRA
    y_bottom = y_center + ch_c + CENTER_SPACING_EXTRA

    bg.alpha_composite(cards_center[2], (x_center, y_bottom)); _draw_label(bg, "3", x_center + 14, y_bottom + 14, 26)
    bg.alpha_composite(cards_center[3], (x_left, y_center));  _draw_label(bg, "4", x_left + 14, y_center + 14, 26)
    bg.alpha_composite(cards_center[4], (x_center, y_top));   _draw_label(bg, "5", x_center + 14, y_top + 14, 26)
    bg.alpha_composite(cards_center[5], (x_right, y_center)); _draw_label(bg, "6", x_right + 14, y_center + 14, 26)

    bg.alpha_composite(cards_center[0], (x_center, y_center)); _draw_label(bg, "1", x_center + 14, y_center + 14, 26)

    cross_card = cards_center[1].rotate(90, expand=True)
    w2, h2 = cross_card.size
    cross_x = center_x - w2 // 2
    cross_y = center_y - h2 // 2
    bg.alpha_composite(cross_card, (cross_x, cross_y))
    _draw_label(bg, "2", cross_x + 14, cross_y + 14, 26)

    col_total_h = 4 * ch_col + 3 * spacing
    col_start_y = (H - col_total_h) // 2
    col_x = column_left + max(0, (col_width - cw_col) // 2)

    y_positions = [col_start_y + i * (ch_col + spacing) for i in range(4)]
    order = [3, 2, 1, 0]
    labels = ["10", "9", "8", "7"]

    for y, idx, lab in zip(y_positions, order, labels):
        bg.alpha_composite(cards_col[idx], (col_x, y))
        _draw_label(bg, lab, col_x + 14, y + 14, 26)

    return _save_temp_png(bg)


def combine_spread_image(
    paths: List[str],
    uprights: List[bool],
    amount: int,
    background_path: str = DEFAULT_BG_3_5,
    background_path10: str = DEFAULT_BG_10,
) -> str:
    if amount == 3:
        return combine_3_cards(paths, uprights, background_path)
    if amount == 4:
        return combine_4_cards(paths, uprights, background_path)
    if amount == 5:
        return combine_5_cards(paths, uprights, background_path)
    if amount == 10:
        return combine_celtic_cross(paths, uprights, background_path10)
    return combine_3_cards(paths[:3], uprights[:3], background_path)
