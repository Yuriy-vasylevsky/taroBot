# dialog_tarot_chat.py
# Преміум файл для Живого Таро-чату:
# - GPT безкоштовно (по енергії) обирає розклад 3/4/5/10 + позиції (JSON)
# - Бот одразу тягне карти + відправляє 1 зображення
# - 1 виклик GPT тільки на тлумачення (без "чекаю карти" / "дякую за карти" / "чи підходить")
# - Енергія списується ТІЛЬКИ якщо тлумачення отримано
# - Celtic Cross: карта 2 поверх, центральні менші + більші відступи

import os
import re
import json
import random
import asyncio
import tempfile
from typing import List, Dict, Tuple, Optional

from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile

from openai import AsyncOpenAI
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from cards_data import TAROT_CARDS
from modules.menu import menu, build_main_menu
from modules.user_stats_db import get_energy, change_energy


dialog_router = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

# ======================
#   НАЛАШТУВАННЯ
# ======================
ENERGY_COST_PER_MESSAGE = 2
BACKGROUND_PATH = "background.png"
BACKGROUND_PATH10 = "bg.png"
EXIT_TEXT = "⬅️ Завершити бесіду"

# ================= MESSAGE HISTORY PER USER ===================
user_histories: Dict[int, List[Dict[str, str]]] = {}


def get_history(user_id: int) -> List[Dict[str, str]]:
    if user_id not in user_histories:
        user_histories[user_id] = []
    return user_histories[user_id]


def add_message(user_id: int, role: str, content: str):
    hist = get_history(user_id)
    hist.append({"role": role, "content": content})
    if len(hist) > 30:
        user_histories[user_id] = hist[-30:]


# ================== GPT SYSTEM PROMPT (INTERPRETER) ==================
SYSTEM_PROMPT = """
Ти — професійний таролог-наставник. Пишеш дуже чітко, структурно, без води, але тепло і підтримуюче.

ГОЛОВНЕ:
- Ти НЕ вигадуєш карти. Тлумачиш ТІЛЬКИ ті, що в блоці “Витягнуті карти”.
- Ти НЕ дякуєш за карти/запит і НЕ пишеш, що “чекаєш карти” або що користувач має “поділитися картами”.
- Ти НЕ питаєш згоду (“хочеш?”, “чи підходить?”). Усе подається як уже виконаний розклад.

ФОРМАТ ВІДПОВІДІ (завжди, PLAIN TEXT, без markdown і без HTML):
🎯 Фокус запиту: 1 коротке речення, що уточнює суть запиту користувача (БЕЗ питань).
🔮 Розклад: <назва>
🧩 По позиціях:
1) <назва позиції> — <карта> (⬆️/⬇️): 2–4 речення по суті
2) ...
✨ Зв’язки між картами: 3–6 речень (підтримка/конфлікт/логіка/повторювані теми)
🧭 Висновок: 2–4 речення (пряма відповідь на запит)
✅ Практична порада
- 3 конкретні кроки (маркерним списком)

СМАЙЛИ:
- Використовуй смайли як акценти: 1–2 на абзац (не більше).
- Підбирай по змісту: 🔮 🧩 ✨ 🧭 ⚠️ ❤️ 💼 💰

ПСИХОЛОГІЧНА БЕЗПЕКА:
- Якщо карта “важка”, не лякай: подавай як сигнал/тему для уваги ⚠️
- Для стосунків — межі, діалог, емоції ❤️
- Для роботи/грошей — рішення, план, ризики 💼💰
- Для здоров’я — без діагнозів: ресурс, стрес, режим ⚠️

ДОДАТКОВО:
- Ти отримуєш “Схема розкладу” і “Позиції” — тлумач строго за цією схемою.
"""


# ================== GPT PROMPT (SPREAD SELECTOR) ==================
SPREAD_SELECTOR_PROMPT = """
Ти — асистент, який ВИБИРАЄ ТІЛЬКИ розклад Таро під запит користувача.
Ти НЕ тлумачиш карти. Ти НЕ ставиш питань. Ти НЕ просиш уточнень.
Ти ПОВИНЕН повернути ТІЛЬКИ валідний JSON (без markdown, без пояснень поза JSON).

ДОСТУПНІ РОЗКЛАДИ (вибирай один):
1) "Три карти (3)" — для загальних/простих питань, коротких ситуацій.
   Схеми:
   - "Минуле—Теперішнє—Майбутнє" (прогноз, коли/що буде далі)
   - "Допомагає—Заважає—Порада" (що робити/як діяти/який крок)
   - "Суть—Виклик—Порада" (універсально)

2) "Стосунки (4)" — якщо запит про любов/відносини/взаємини/партнера/екс/почуття/поведінку.
   Позиції:
   1 — як виглядає зв’язок загалом
   2 — почуття/намір між вами
   3 — що напружує / що заважає
   4 — куди це рухається (вектор)

3) "Поглиблений розклад ситуації (5)" — рішення/робота/гроші/переїзд/план/вибір,
   або коли в запиті багато деталей чи потрібна практична стратегія.
   Позиції:
   1 — поточна ситуація
   2 — ресурс / що допомагає
   3 — виклик / що заважає
   4 — приховане / те, чого не видно
   5 — ймовірний напрямок / результат

4) "Кельтський хрест (10)" — комплексно/криза/затяжно/по колу/дуже важливе рішення/максимально глибоко.
   Позиції:
   1 — поточна ситуація
   2 — головний виклик / що перехрещує
   3 — корінь / глибинна причина
   4 — минуле, що вплинуло
   5 — тенденція / що над ситуацією
   6 — найближче майбутнє
   7 — ти / твоє ставлення
   8 — зовнішні обставини / впливи
   9 — надії та побоювання
   10 — підсумок / результат

ПРАВИЛА:
- Якщо явно про стосунки/відносини/взаємини — обирай "Стосунки (4)" (майже завжди).
- Якщо про рішення/роботу/гроші/переїзд/вибір — обирай "Поглиблений (5)".
- Якщо “криза/тупик/по колу/дуже складно/все одразу/детально” — "Кельтський (10)".
- Якщо коротко і загально — "Три карти (3)".
- НІКОЛИ не вибирай 1 карту.

ФОРМАТ ВІДПОВІДІ — ТІЛЬКИ JSON:
{
  "amount": 3|4|5|10,
  "spread_name": "…",
  "positions": ["…", "..."],
  "scheme_hint": "коротко: чому саме цей розклад"
}
"""


# ================== FSM ==================
class TarotChatFSM(StatesGroup):
    chatting = State()


def dialog_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text=EXIT_TEXT)]])


# ================== HELPERS ==================
def _norm(text: str) -> str:
    return (text or "").lower().replace("’", "'").replace("‘", "'")


def choose_spread_amount_fallback(user_text: str) -> int:
    """Фолбек-евристика на випадок, якщо JSON від GPT зламається."""
    t = _norm(user_text)

    if "кельт" in t or re.search(r"\b10\b|десять", t):
        return 10
    if re.search(r"\b5\b|п'ять|пять", t):
        return 5
    if re.search(r"\b4\b|чотири|чотирьох", t):
        return 4
    if re.search(r"\b3\b|три", t):
        return 3

    rel_words = ["стосунк", "відносин", "відносини", "взаємин", "взаємини", "кохан", "любов", "партнер", "екс", "колишн"]
    if any(w in t for w in rel_words):
        return 4

    deep_words = ["криза", "тупик", "по колу", "детально", "глибок", "безвихід", "все одразу", "роками"]
    if any(w in t for w in deep_words):
        return 10

    work_money_choice = ["робот", "кар'єр", "гроші", "дохід", "борг", "вибір", "рішення", "що робити", "як бути", "переїзд", "план"]
    if any(w in t for w in work_money_choice):
        return 5

    return 3


def choose_spread_layout_fallback(amount: int, user_text: str) -> Tuple[str, List[str]]:
    t = _norm(user_text)

    if amount == 10:
        return (
            "Кельтський хрест (10)",
            [
                "Поточна ситуація",
                "Головний виклик / що перехрещує",
                "Корінь / глибинна причина",
                "Минуле, що вплинуло",
                "Тенденція / що над ситуацією",
                "Найближче майбутнє",
                "Ти / твоє ставлення",
                "Зовнішні впливи / обставини",
                "Надії та побоювання",
                "Підсумок / результат",
            ],
        )
    if amount == 4:
        return (
            "Стосунки (4)",
            [
                "Як виглядає зв’язок загалом",
                "Почуття/намір між вами",
                "Що напружує / що заважає",
                "Куди це рухається (вектор)",
            ],
        )
    if amount == 5:
        return (
            "Поглиблений розклад ситуації (5)",
            [
                "Поточна ситуація",
                "Ресурс / що допомагає",
                "Виклик / що заважає",
                "Приховане / те, чого не видно",
                "Ймовірний напрямок / результат",
            ],
        )

    # 3 карти
    future_words = ["коли", "чи буде", "буде", "в майбутньому", "прогноз", "через", "наступ", "завтра", "цього місяця", "202"]
    action_words = ["що робити", "як бути", "як діяти", "вибір", "виріш", "порада", "план", "крок", "чи варто"]

    if any(w in t for w in future_words):
        return ("Три карти (3): Минуле—Теперішнє—Майбутнє", ["Минуле", "Теперішнє", "Майбутнє"])
    if any(w in t for w in action_words):
        return ("Три карти (3): Допомагає—Заважає—Порада", ["Що допомагає", "Що заважає", "Порада / як діяти"])

    return ("Три карти (3): Суть—Виклик—Порада", ["Суть ситуації", "Ключовий виклик", "Порада / напрям"])


def _extract_json_object(raw: str) -> Optional[dict]:
    """Надійний парсер: спочатку json.loads, потім витяг першого {...}."""
    raw = (raw or "").strip()
    if not raw:
        return None

    # 1) спроба чистого JSON
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2) витяг блоку {...}
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


async def choose_spread_via_gpt(user_text: str) -> Tuple[int, str, List[str]]:
    """
    Безкоштовний (по енергії) вибір розкладу GPT.
    Повертає: amount, spread_name, positions.
    Якщо GPT зламає JSON — fallback на евристику.
    """
    try:
        # Спроба JSON-mode (якщо підтримується бібліотекою/моделлю)
        try:
            r = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SPREAD_SELECTOR_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=220,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except TypeError:
            r = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SPREAD_SELECTOR_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=220,
                temperature=0.2,
            )

        raw = (r.choices[0].message.content or "").strip()
        data = _extract_json_object(raw)
        if not data:
            raise ValueError("No JSON parsed")

        amount = int(data.get("amount"))
        spread_name = str(data.get("spread_name", "")).strip()
        positions = data.get("positions")

        if amount not in (3, 4, 5, 10):
            raise ValueError("Bad amount")
        if not isinstance(positions, list) or len(positions) != amount:
            raise ValueError("Bad positions")

        positions = [str(p).strip() for p in positions]
        if not spread_name:
            raise ValueError("Empty spread_name")

        return amount, spread_name, positions

    except Exception:
        # fallback
        amount = choose_spread_amount_fallback(user_text)
        spread_name, positions = choose_spread_layout_fallback(amount, user_text)
        return amount, spread_name, positions


def build_cards_payload_ready(
    spread_name: str, positions: List[str], user_text: str, cards: List[dict]
) -> str:
    amount = len(cards)
    pos_lines = "\n".join([f"{i}. {positions[i-1]}" for i in range(1, amount + 1)])

    cards_lines = "\n".join(
        f"{i}. {c['ua']} ({c['code']}) {('⬆️' if c['upright'] else '⬇️')} — {'пряма' if c['upright'] else 'перевернута'}"
        for i, c in enumerate(cards, start=1)
    )

    return (
        f"Схема розкладу: {spread_name}\n"
        f"Позиції:\n{pos_lines}\n\n"
        f"Витягнуті карти:\n{cards_lines}\n\n"
        f"Запит користувача (контекст): {user_text}"
    )


def strip_bad_phrases(text: str) -> str:
    """
    Страховка: вирізаємо типові “заборонені” рядки, якщо інколи прослизнуть.
    """
    if not text:
        return ""

    bad_patterns = [
        r"дякую",
        r"чекаю",
        r"коли будеш готов",
        r"поділи(сь|ться).*карт",
        r"скажи коли",
        r"коли витягнеш",
    ]

    lines = text.splitlines()
    cleaned: List[str] = []
    for ln in lines:
        low = ln.strip().lower()
        if any(re.search(p, low) for p in bad_patterns):
            continue
        cleaned.append(ln)

    return "\n".join(cleaned).strip()


# ================== CARD DRAWING ==================
def draw_cards(amount: int):
    names = list(TAROT_CARDS.keys())
    amount = max(1, min(amount, len(names), 10))
    chosen = random.sample(names, amount)

    result = []
    for name in chosen:
        upright = random.choice([True, False])
        ua = TAROT_CARDS[name]["ua_name"]
        img_path = TAROT_CARDS[name]["image"]
        result.append({"code": name, "ua": ua, "upright": upright, "image": img_path})
    return result


# ======================
#   IMAGE HELPERS
# ======================
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
    tmp.close()  # важливо для Windows
    img.save(tmp.name, "PNG", optimize=True)
    return tmp.name


# ======================
#   COMBINE: 3 / 4 / 5
# ======================
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


# ======================
#   COMBINE: CELTIC CROSS (10) - PREMIUM FIX
# ======================
def combine_celtic_cross_with_background(
    paths: List[str],
    uprights: List[bool],
    background_path: str = BACKGROUND_PATH10,
) -> str:
    bg = _safe_background(background_path)
    W, H = bg.size

    margin = max(18, int(W * 0.035))
    spacing = max(10, int(W * 0.014))

    column_left = int(W * 0.72)
    cross_left = margin
    cross_right = column_left - spacing
    cross_width = cross_right - cross_left
    col_width = (W - margin) - column_left

    prepared: List[Image.Image] = [_prepare_card(p, u) for p, u in zip(paths, uprights)]

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

    # Менші центральні + більші відступи
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

    # 3–6 спочатку
    bg.alpha_composite(cards_center[2], (x_center, y_bottom))
    _draw_label(bg, "3", x_center + 14, y_bottom + 14, font_size=26)

    bg.alpha_composite(cards_center[3], (x_left, y_center))
    _draw_label(bg, "4", x_left + 14, y_center + 14, font_size=26)

    bg.alpha_composite(cards_center[4], (x_center, y_top))
    _draw_label(bg, "5", x_center + 14, y_top + 14, font_size=26)

    bg.alpha_composite(cards_center[5], (x_right, y_center))
    _draw_label(bg, "6", x_right + 14, y_center + 14, font_size=26)

    # 1 центр
    bg.alpha_composite(cards_center[0], (x_center, y_center))
    _draw_label(bg, "1", x_center + 14, y_center + 14, font_size=26)

    # 2 перехрестя — ОСТАННЄ (завжди поверх)
    cross_card = cards_center[1].rotate(90, expand=True)
    w2, h2 = cross_card.size
    cross_x = center_x - w2 // 2
    cross_y = center_y - h2 // 2
    bg.alpha_composite(cross_card, (cross_x, cross_y))
    _draw_label(bg, "2", cross_x + 14, cross_y + 14, font_size=26)

    # Права колонка 7–10 (10 зверху)
    col_total_h = 4 * ch_col + 3 * spacing
    col_start_y = (H - col_total_h) // 2
    col_x = column_left + max(0, (col_width - cw_col) // 2)

    y_positions = [
        col_start_y + 0 * (ch_col + spacing),
        col_start_y + 1 * (ch_col + spacing),
        col_start_y + 2 * (ch_col + spacing),
        col_start_y + 3 * (ch_col + spacing),
    ]
    order = [3, 2, 1, 0]  # [7,8,9,10] -> [10,9,8,7]
    labels = ["10", "9", "8", "7"]

    for y, idx, lab in zip(y_positions, order, labels):
        bg.alpha_composite(cards_col[idx], (col_x, y))
        _draw_label(bg, lab, col_x + 14, y + 14, font_size=26)

    return _save_temp_png(bg)


def combine_spread_image(paths: List[str], uprights: List[bool], amount: int) -> str:
    if amount == 3:
        return combine_3_cards(paths, uprights, BACKGROUND_PATH)
    if amount == 4:
        return combine_4_cards(paths, uprights, BACKGROUND_PATH)
    if amount == 5:
        return combine_5_cards(paths, uprights, BACKGROUND_PATH)
    if amount == 10:
        return combine_celtic_cross_with_background(paths, uprights, BACKGROUND_PATH10)
    return combine_3_cards(paths[:3], uprights[:3], BACKGROUND_PATH)


# ================== START DIALOG ===================
@dialog_router.message(F.text == "🔮 Живий Таро-чат")
async def start_dialog(message: types.Message, state: FSMContext):
    await state.set_state(TarotChatFSM.chatting)
    user_histories[message.from_user.id] = []
    add_message(message.from_user.id, "system", SYSTEM_PROMPT)

    welcome = (
        "✨ Привіт! Я тут, щоб підтримати тебе й допомогти розібратися в тому, що хвилює.\n"
        "🔮 Напиши свою ситуацію або питання — і я одразу зроблю розклад та дам чітку пораду.\n"
        "Можна про стосунки ❤️, роботу 💼, гроші 💰, вибір 🧭 або будь-що інше.\n\n"
        f"⚡ Вартість повідомлення: <b>{ENERGY_COST_PER_MESSAGE}</b> енергії."
    )
    await message.answer(welcome, reply_markup=dialog_kb(), parse_mode="HTML")


# ================== EXIT ===================
@dialog_router.message(F.text == EXIT_TEXT)
async def exit_dialog(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    try:
        await message.delete()
    except Exception:
        pass

    kb = build_main_menu(user_id)
    await message.bot.send_message(
        chat_id=message.chat.id,
        text="🔙 Повертаю в головне меню.",
        reply_markup=kb,
    )
    await state.clear()


# ================== MAIN CHAT ===================
@dialog_router.message(TarotChatFSM.chatting)
async def chat(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = (message.text or "").strip()
    if not text:
        return

    # 0) Перевірка енергії (вибір розкладу безкоштовний, але тлумачення — платне)
    current = await get_energy(user_id)
    if current < ENERGY_COST_PER_MESSAGE:
        await message.answer(
            "🔋 <b>Недостатньо енергії</b> для продовження чату.\n\n"
            f"Потрібно: <b>{ENERGY_COST_PER_MESSAGE}</b> ✨\n"
            f"У вас: <b>{current}</b> ✨\n\n"
            "Поповніть енергію через меню: «⚡ Поповнити енергію».",
            parse_mode="HTML",
            reply_markup=menu,
        )
        return

    # 1) Контекст в історію
    add_message(user_id, "user", text)

    # 2) GPT безкоштовно вибирає розклад (3/4/5/10) + позиції
    amount, spread_name, positions = await choose_spread_via_gpt(text)

    # 3) Тягнемо карти
    cards = draw_cards(amount)

    # НЕ міняю як ти просив ✅
    await message.answer(f"🃏 Роблю розклад на {spread_name}")
    await asyncio.sleep(0.2)

    # 4) Зображення розкладу
    img_paths = [c["image"] for c in cards]
    uprights = [c["upright"] for c in cards]
    final_img = combine_spread_image(img_paths, uprights, amount)

    lines = []
    for i, c in enumerate(cards, start=1):
        arrow = "⬆️" if c["upright"] else "⬇️"
        lines.append(f"{i}. {c['ua']} {arrow}")

    caption = "🃏 <b>Витягнуті карти:</b>\n" + "\n".join(lines)

    await message.answer_photo(
        photo=FSInputFile(final_img),
        caption=caption,
        parse_mode="HTML",
    )

    try:
        os.remove(final_img)
    except Exception:
        pass

    # 5) Payload з позиціями + картами в історію
    cards_payload = build_cards_payload_ready(spread_name, positions, text, cards)
    add_message(user_id, "user", cards_payload)

    # 6) Один виклик GPT — ТІЛЬКИ тлумачення
    try:
        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=get_history(user_id),
            max_tokens=2000,
            temperature=0.7,
        )
        final_reply = (resp.choices[0].message.content or "").strip()
        final_reply = strip_bad_phrases(final_reply)
    except Exception:
        await message.answer("⚠️ Не вдалося отримати тлумачення. Спробуй ще раз.")
        return

    # 7) Списуємо енергію тільки якщо тлумачення успішне
    await change_energy(user_id, -ENERGY_COST_PER_MESSAGE)

    # 8) Відправляємо відповідь (PLAIN TEXT)
    add_message(user_id, "assistant", final_reply)
    await message.answer(final_reply)
