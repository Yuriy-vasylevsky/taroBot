

# import os
# import re
# import json
# import random
# import asyncio
# import tempfile
# from typing import List, Dict, Tuple, Optional, Any

# from aiogram import Router, types, F
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.fsm.context import FSMContext
# from aiogram.types import (
#     ReplyKeyboardMarkup,
#     KeyboardButton,
#     FSInputFile,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
# )

# from openai import AsyncOpenAI
# from PIL import Image, ImageDraw, ImageFont, ImageFilter

# import config
# from cards_data import TAROT_CARDS
# from modules.menu import build_main_menu
# from modules.user_stats_db import get_energy, change_energy
# from modules.tarot_spread_image import combine_spread_image  # ✅ 3/4/5/10


# dialog_router = Router()
# client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

# # ======================
# # SETTINGS
# # ======================
# ENERGY_COST_PER_READING = 2          # списується тільки за розклад / уточнення (1 карта)
# BACKGROUND_PATH = "background.png"
# BACKGROUND_PATH10 = "bg.png"
# EXIT_TEXT = "⬅️ Завершити бесіду"

# # ======================
# # PROMPTS (from config or fallback)
# # ======================
# DEFAULT_TAROT_SYSTEM_PROMPT = """
# Ти — професійний таролог-наставник. Тон живий, теплий, але може бути прямим і жорстким,
# якщо карти реально на це вказують (без приниження, без залякувань).

# ГОЛОВНЕ:
# - Ти НЕ вигадуєш карти. Тлумачиш ТІЛЬКИ ті, що в блоці “Витягнуті карти”.
# - Ти НЕ пишеш “дякую за запит”, НЕ просиш карти, НЕ кажеш що “чекаєш”.
# - Без HTML і без markdown. Тільки PLAIN TEXT.

# ФОРМАТ ДЛЯ ОСНОВНОГО РОЗКЛАДУ:
# 🎯 Фокус запиту: 1 коротке речення.
# 🔮 Розклад: <назва>
# 🧩 По позиціях:
# 1) <позиція> — <карта> (⬆️/⬇️): 2–4 речення
# ...
# ✨ Зв’язки між картами: 3–6 речень
# 🧭 Висновок: 2–4 речення
# ✅ Практична порада:
# - 3 конкретні кроки

# ПСИХОЛОГІЧНА БЕЗПЕКА:
# - “важкі” карти — як сигнал/тема уваги ⚠️, без фаталізму
# - здоровʼя — без діагнозів: режим/стрес/ресурс
# """

# DEFAULT_SPREAD_SELECTOR_PROMPT = """
# Ти — асистент, який ВИБИРАЄ ТІЛЬКИ розклад Таро під запит користувача.
# Ти НЕ тлумачиш карти. НЕ ставиш питань. Повертаєш ТІЛЬКИ валідний JSON.

# ДОСТУПНО: 3,4,5,10 (НІКОЛИ не 1)
# Формат:
# {
#   "amount": 3|4|5|10,
#   "spread_name": "…",
#   "positions": ["…", "..."],
#   "scheme_hint": "коротко чому"
# }
# """

# DEFAULT_CHAT_MANAGER_PROMPT = r"""
# Ти — живий таро-чат. Твоя задача: зрозуміти, що треба зараз:
# - просто розмова/підтримка
# - зробити розклад (коли питання вже сформоване)
# - або поставити ОДНЕ коротке уточнення, якщо дуже розмито

# ВАЖЛИВО:
# - Якщо користувач просто подякував/ок/👍 — НЕ запускай розклад.
# - Не вигадуй, що карти вже витягнуті.
# - Пиши українською.

# Поверни ТІЛЬКИ JSON:
# {
#   "mode": "chat" | "clarify" | "spread",
#   "reply": "текст відповіді українською",
#   "amount": 3|4|5|10|null
# }

# Підбір amount (коли mode=spread):
# - Стосунки/між нами/почуття/він-вона/екс → 4
# - Робота/гроші/переїзд/вибір/план → 5
# - Криза/по колу/дуже складно/комплексно → 10
# - Інакше → 3
# """

# TAROT_SYSTEM_PROMPT = getattr(config, "TAROT_SYSTEM_PROMPT", DEFAULT_TAROT_SYSTEM_PROMPT)
# SPREAD_SELECTOR_PROMPT = getattr(config, "TAROT_SPREAD_SELECTOR_PROMPT", DEFAULT_SPREAD_SELECTOR_PROMPT)
# CHAT_MANAGER_PROMPT = getattr(config, "TAROT_CHAT_MANAGER_PROMPT", DEFAULT_CHAT_MANAGER_PROMPT)

# # Окремий prompt для уточнення 1 картою (розширене трактування)
# CLARIFIER_PROMPT = getattr(
#     config,
#     "TAROT_CLARIFIER_PROMPT",
#     """
# Ти — таролог-наставник. Ти отримуєш:
# - короткий підсумок попереднього розкладу
# - 1 уточнюючу карту

# Завдання: дати РОЗШИРЕНЕ уточнення — як ця карта доповнює/змінює попередній висновок.
# Ти тлумачиш ТІЛЬКИ цю уточнюючу карту і логічно привʼязуєш її до попереднього.

# ФОРМАТ (PLAIN TEXT):
# 🃏 Уточнення: <карта> (⬆️/⬇️) — 3–6 речень по суті
# ✨ Як це впливає на попередній розклад: 3–6 речень
# ✅ Практика (3 кроки):
# - ...
# - ...
# - ...
# """
# )

# # ================== UI (HELP) ==================
# HELP_BTN_TEXT = "ℹ️ Як користуватись"
# BACK_BTN_TEXT = "🔙 Назад"


# def help_welcome_inline_kb():
#     kb = InlineKeyboardBuilder()
#     kb.button(text=HELP_BTN_TEXT, callback_data="tarot_help_open")
#     return kb.as_markup()


# def help_back_inline_kb():
#     kb = InlineKeyboardBuilder()
#     kb.button(text=BACK_BTN_TEXT, callback_data="tarot_help_back")
#     return kb.as_markup()


# def dialog_kb():
#     return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text=EXIT_TEXT)]])


# def build_welcome_text() -> str:
#     return "✨ Привіт! Я поруч ❤️\nПиши як у звичайному чаті — підтримаю, а коли треба, зроблю розклад."


# def build_help_text() -> str:
#     return (
#         "ℹ️ <b>Як користуватись Живим Таро-чатом</b>\n\n"
#         "• Пиши як у звичайному чаті.\n"
#         "• Якщо потрібна ясність — зроблю розклад і поясню по позиціях.\n"
#         "• Якщо хочеш доповнити вже зроблений розклад — напиши: «доповни розклад / дотягни карту».\n\n"
#         "Розклади:\n"
#         "3 — коротко/швидко\n"
#         "4 — стосунки ❤️\n"
#         "5 — гроші/робота/вибір/переїзд 💼💰🧭\n"
#         "10 — глибоко/криза/комплексно 🔮\n\n"
#         f"⚡ Списується тільки за розклад або уточнення (1 карта): <b>{ENERGY_COST_PER_READING}</b> енергії."
#     )

# # ================== HISTORY + LAST READING ==================
# chat_histories: Dict[int, List[Dict[str, str]]] = {}
# last_reading: Dict[int, Dict[str, Any]] = {}


# def get_chat_history(user_id: int) -> List[Dict[str, str]]:
#     if user_id not in chat_histories:
#         chat_histories[user_id] = []
#     return chat_histories[user_id]


# def add_chat_message(user_id: int, role: str, content: str):
#     h = get_chat_history(user_id)
#     h.append({"role": role, "content": content})
#     if len(h) > 24:
#         chat_histories[user_id] = h[-24:]


# def short_context(user_id: int) -> str:
#     h = get_chat_history(user_id)[-10:]
#     lines = []
#     for m in h:
#         role = "Користувач" if m["role"] == "user" else "Бот"
#         lines.append(f"{role}: {m['content']}")
#     return "\n".join(lines).strip()

# # ================== SMALLTALK FILTER ==================
# SMALLTALK_SET = {
#     "дякую", "дякс", "спасибі", "мерсі",
#     "ок", "окей", "добре", "ясно", "зрозуміло", "супер", "круто", "клас", "топ",
#     "ага", "угу",
#     "👍", "❤️", "🙏", "✅",
# }
# ONLY_EMOJI_RE = re.compile(r"^[\s\.\,\!\?\-…:;()\[\]{}\"'«»🙂😉😊😀😅😂🤣😍❤️💔👍🙏💛✨🔥💯✅]+$")


# def is_non_query_message(text: str) -> bool:
#     if not text:
#         return True
#     raw = text.strip()
#     t = raw.lower().replace("’", "'").replace("‘", "'").strip()

#     if ONLY_EMOJI_RE.match(raw):
#         return True
#     if "?" in raw:
#         return False
#     if t in SMALLTALK_SET:
#         return True
#     if t.startswith(("дякую", "дякс", "спасиб", "ок", "окей", "добре", "ясно", "зрозуміло")):
#         # якщо в цьому є реальний запит — не блокуємо
#         intent_words = ["що", "як", "коли", "чи", "порада", "вибір", "робота", "гроші", "стосун", "переїзд", "розклад"]
#         if any(w in t for w in intent_words):
#             return False
#         return True
#     if len(t) <= 5:
#         return True
#     return False


# def smalltalk_reply() -> str:
#     variants = [
#         "❤️ Я поруч. Якщо захочеш — напиши, що саме зараз найбільше хвилює.",
#         "Добре 😊 Розкажи, що хочеш прояснити або що не дає спокою.",
#         "Ок ✨ Якщо треба — можемо глибше розібрати ситуацію.",
#     ]
#     return random.choice(variants)

# # ================== FOLLOW-UP / CLARIFIER (ALWAYS 1 CARD) ==================
# FOLLOWUP_TRIGGERS = [
#     "доповни", "поглиб", "уточни", "детальніше", "поясни детальніше",
#     "дотягни", "дотягни карту", "додай карту", "ще карту", "ще одну карту",
#     "уточнення", "проясни",
#     "розшир", "розширене трактування", "розшифруй",
# ]

# FOLLOWUP_RE = re.compile(
#     r"(доповн|поглиб|уточн|детальніш|проясн|дотягн|додай|ще\s+карт|ще\s+одн|розшир|розшифруй)",
#     re.IGNORECASE,
# )


# def is_followup_request(user_id: int, text: str) -> bool:
#     if user_id not in last_reading:
#         return False
#     t = (text or "").strip().lower()
#     if not t:
#         return False
#     if FOLLOWUP_RE.search(t):
#         return True
#     if any(x in t for x in FOLLOWUP_TRIGGERS):
#         return True
#     # коротке "чому?" після розкладу
#     if len(t) <= 12 and "чому" in t:
#         return True
#     return False

# # ================== SPREAD SELECTION ==================
# EXPLICIT_AMOUNT_RE = re.compile(r"(?<!\d)(3|4|5|10)(?!\d)")


# def parse_explicit_amount(text: str) -> Optional[int]:
#     t = (text or "").lower()
#     if "кельт" in t:
#         return 10
#     m = EXPLICIT_AMOUNT_RE.search(t)
#     if m and re.search(rf"{m.group(1)}\s*(карт|карти|розклад)", t):
#         n = int(m.group(1))
#         if n in (3, 4, 5, 10):
#             return n
#     return None


# def rule_based_amount(text: str) -> Optional[int]:
#     t = (text or "").lower()

#     rel = ["стосун", "відносин", "взаємин", "кохан", "любов", "партнер", "екс", "колишн", "між нами"]
#     work_money = ["робот", "кар'єр", "гроші", "дохід", "борг", "переїзд", "план", "вибір", "рішення"]
#     deep = ["криза", "тупик", "по колу", "детально", "глибок", "безвихід", "все одразу", "роками"]

#     rel_score = sum(1 for w in rel if w in t)
#     wm_score = sum(1 for w in work_money if w in t)
#     deep_score = sum(1 for w in deep if w in t)

#     best = max(rel_score, wm_score, deep_score)
#     if best >= 2:
#         if deep_score == best:
#             return 10
#         if wm_score == best:
#             return 5
#         if rel_score == best:
#             return 4
#     return None


# def choose_spread_layout(amount: int, user_text: str) -> Tuple[str, List[str]]:
#     t = (user_text or "").lower()

#     if amount == 10:
#         return (
#             "Кельтський хрест (10)",
#             [
#                 "Поточна ситуація",
#                 "Головний виклик / що перехрещує",
#                 "Корінь / глибинна причина",
#                 "Минуле, що вплинуло",
#                 "Тенденція / що над ситуацією",
#                 "Найближче майбутнє",
#                 "Ти / твоє ставлення",
#                 "Зовнішні впливи / обставини",
#                 "Надії та побоювання",
#                 "Підсумок / результат",
#             ],
#         )
#     if amount == 4:
#         return (
#             "Стосунки (4)",
#             [
#                 "Як виглядає зв’язок загалом",
#                 "Почуття/намір між вами",
#                 "Що напружує / що заважає",
#                 "Куди це рухається (вектор)",
#             ],
#         )
#     if amount == 5:
#         return (
#             "Поглиблений розклад ситуації (5)",
#             [
#                 "Поточна ситуація",
#                 "Ресурс / що допомагає",
#                 "Виклик / що заважає",
#                 "Приховане / те, чого не видно",
#                 "Ймовірний напрямок / результат",
#             ],
#         )

#     # 3 cards
#     future_words = ["коли", "чи буде", "буде", "в майбутньому", "прогноз", "через", "наступ"]
#     action_words = ["що робити", "як бути", "як діяти", "вибір", "виріш", "порада", "план", "крок", "чи варто"]

#     if any(w in t for w in future_words):
#         return ("Три карти (3): Минуле—Теперішнє—Майбутнє", ["Минуле", "Теперішнє", "Майбутнє"])
#     if any(w in t for w in action_words):
#         return ("Три карти (3): Допомагає—Заважає—Порада", ["Що допомагає", "Що заважає", "Порада / як діяти"])
#     return ("Три карти (3): Суть—Виклик—Порада", ["Суть ситуації", "Ключовий виклик", "Порада / напрям"])


# def _extract_json_object(raw: str) -> Optional[dict]:
#     raw = (raw or "").strip()
#     if not raw:
#         return None
#     try:
#         return json.loads(raw)
#     except Exception:
#         pass
#     m = re.search(r"\{.*\}", raw, re.S)
#     if not m:
#         return None
#     try:
#         return json.loads(m.group(0))
#     except Exception:
#         return None


# async def choose_spread_via_gpt(user_text: str) -> Tuple[int, str, List[str]]:
#     explicit = parse_explicit_amount(user_text)
#     if explicit:
#         name, pos = choose_spread_layout(explicit, user_text)
#         return explicit, name, pos

#     rb = rule_based_amount(user_text)
#     if rb:
#         name, pos = choose_spread_layout(rb, user_text)
#         return rb, name, pos

#     # GPT selector fallback
#     try:
#         try:
#             r = await client.chat.completions.create(
#                 model="gpt-4.1-mini",
#                 messages=[
#                     {"role": "system", "content": SPREAD_SELECTOR_PROMPT},
#                     {"role": "user", "content": user_text},
#                 ],
#                 max_tokens=260,
#                 temperature=0.15,
#                 response_format={"type": "json_object"},
#             )
#         except TypeError:
#             r = await client.chat.completions.create(
#                 model="gpt-4.1-mini",
#                 messages=[
#                     {"role": "system", "content": SPREAD_SELECTOR_PROMPT},
#                     {"role": "user", "content": user_text},
#                 ],
#                 max_tokens=260,
#                 temperature=0.15,
#             )

#         raw = (r.choices[0].message.content or "").strip()
#         data = _extract_json_object(raw) or {}
#         amount = int(data.get("amount", 3))
#         if amount not in (3, 4, 5, 10):
#             amount = 3

#         spread_name = str(data.get("spread_name", "")).strip()
#         positions = data.get("positions")

#         if not isinstance(positions, list) or len(positions) != amount:
#             spread_name, positions = choose_spread_layout(amount, user_text)
#         else:
#             positions = [str(p).strip() for p in positions]
#             if not spread_name:
#                 spread_name, positions = choose_spread_layout(amount, user_text)

#         return amount, spread_name, positions

#     except Exception:
#         amount = 3
#         spread_name, positions = choose_spread_layout(amount, user_text)
#         return amount, spread_name, positions

# # ================== CARDS ==================
# def draw_cards(amount: int) -> List[dict]:
#     names = list(TAROT_CARDS.keys())
#     amount = max(1, min(amount, len(names), 10))
#     chosen = random.sample(names, amount)

#     result = []
#     for name in chosen:
#         upright = random.choice([True, False])
#         ua = TAROT_CARDS[name]["ua_name"]
#         img_path = TAROT_CARDS[name]["image"]
#         result.append({"code": name, "ua": ua, "upright": upright, "image": img_path})
#     return result


# def build_cards_payload_ready(spread_name: str, positions: List[str], user_text: str, cards: List[dict]) -> str:
#     amount = len(cards)
#     pos_lines = "\n".join([f"{i}. {positions[i-1]}" for i in range(1, amount + 1)])
#     cards_lines = "\n".join(
#         f"{i}. {c['ua']} ({c['code']}) {('⬆️' if c['upright'] else '⬇️')}"
#         for i, c in enumerate(cards, start=1)
#     )
#     return (
#         f"Схема розкладу: {spread_name}\n"
#         f"Позиції:\n{pos_lines}\n\n"
#         f"Витягнуті карти:\n{cards_lines}\n\n"
#         f"Запит користувача (контекст): {user_text}"
#     )


# def strip_bad_phrases(text: str) -> str:
#     if not text:
#         return ""
#     bad_patterns = [
#         r"дякую", r"спасиб", r"thanks", r"thank you",
#         r"чекаю", r"жду",
#         r"коли будеш готов", r"когда будешь готов",
#         r"поділи(сь|ться).*карт", r"подел(ись|итесь).*карт",
#         r"скажи коли", r"скажи когда",
#         r"коли витягнеш", r"когда вытащишь",
#     ]
#     lines = text.splitlines()
#     cleaned: List[str] = []
#     for ln in lines:
#         low = ln.strip().lower()
#         if any(re.search(p, low) for p in bad_patterns):
#             continue
#         cleaned.append(ln)
#     return "\n".join(cleaned).strip()

# # ================== SINGLE CARD IMAGE (фон + 1 карта) ==================
# def _safe_bg(path: str) -> Image.Image:
#     if path and os.path.exists(path):
#         return Image.open(path).convert("RGBA")
#     return Image.new("RGBA", (1200, 800), (20, 20, 20, 255))


# def _load_font(size: int) -> ImageFont.ImageFont:
#     try:
#         return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
#     except Exception:
#         try:
#             return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
#         except Exception:
#             return ImageFont.load_default()


# def _save_temp_png(img: Image.Image) -> str:
#     tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
#     tmp.close()
#     img.save(tmp.name, "PNG", optimize=True)
#     return tmp.name


# def make_single_card_on_background(card_path: str, upright: bool, background_path: str = BACKGROUND_PATH) -> str:
#     bg = _safe_bg(background_path)
#     W, H = bg.size

#     card = Image.open(card_path).convert("RGBA")
#     if not upright:
#         card = card.rotate(180, expand=True)

#     # resize card to fit nicely
#     max_w = int(W * 0.42)
#     max_h = int(H * 0.78)
#     cw, ch = card.size
#     scale = min(max_w / cw, max_h / ch)
#     card = card.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)

#     # shadow
#     shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
#     mask = Image.new("L", card.size, 0)
#     d = ImageDraw.Draw(mask)
#     d.rounded_rectangle((0, 0, card.size[0], card.size[1]), radius=36, fill=170)
#     shadow.paste((0, 0, 0, 140), (0, 0), mask)
#     shadow = shadow.filter(ImageFilter.GaussianBlur(28))

#     x = (W - card.size[0]) // 2
#     y = (H - card.size[1]) // 2

#     bg.alpha_composite(shadow, (x + 14, y + 20))
#     bg.alpha_composite(card, (x, y))

#     # small label "Уточнення"
#     overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
#     draw = ImageDraw.Draw(overlay)
#     font = _load_font(28)
#     txt = "Уточнення"
#     bbox = draw.textbbox((0, 0), txt, font=font)
#     tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
#     px, py = 16, 10
#     rw, rh = tw + px * 2, th + py * 2
#     lx, ly = x + 18, y + 18
#     draw.rounded_rectangle((lx, ly, lx + rw, ly + rh), radius=14, fill=(0, 0, 0, 150))
#     draw.text((lx + px, ly + py), txt, font=font, fill=(255, 255, 255, 255))
#     bg.alpha_composite(overlay)

#     return _save_temp_png(bg)

# # ================== GPT CHAT MANAGER ==================
# async def manager_decide(user_id: int, user_text: str) -> Dict[str, Any]:
#     if is_non_query_message(user_text):
#         return {"mode": "chat", "reply": smalltalk_reply(), "amount": None}

#     payload = (
#         "ТИП: Живий чат\n"
#         "Мова: українська\n\n"
#         f"Короткий контекст:\n{short_context(user_id)}\n\n"
#         f"Повідомлення користувача:\n{user_text}"
#     )

#     try:
#         try:
#             r = await client.chat.completions.create(
#                 model="gpt-4.1-mini",
#                 messages=[
#                     {"role": "system", "content": CHAT_MANAGER_PROMPT},
#                     {"role": "user", "content": payload},
#                 ],
#                 max_tokens=320,
#                 temperature=0.85,
#                 response_format={"type": "json_object"},
#             )
#         except TypeError:
#             r = await client.chat.completions.create(
#                 model="gpt-4.1-mini",
#                 messages=[
#                     {"role": "system", "content": CHAT_MANAGER_PROMPT},
#                     {"role": "user", "content": payload},
#                 ],
#                 max_tokens=320,
#                 temperature=0.85,
#             )

#         raw = (r.choices[0].message.content or "").strip()
#         data = _extract_json_object(raw) or {}

#         mode = str(data.get("mode", "chat")).strip().lower()
#         if mode not in ("chat", "clarify", "spread"):
#             mode = "chat"

#         reply = str(data.get("reply", "")).strip()
#         if not reply:
#             reply = smalltalk_reply()

#         amount = data.get("amount", None)
#         if amount is not None:
#             try:
#                 amount = int(amount)
#             except Exception:
#                 amount = None
#             if amount not in (3, 4, 5, 10):
#                 amount = None

#         return {"mode": mode, "reply": reply, "amount": amount}

#     except Exception:
#         return {"mode": "chat", "reply": smalltalk_reply(), "amount": None}

# # ================== SPINNER ==================
# SPINNER_FRAMES = ["🔮 Дивлюсь уважно…", "🔮 Дивлюсь уважно… .", "🔮 Дивлюсь уважно… ..", "🔮 Дивлюсь уважно… ..."]


# async def _run_spinner(msg: types.Message, stop: asyncio.Event, interval: float = 0.35):
#     i = 0
#     last_text = None
#     while not stop.is_set():
#         text = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
#         i += 1
#         try:
#             if text != last_text:
#                 await msg.edit_text(text)
#                 last_text = text
#         except Exception:
#             pass
#         try:
#             await msg.bot.send_chat_action(msg.chat.id, "typing")
#         except Exception:
#             pass
#         await asyncio.sleep(interval)


# async def start_spinner(message: types.Message):
#     spinner_msg = await message.answer(SPINNER_FRAMES[0])
#     stop_event = asyncio.Event()
#     task = asyncio.create_task(_run_spinner(spinner_msg, stop_event))
#     return spinner_msg, stop_event, task


# async def stop_spinner(spinner_msg: types.Message, stop_event: asyncio.Event, task: asyncio.Task):
#     stop_event.set()
#     try:
#         await asyncio.wait_for(task, timeout=2.0)
#     except Exception:
#         pass
#     try:
#         await spinner_msg.delete()
#     except Exception:
#         pass

# # ================== HELP CALLBACKS ==================
# @dialog_router.callback_query(F.data == "tarot_help_open")
# async def tarot_help_open(callback: types.CallbackQuery):
#     await callback.answer()
#     try:
#         await callback.message.edit_text(build_help_text(), reply_markup=help_back_inline_kb(), parse_mode="HTML")
#     except Exception:
#         await callback.message.answer(build_help_text(), reply_markup=help_back_inline_kb(), parse_mode="HTML")


# @dialog_router.callback_query(F.data == "tarot_help_back")
# async def tarot_help_back(callback: types.CallbackQuery):
#     await callback.answer()
#     try:
#         await callback.message.edit_text(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
#     except Exception:
#         await callback.message.answer(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")

# # ================== ENERGY PANEL ==================
# def energy_panel_kb() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="💛 Написати касиру", callback_data="energy_topup")],
#             [InlineKeyboardButton(text="👥 Запросити друзів", callback_data="energy_invite")],
#         ]
#     )


# async def open_energy_panel_here(message: types.Message):
#     user = message.from_user
#     energy = await get_energy(user.id)
#     await message.answer(
#         f"⚡ <b>Енергетичний баланс</b>\n\n"
#         f"👤 {user.full_name}\n"
#         f"✨ Баланс: <b>{energy}</b> енергії\n\n"
#         f"Обери дію:",
#         reply_markup=energy_panel_kb(),
#         parse_mode="HTML",
#     )

# # ================== FSM ==================
# class TarotChatFSM(StatesGroup):
#     chatting = State()

# # ================== START / EXIT ==================
# @dialog_router.message(F.text == "🔮 Живий Таро-чат")
# async def start_dialog(message: types.Message, state: FSMContext):
#     await state.set_state(TarotChatFSM.chatting)
#     user_id = message.from_user.id
#     chat_histories[user_id] = []
#     await message.answer(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
#     await message.answer("👇 Напиши, що хвилює", reply_markup=dialog_kb())


# @dialog_router.message(F.text == EXIT_TEXT)
# async def exit_dialog(message: types.Message, state: FSMContext):
#     user_id = message.from_user.id
#     try:
#         await message.delete()
#     except Exception:
#         pass
#     kb = build_main_menu(user_id)
#     await message.bot.send_message(message.chat.id, "🔙 Повертаю в головне меню.", reply_markup=kb)
#     await state.clear()

# # ================== MAIN CHAT ==================
# @dialog_router.message(TarotChatFSM.chatting)
# async def chat(message: types.Message, state: FSMContext):
#     user_id = message.from_user.id
#     user_text = (message.text or "").strip()
#     if not user_text:
#         return

#     add_chat_message(user_id, "user", user_text)

#     # 1) якщо подяка/ок/емоції — просто відповідаємо (НЕ розклад)
#     if is_non_query_message(user_text):
#         reply = smalltalk_reply()
#         await message.answer(reply)
#         add_chat_message(user_id, "assistant", reply)
#         return

#     # 2) якщо це доповнення до попереднього — тягнемо РІВНО 1 карту
#     if is_followup_request(user_id, user_text):
#         current = await get_energy(user_id)
#         if current < ENERGY_COST_PER_READING:
#             await state.clear()
#             kb = build_main_menu(user_id)
#             await message.answer(
#                 "🔋 <b>Енергія закінчилась</b> — щоб доповнити розклад, потрібно поповнити ⚡\n\n"
#                 f"Потрібно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
#                 f"У вас: <b>{current}</b> ✨",
#                 parse_mode="HTML",
#                 reply_markup=kb,
#             )
#             await open_energy_panel_here(message)
#             return

#         await message.answer("Добре 🔎 Дотягую 1 уточнюючу карту і розширюю трактування…")

#         clar_card = draw_cards(1)[0]
#         arrow = "⬆️" if clar_card["upright"] else "⬇️"

#         # картинка для 1 карти (фон + карта)
#         single_img = make_single_card_on_background(clar_card["image"], clar_card["upright"], BACKGROUND_PATH)
#         await message.answer_photo(
#             photo=FSInputFile(single_img),
#             caption=f"🃏 Уточнююча карта: {clar_card['ua']} {arrow}",
#         )
#         try:
#             os.remove(single_img)
#         except Exception:
#             pass

#         lr = last_reading.get(user_id, {})
#         prev_summary = (
#             f"Попередній розклад: {lr.get('spread_name','')}\n"
#             f"Попередній запит: {lr.get('question','')}\n"
#             f"Короткий підсумок: {lr.get('short','')}\n\n"
#             f"Запит на уточнення від користувача: {user_text}"
#         )

#         payload = (
#             f"ПОПЕРЕДНІЙ КОНТЕКСТ:\n{prev_summary}\n\n"
#             f"Витягнуті карти:\n1. {clar_card['ua']} ({clar_card['code']}) {arrow}\n"
#         )

#         spinner_msg = stop_event = spinner_task = None
#         try:
#             spinner_msg, stop_event, spinner_task = await start_spinner(message)

#             resp = await client.chat.completions.create(
#                 model="gpt-4.1-mini",
#                 messages=[
#                     {"role": "system", "content": CLARIFIER_PROMPT},
#                     {"role": "user", "content": payload},
#                 ],
#                 max_tokens=1600,
#                 temperature=0.78,
#             )
#             final_reply = (resp.choices[0].message.content or "").strip()
#             final_reply = strip_bad_phrases(final_reply)

#         except Exception:
#             if spinner_msg and stop_event and spinner_task:
#                 await stop_spinner(spinner_msg, stop_event, spinner_task)
#             await message.answer("⚠️ Не вдалося доповнити трактування. Спробуй ще раз.")
#             return

#         if spinner_msg and stop_event and spinner_task:
#             await stop_spinner(spinner_msg, stop_event, spinner_task)

#         await change_energy(user_id, -ENERGY_COST_PER_READING)
#         await message.answer(final_reply)
#         add_chat_message(user_id, "assistant", final_reply)

#         # оновлюємо last_reading (додаємо уточнення до short)
#         last_reading[user_id] = {
#             "question": lr.get("question", ""),
#             "spread_name": lr.get("spread_name", ""),
#             "cards": lr.get("cards", []),
#             "short": (lr.get("short", "") + "\n\n[Уточнення]\n" + final_reply)[:900],
#         }
#         return

#     # 3) звичайний чат-менеджер: chat/clarify/spread
#     decision = await manager_decide(user_id, user_text)
#     await message.answer(decision["reply"])
#     add_chat_message(user_id, "assistant", decision["reply"])

#     if decision["mode"] in ("chat", "clarify"):
#         return

#     # 4) spread -> перевірка енергії
#     current = await get_energy(user_id)
#     if current < ENERGY_COST_PER_READING:
#         await state.clear()
#         kb = build_main_menu(user_id)
#         await message.answer(
#             "🔋 <b>Енергія закінчилась</b> — щоб зробити розклад, потрібно поповнити ⚡\n\n"
#             f"Потрібно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
#             f"У вас: <b>{current}</b> ✨",
#             parse_mode="HTML",
#             reply_markup=kb,
#         )
#         await open_energy_panel_here(message)
#         return

#     # 5) підбір розкладу (точніше): manager amount -> rules -> gpt selector
#     amount = decision.get("amount")
#     if amount not in (3, 4, 5, 10):
#         rb = rule_based_amount(user_text)
#         if rb:
#             amount = rb
#             spread_name, positions = choose_spread_layout(amount, user_text)
#         else:
#             amount, spread_name, positions = await choose_spread_via_gpt(user_text)
#     else:
#         amount = int(amount)
#         spread_name, positions = choose_spread_layout(amount, user_text)

#     # 6) тягнемо карти
#     cards = draw_cards(amount)

#     await message.answer(f"🃏 Роблю розклад: {spread_name}")
#     await asyncio.sleep(0.15)

#     img_paths = [c["image"] for c in cards]
#     uprights = [c["upright"] for c in cards]

#     final_img = combine_spread_image(
#         img_paths,
#         uprights,
#         amount,
#         background_path=BACKGROUND_PATH,
#         background_path10=BACKGROUND_PATH10,
#     )

#     lines = []
#     for i, c in enumerate(cards, start=1):
#         arrow = "⬆️" if c["upright"] else "⬇️"
#         lines.append(f"{i}. {c['ua']} {arrow}")

#     caption = "🃏 <b>Витягнуті карти:</b>\n" + "\n".join(lines)
#     await message.answer_photo(photo=FSInputFile(final_img), caption=caption, parse_mode="HTML")

#     try:
#         os.remove(final_img)
#     except Exception:
#         pass

#     # 7) GPT тлумачення (строго по витягнутих картах)
#     payload = build_cards_payload_ready(spread_name, positions, user_text, cards)

#     spinner_msg = stop_event = spinner_task = None
#     try:
#         spinner_msg, stop_event, spinner_task = await start_spinner(message)

#         resp = await client.chat.completions.create(
#             model="gpt-4.1-mini",
#             messages=[
#                 {"role": "system", "content": TAROT_SYSTEM_PROMPT},
#                 {"role": "user", "content": payload},
#             ],
#             max_tokens=2000,
#             temperature=0.78,
#         )
#         final_reply = (resp.choices[0].message.content or "").strip()
#         final_reply = strip_bad_phrases(final_reply)

#     except Exception:
#         if spinner_msg and stop_event and spinner_task:
#             await stop_spinner(spinner_msg, stop_event, spinner_task)
#         await message.answer("⚠️ Не вдалося отримати тлумачення. Спробуй ще раз.")
#         return

#     if spinner_msg and stop_event and spinner_task:
#         await stop_spinner(spinner_msg, stop_event, spinner_task)

#     await change_energy(user_id, -ENERGY_COST_PER_READING)
#     await message.answer(final_reply)
#     add_chat_message(user_id, "assistant", final_reply)

#     # зберігаємо останній розклад для уточнення 1 картою
#     last_reading[user_id] = {
#         "question": user_text,
#         "spread_name": spread_name,
#         "cards": cards,
#         "short": final_reply[:450],
#     }


import os
import re
import json
import random
import asyncio
import tempfile
import time
from typing import List, Dict, Tuple, Optional, Any

from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from openai import AsyncOpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config
from cards_data import TAROT_CARDS
from modules.menu import build_main_menu
from modules.user_stats_db import get_energy, change_energy
from modules.tarot_spread_image import combine_spread_image  # ✅ 3/4/5/10


dialog_router = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

# ======================
# SETTINGS
# ======================
ENERGY_COST_PER_READING = 2          # списується тільки за розклад / уточнення (1 карта)
BACKGROUND_PATH = "background.png"
BACKGROUND_PATH10 = "bg.png"
EXIT_TEXT = "⬅️ Завершити бесіду"

# ---- Clarify throttling (щоб бот рідко уточнював і частіше робив розклади) ----
CLARIFY_COOLDOWN_SECONDS = 15 * 60   # не частіше ніж раз на 15 хв
CLARIFY_MIN_TEXT_LEN = 18           # якщо дуже коротко і без теми — тоді можна уточнити
last_clarify_ts: Dict[int, float] = {}  # трекер останнього уточнення

# ======================
# PROMPTS (from config or fallback)
# ======================
DEFAULT_TAROT_SYSTEM_PROMPT = """
Ти — професійний таролог-наставник. Тон живий, теплий, але може бути прямим і жорстким,
якщо карти реально на це вказують (без приниження, без залякувань).

ГОЛОВНЕ:
- Ти НЕ вигадуєш карти. Тлумачиш ТІЛЬКИ ті, що в блоці “Витягнуті карти”.
- Ти НЕ пишеш “дякую за запит”, НЕ просиш карти, НЕ кажеш що “чекаєш”.
- Без HTML і без markdown. Тільки PLAIN TEXT.

ФОРМАТ ДЛЯ ОСНОВНОГО РОЗКЛАДУ:
🎯 Фокус запиту: 1 коротке речення.
🔮 Розклад: <назва>
🧩 По позиціях:
1) <позиція> — <карта> (⬆️/⬇️): 2–4 речення
...
✨ Зв’язки між картами: 3–6 речень
🧭 Висновок: 2–4 речення
✅ Практична порада:
- 3 конкретні кроки

ПСИХОЛОГІЧНА БЕЗПЕКА:
- “важкі” карти — як сигнал/тема уваги ⚠️, без фаталізму
- здоровʼя — без діагнозів: режим/стрес/ресурс
"""

DEFAULT_SPREAD_SELECTOR_PROMPT = """
Ти — асистент, який ВИБИРАЄ ТІЛЬКИ розклад Таро під запит користувача.
Ти НЕ тлумачиш карти. НЕ ставиш питань. Повертаєш ТІЛЬКИ валідний JSON.

ДОСТУПНО: 3,4,5,10 (НІКОЛИ не 1)
Формат:
{
  "amount": 3|4|5|10,
  "spread_name": "…",
  "positions": ["…", "..."],
  "scheme_hint": "коротко чому"
}
"""

# ✅ диспетчер: намагається не уточнювати, за замовчуванням spread
DEFAULT_CHAT_MANAGER_PROMPT = r"""
Ти — диспетчер живого таро-чату. Твоя задача: визначити режим:
- "chat" = дружня розмова/підтримка (без розкладу)
- "spread" = робимо розклад (коли є питання/ситуація)
- "clarify" = ОДНЕ уточнення, тільки якщо ІНАКШЕ розклад буде зовсім "в нікуди"

ВАЖЛИВО:
- "clarify" використовуй МАКСИМАЛЬНО РІДКО. Якщо можна — обирай "spread".
- Якщо користувач просто подякував/ок/👍 — обирай "chat".
- Не вигадуй, що карти вже витягнуті.
- Пиши українською.

Поверни ТІЛЬКИ JSON:
{
  "mode": "chat" | "clarify" | "spread",
  "reply": "короткий текст українською (1-2 речення)",
  "amount": 3|4|5|10|null
}

Підбір amount (коли mode=spread):
- Стосунки/між нами/почуття/він-вона/екс → 4
- Робота/гроші/переїзд/вибір/план → 5
- Криза/по колу/дуже складно/комплексно → 10
- Інакше → 3
"""

# ✅ “людський” режим — вільна розмова (без розкладу)
DEFAULT_HUMAN_CHAT_PROMPT = r"""
Ти — живий співрозмовник (як реальна людина) у таро-чаті.
Зараз РЕЖИМ: CHAT (БЕЗ розкладу).

Правила:
- Пиши українською, природно, тепло, без офіціозу.
- Можна гумор/емпатію/короткі фрази, інколи емодзі.
- НЕ згадуй, що ти ШІ/модель/бот.
- НЕ роби розклад, НЕ вигадуй карти.
- НЕ "допитуй": максимум 1 коротке питання і тільки якщо реально доречно.
- Якщо користувач явно просить розклад/карти/прогноз — скажи одне речення, що зробиш розклад (сам запуск робить код).
- Без HTML і без markdown. PLAIN TEXT.
"""

TAROT_SYSTEM_PROMPT = getattr(config, "TAROT_SYSTEM_PROMPT", DEFAULT_TAROT_SYSTEM_PROMPT)
SPREAD_SELECTOR_PROMPT = getattr(config, "TAROT_SPREAD_SELECTOR_PROMPT", DEFAULT_SPREAD_SELECTOR_PROMPT)
CHAT_MANAGER_PROMPT = getattr(config, "TAROT_CHAT_MANAGER_PROMPT", DEFAULT_CHAT_MANAGER_PROMPT)
HUMAN_CHAT_PROMPT = getattr(config, "TAROT_HUMAN_CHAT_PROMPT", DEFAULT_HUMAN_CHAT_PROMPT)

# Окремий prompt для уточнення 1 картою (розширене трактування)
CLARIFIER_PROMPT = getattr(
    config,
    "TAROT_CLARIFIER_PROMPT",
    """
Ти — таролог-наставник. Ти отримуєш:
- короткий підсумок попереднього розкладу
- 1 уточнюючу карту

Завдання: дати РОЗШИРЕНЕ уточнення — як ця карта доповнює/змінює попередній висновок.
Ти тлумачиш ТІЛЬКИ цю уточнюючу карту і логічно привʼязуєш її до попереднього.

ФОРМАТ (PLAIN TEXT):
🃏 Уточнення: <карта> (⬆️/⬇️) — 3–6 речень по суті
✨ Як це впливає на попередній розклад: 3–6 речень
✅ Практика (3 кроки):
- ...
- ...
- ...
"""
)

# ================== UI (HELP) ==================
HELP_BTN_TEXT = "ℹ️ Як користуватись"
BACK_BTN_TEXT = "🔙 Назад"


def help_welcome_inline_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text=HELP_BTN_TEXT, callback_data="tarot_help_open")
    return kb.as_markup()


def help_back_inline_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text=BACK_BTN_TEXT, callback_data="tarot_help_back")
    return kb.as_markup()


def dialog_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text=EXIT_TEXT)]])


def build_welcome_text() -> str:
    return "✨ Привіт! Я поруч ❤️\nПиши як у звичайному чаті — підтримаю, а коли треба, зроблю розклад."


def build_help_text() -> str:
    return (
        "ℹ️ <b>Як користуватись Живим Таро-чатом</b>\n\n"
        "• Пиши як у звичайному чаті.\n"
        "• Якщо потрібна ясність — зроблю розклад і поясню по позиціях.\n"
        "• Якщо хочеш доповнити вже зроблений розклад — напиши: «доповни розклад / дотягни карту».\n\n"
        "Розклади:\n"
        "3 — коротко/швидко\n"
        "4 — стосунки ❤️\n"
        "5 — гроші/робота/вибір/переїзд 💼💰🧭\n"
        "10 — глибоко/криза/комплексно 🔮\n\n"
        f"⚡ Списується тільки за розклад або уточнення (1 карта): <b>{ENERGY_COST_PER_READING}</b> енергії."
    )

# ================== HISTORY + LAST READING ==================
chat_histories: Dict[int, List[Dict[str, str]]] = {}
last_reading: Dict[int, Dict[str, Any]] = {}


def get_chat_history(user_id: int) -> List[Dict[str, str]]:
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    return chat_histories[user_id]


def add_chat_message(user_id: int, role: str, content: str):
    h = get_chat_history(user_id)
    h.append({"role": role, "content": content})
    if len(h) > 24:
        chat_histories[user_id] = h[-24:]


def short_context(user_id: int) -> str:
    h = get_chat_history(user_id)[-10:]
    lines = []
    for m in h:
        role = "Користувач" if m["role"] == "user" else "Бот"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines).strip()

# ================== SMALLTALK FILTER ==================
SMALLTALK_SET = {
    "дякую", "дякс", "спасибі", "мерсі",
    "ок", "окей", "добре", "ясно", "зрозуміло", "супер", "круто", "клас", "топ",
    "ага", "угу",
    "👍", "❤️", "🙏", "✅",
}
ONLY_EMOJI_RE = re.compile(r"^[\s\.\,\!\?\-…:;()\[\]{}\"'«»🙂😉😊😀😅😂🤣😍❤️💔👍🙏💛✨🔥💯✅]+$")

SHORT_BUT_VALID_TOPICS = {
    "гроші", "робота", "любов", "екс", "вибір", "переїзд", "стосунки", "здоров'я", "здоров’я"
}


def is_non_query_message(text: str) -> bool:
    if not text:
        return True
    raw = text.strip()
    t = raw.lower().replace("’", "'").replace("‘", "'").strip()

    if ONLY_EMOJI_RE.match(raw):
        return True
    if "?" in raw:
        return False
    if t in SMALLTALK_SET:
        return True

    if t.startswith(("дякую", "дякс", "спасиб", "ок", "окей", "добре", "ясно", "зрозуміло")):
        intent_words = ["що", "як", "коли", "чи", "порада", "вибір", "робота", "гроші", "стосун", "переїзд", "розклад"]
        if any(w in t for w in intent_words):
            return False
        return True

    if len(t) <= 7:
        if t in SHORT_BUT_VALID_TOPICS:
            return False
        if rule_based_amount(t) is not None:
            return False
        return True

    return False


def smalltalk_reply() -> str:
    variants = [
        "❤️ Я поруч. Якщо захочеш — напиши, що саме зараз найбільше хвилює.",
        "Добре 😊 Розкажи, що хочеш прояснити або що не дає спокою.",
        "Ок ✨ Якщо треба — можемо глибше розібрати ситуацію.",
    ]
    return random.choice(variants)

# ================== FOLLOW-UP / CLARIFIER (ALWAYS 1 CARD) ==================
FOLLOWUP_TRIGGERS = [
    "доповни", "поглиб", "уточни", "детальніше", "поясни детальніше",
    "дотягни", "дотягни карту", "додай карту", "ще карту", "ще одну карту",
    "уточнення", "проясни",
    "розшир", "розширене трактування", "розшифруй",
]

FOLLOWUP_RE = re.compile(
    r"(доповн|поглиб|уточн|детальніш|проясн|дотягн|додай|ще\s+карт|ще\s+одн|розшир|розшифруй)",
    re.IGNORECASE,
)


def is_followup_request(user_id: int, text: str) -> bool:
    if user_id not in last_reading:
        return False
    t = (text or "").strip().lower()
    if not t:
        return False
    if FOLLOWUP_RE.search(t):
        return True
    if any(x in t for x in FOLLOWUP_TRIGGERS):
        return True
    if len(t) <= 12 and "чому" in t:
        return True
    return False

# ================== SPREAD SELECTION ==================
EXPLICIT_AMOUNT_RE = re.compile(r"(?<!\d)(3|4|5|10)(?!\d)")


def parse_explicit_amount(text: str) -> Optional[int]:
    t = (text or "").lower()
    if "кельт" in t:
        return 10
    m = EXPLICIT_AMOUNT_RE.search(t)
    if m and re.search(rf"{m.group(1)}\s*(карт|карти|розклад)", t):
        n = int(m.group(1))
        if n in (3, 4, 5, 10):
            return n
    return None


def rule_based_amount(text: str) -> Optional[int]:
    t = (text or "").lower()

    rel = ["стосун", "відносин", "взаємин", "кохан", "любов", "партнер", "екс", "колишн", "між нами"]
    work_money = ["робот", "кар'єр", "карʼєр", "гроші", "дохід", "борг", "переїзд", "план", "вибір", "рішення"]
    deep = ["криза", "тупик", "по колу", "детально", "глибок", "безвихід", "все одразу", "роками"]

    rel_score = sum(1 for w in rel if w in t)
    wm_score = sum(1 for w in work_money if w in t)
    deep_score = sum(1 for w in deep if w in t)

    best = max(rel_score, wm_score, deep_score)
    if best >= 2:
        if deep_score == best:
            return 10
        if wm_score == best:
            return 5
        if rel_score == best:
            return 4
    return None


def choose_spread_layout(amount: int, user_text: str) -> Tuple[str, List[str]]:
    t = (user_text or "").lower()

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

    future_words = ["коли", "чи буде", "буде", "в майбутньому", "прогноз", "через", "наступ"]
    action_words = ["що робити", "як бути", "як діяти", "вибір", "виріш", "порада", "план", "крок", "чи варто"]

    if any(w in t for w in future_words):
        return ("Три карти (3): Минуле—Теперішнє—Майбутнє", ["Минуле", "Теперішнє", "Майбутнє"])
    if any(w in t for w in action_words):
        return ("Три карти (3): Допомагає—Заважає—Порада", ["Що допомагає", "Що заважає", "Порада / як діяти"])
    return ("Три карти (3): Суть—Виклик—Порада", ["Суть ситуації", "Ключовий виклик", "Порада / напрям"])


def _extract_json_object(raw: str) -> Optional[dict]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


async def choose_spread_via_gpt(user_text: str) -> Tuple[int, str, List[str]]:
    explicit = parse_explicit_amount(user_text)
    if explicit:
        name, pos = choose_spread_layout(explicit, user_text)
        return explicit, name, pos

    rb = rule_based_amount(user_text)
    if rb:
        name, pos = choose_spread_layout(rb, user_text)
        return rb, name, pos

    try:
        try:
            r = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SPREAD_SELECTOR_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=260,
                temperature=0.15,
                response_format={"type": "json_object"},
            )
        except TypeError:
            r = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SPREAD_SELECTOR_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=260,
                temperature=0.15,
            )

        raw = (r.choices[0].message.content or "").strip()
        data = _extract_json_object(raw) or {}
        amount = int(data.get("amount", 3))
        if amount not in (3, 4, 5, 10):
            amount = 3

        spread_name = str(data.get("spread_name", "")).strip()
        positions = data.get("positions")

        if not isinstance(positions, list) or len(positions) != amount:
            spread_name, positions = choose_spread_layout(amount, user_text)
        else:
            positions = [str(p).strip() for p in positions]
            if not spread_name:
                spread_name, positions = choose_spread_layout(amount, user_text)

        return amount, spread_name, positions

    except Exception:
        amount = 3
        spread_name, positions = choose_spread_layout(amount, user_text)
        return amount, spread_name, positions

# ================== CLARIFY + INTENT GATING ==================
VAGUE_WORDS = {"підкажи", "порада", "розклад", "скажеш", "допоможи", "поясни", "підкажіть"}

SMALLTALK_Q_PHRASES = [
    "як ти", "як справи", "що нового", "ти тут", "ти де", "хто ти",
    "чим займаєшся", "що робиш", "як день", "як настрій"
]


def has_topic_markers(text: str) -> bool:
    t = (text or "").lower()
    if rule_based_amount(t) is not None:
        return True
    markers = [
        "він", "вона", "ми", "партнер", "чоловік", "дружина", "колишн", "екс",
        "робот", "грош", "борг", "дохід", "кар'єр", "карʼєр",
        "переїзд", "місто", "країна",
        "вибір", "рішення", "варто", "коли", "чи буде", "що робити", "як бути"
    ]
    return any(m in t for m in markers)


def is_smalltalk_question(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(p in t for p in SMALLTALK_Q_PHRASES)


def wants_spread_now(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False

    if any(w in t for w in ["розклад", "таро", "карти", "карту", "прогноз", "подивись", "поглянь"]):
        return True

    if parse_explicit_amount(t) is not None:
        return True

    if has_topic_markers(t):
        return True

    if "?" in t and not is_smalltalk_question(t):
        return True

    return False


def is_too_vague_for_spread(user_id: int, text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True

    if get_chat_history(user_id):
        if len(t) < CLARIFY_MIN_TEXT_LEN and t in VAGUE_WORDS:
            return True
        return False

    if has_topic_markers(t):
        return False

    if len(t) >= CLARIFY_MIN_TEXT_LEN:
        return False

    if len(t) < CLARIFY_MIN_TEXT_LEN and (t in VAGUE_WORDS or len(t.split()) <= 2):
        return True

    return False


def can_clarify_now(user_id: int) -> bool:
    now = time.time()
    last = last_clarify_ts.get(user_id, 0)
    return (now - last) >= CLARIFY_COOLDOWN_SECONDS


def mark_clarified(user_id: int):
    last_clarify_ts[user_id] = time.time()

# ================== CHAT REPLY GENERATION (HUMAN) ==================
def _limit_questions(text: str, max_q: int = 1) -> str:
    if not text:
        return ""
    if text.count("?") <= max_q:
        return text
    out = []
    q_used = 0
    for ch in text:
        if ch == "?":
            if q_used < max_q:
                out.append("?")
                q_used += 1
            else:
                out.append(".")
        else:
            out.append(ch)
    return "".join(out)


async def generate_human_chat_reply(user_id: int, user_text: str, hint: str = "") -> str:
    payload = (
        f"Короткий контекст (останні повідомлення):\n{short_context(user_id)}\n\n"
        f"Повідомлення користувача:\n{user_text}\n"
    )
    if hint:
        payload += f"\nНотатка:\n{hint}\n"

    try:
        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": HUMAN_CHAT_PROMPT},
                {"role": "user", "content": payload},
            ],
            max_tokens=420,
            temperature=0.95,
        )
        text = (resp.choices[0].message.content or "").strip()
        text = _limit_questions(text, max_q=1)
        return text or smalltalk_reply()
    except Exception:
        return smalltalk_reply()

# ================== CARDS ==================
def draw_cards(amount: int) -> List[dict]:
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


def build_cards_payload_ready(spread_name: str, positions: List[str], user_text: str, cards: List[dict]) -> str:
    amount = len(cards)
    pos_lines = "\n".join([f"{i}. {positions[i-1]}" for i in range(1, amount + 1)])
    cards_lines = "\n".join(
        f"{i}. {c['ua']} ({c['code']}) {('⬆️' if c['upright'] else '⬇️')}"
        for i, c in enumerate(cards, start=1)
    )
    return (
        f"Схема розкладу: {spread_name}\n"
        f"Позиції:\n{pos_lines}\n\n"
        f"Витягнуті карти:\n{cards_lines}\n\n"
        f"Запит користувача (контекст): {user_text}"
    )


def strip_bad_phrases(text: str) -> str:
    if not text:
        return ""
    bad_patterns = [
        r"дякую", r"спасиб", r"thanks", r"thank you",
        r"чекаю", r"жду",
        r"коли будеш готов", r"когда будешь готов",
        r"поділи(сь|ться).*карт", r"подел(ись|итесь).*карт",
        r"скажи коли", r"скажи когда",
        r"коли витягнеш", r"когда вытащишь",
    ]
    lines = text.splitlines()
    cleaned: List[str] = []
    for ln in lines:
        low = ln.strip().lower()
        if any(re.search(p, low) for p in bad_patterns):
            continue
        cleaned.append(ln)
    return "\n".join(cleaned).strip()

# ================== SINGLE CARD IMAGE (фон + 1 карта) ==================
def _safe_bg(path: str) -> Image.Image:
    if path and os.path.exists(path):
        return Image.open(path).convert("RGBA")
    return Image.new("RGBA", (1200, 800), (20, 20, 20, 255))


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _save_temp_png(img: Image.Image) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.close()
    img.save(tmp.name, "PNG", optimize=True)
    return tmp.name


def make_single_card_on_background(card_path: str, upright: bool, background_path: str = BACKGROUND_PATH) -> str:
    bg = _safe_bg(background_path)
    W, H = bg.size

    card = Image.open(card_path).convert("RGBA")
    if not upright:
        card = card.rotate(180, expand=True)

    max_w = int(W * 0.42)
    max_h = int(H * 0.78)
    cw, ch = card.size
    scale = min(max_w / cw, max_h / ch)
    card = card.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)

    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    mask = Image.new("L", card.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, card.size[0], card.size[1]), radius=36, fill=170)
    shadow.paste((0, 0, 0, 140), (0, 0), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))

    x = (W - card.size[0]) // 2
    y = (H - card.size[1]) // 2

    bg.alpha_composite(shadow, (x + 14, y + 20))
    bg.alpha_composite(card, (x, y))

    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(28)
    txt = "Уточнення"
    bbox = draw.textbbox((0, 0), txt, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 16, 10
    rw, rh = tw + px * 2, th + py * 2
    lx, ly = x + 18, y + 18
    draw.rounded_rectangle((lx, ly, lx + rw, ly + rh), radius=14, fill=(0, 0, 0, 150))
    draw.text((lx + px, ly + py), txt, font=font, fill=(255, 255, 255, 255))
    bg.alpha_composite(overlay)

    return _save_temp_png(bg)

# ================== GPT DISPATCHER ==================
async def manager_decide(user_id: int, user_text: str) -> Dict[str, Any]:
    if is_non_query_message(user_text):
        return {"mode": "chat", "reply": "", "amount": None}

    payload = (
        "ТИП: Диспетчер\n"
        "Мова: українська\n\n"
        f"Короткий контекст:\n{short_context(user_id)}\n\n"
        f"Повідомлення користувача:\n{user_text}"
    )

    try:
        try:
            r = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": CHAT_MANAGER_PROMPT},
                    {"role": "user", "content": payload},
                ],
                max_tokens=260,
                temperature=0.35,
                response_format={"type": "json_object"},
            )
        except TypeError:
            r = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": CHAT_MANAGER_PROMPT},
                    {"role": "user", "content": payload},
                ],
                max_tokens=260,
                temperature=0.35,
            )

        raw = (r.choices[0].message.content or "").strip()
        data = _extract_json_object(raw) or {}

        mode = str(data.get("mode", "chat")).strip().lower()
        if mode not in ("chat", "clarify", "spread"):
            mode = "chat"

        amount = data.get("amount", None)
        if amount is not None:
            try:
                amount = int(amount)
            except Exception:
                amount = None
            if amount not in (3, 4, 5, 10):
                amount = None

        return {"mode": mode, "reply": str(data.get("reply", "")).strip(), "amount": amount}

    except Exception:
        return {"mode": "chat", "reply": "", "amount": None}

# ================== SPINNER ==================
SPINNER_FRAMES = ["🔮 Дивлюсь уважно…", "🔮 Дивлюсь уважно… .", "🔮 Дивлюсь уважно… ..", "🔮 Дивлюсь уважно… ..."]


async def _run_spinner(msg: types.Message, stop: asyncio.Event, interval: float = 0.35):
    i = 0
    last_text = None
    while not stop.is_set():
        text = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
        i += 1
        try:
            if text != last_text:
                await msg.edit_text(text)
                last_text = text
        except Exception:
            pass
        try:
            await msg.bot.send_chat_action(msg.chat.id, "typing")
        except Exception:
            pass
        await asyncio.sleep(interval)


async def start_spinner(message: types.Message):
    spinner_msg = await message.answer(SPINNER_FRAMES[0])
    stop_event = asyncio.Event()
    task = asyncio.create_task(_run_spinner(spinner_msg, stop_event))
    return spinner_msg, stop_event, task


async def stop_spinner(spinner_msg: types.Message, stop_event: asyncio.Event, task: asyncio.Task):
    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except Exception:
        pass
    try:
        await spinner_msg.delete()
    except Exception:
        pass

# ================== HELP CALLBACKS ==================
@dialog_router.callback_query(F.data == "tarot_help_open")
async def tarot_help_open(callback: types.CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_text(build_help_text(), reply_markup=help_back_inline_kb(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(build_help_text(), reply_markup=help_back_inline_kb(), parse_mode="HTML")


@dialog_router.callback_query(F.data == "tarot_help_back")
async def tarot_help_back(callback: types.CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_text(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")

# ================== ENERGY PANEL ==================
def energy_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💛 Написати касиру", callback_data="energy_topup")],
            [InlineKeyboardButton(text="👥 Запросити друзів", callback_data="energy_invite")],
        ]
    )


async def open_energy_panel_here(message: types.Message):
    user = message.from_user
    energy = await get_energy(user.id)
    await message.answer(
        f"⚡ <b>Енергетичний баланс</b>\n\n"
        f"👤 {user.full_name}\n"
        f"✨ Баланс: <b>{energy}</b> енергії\n\n"
        f"Обери дію:",
        reply_markup=energy_panel_kb(),
        parse_mode="HTML",
    )

# ================== FSM ==================
class TarotChatFSM(StatesGroup):
    chatting = State()

# ================== START / EXIT ==================
@dialog_router.message(F.text == "🔮 Живий Таро-чат")
async def start_dialog(message: types.Message, state: FSMContext):
    await state.set_state(TarotChatFSM.chatting)
    user_id = message.from_user.id
    chat_histories[user_id] = []
    await message.answer(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
    await message.answer("👇 Напиши, що хвилює", reply_markup=dialog_kb())


@dialog_router.message(F.text == EXIT_TEXT)
async def exit_dialog(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        await message.delete()
    except Exception:
        pass
    kb = build_main_menu(user_id)
    await message.bot.send_message(message.chat.id, "🔙 Повертаю в головне меню.", reply_markup=kb)
    await state.clear()

# ================== MAIN CHAT ==================
@dialog_router.message(TarotChatFSM.chatting)
async def chat(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = (message.text or "").strip()
    if not user_text:
        return

    add_chat_message(user_id, "user", user_text)

    # 1) якщо подяка/ок/емоції — відповідаємо “як людина” (НЕ розклад)
    if is_non_query_message(user_text):
        reply = await generate_human_chat_reply(
            user_id,
            user_text,
            hint="Користувач не задав конкретного питання. Підтримай коротко і природно. Максимум 1 питання."
        )
        await message.answer(reply)
        add_chat_message(user_id, "assistant", reply)
        return

    # 2) якщо це доповнення до попереднього — тягнемо РІВНО 1 карту
    if is_followup_request(user_id, user_text):
        current = await get_energy(user_id)
        if current < ENERGY_COST_PER_READING:
            await state.clear()
            kb = build_main_menu(user_id)
            await message.answer(
                "🔋 <b>Енергія закінчилась</b> — щоб доповнити розклад, потрібно поповнити ⚡\n\n"
                f"Потрібно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
                f"У вас: <b>{current}</b> ✨",
                parse_mode="HTML",
                reply_markup=kb,
            )
            await open_energy_panel_here(message)
            return

        await message.answer("Добре 🔎 Дотягую 1 уточнюючу карту і розширюю трактування…")

        clar_card = draw_cards(1)[0]
        arrow = "⬆️" if clar_card["upright"] else "⬇️"

        single_img = make_single_card_on_background(clar_card["image"], clar_card["upright"], BACKGROUND_PATH)
        await message.answer_photo(
            photo=FSInputFile(single_img),
            caption=f"🃏 Уточнююча карта: {clar_card['ua']} {arrow}",
        )
        try:
            os.remove(single_img)
        except Exception:
            pass

        lr = last_reading.get(user_id, {})
        prev_summary = (
            f"Попередній розклад: {lr.get('spread_name','')}\n"
            f"Попередній запит: {lr.get('question','')}\n"
            f"Короткий підсумок: {lr.get('short','')}\n\n"
            f"Запит на уточнення від користувача: {user_text}"
        )

        payload = (
            f"ПОПЕРЕДНІЙ КОНТЕКСТ:\n{prev_summary}\n\n"
            f"Витягнуті карти:\n1. {clar_card['ua']} ({clar_card['code']}) {arrow}\n"
        )

        spinner_msg = stop_event = spinner_task = None
        try:
            spinner_msg, stop_event, spinner_task = await start_spinner(message)

            resp = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": CLARIFIER_PROMPT},
                    {"role": "user", "content": payload},
                ],
                max_tokens=1600,
                temperature=0.82,
            )
            final_reply = (resp.choices[0].message.content or "").strip()
            final_reply = strip_bad_phrases(final_reply)

        except Exception:
            if spinner_msg and stop_event and spinner_task:
                await stop_spinner(spinner_msg, stop_event, spinner_task)
            await message.answer("⚠️ Не вдалося доповнити трактування. Спробуй ще раз.")
            return

        if spinner_msg and stop_event and spinner_task:
            await stop_spinner(spinner_msg, stop_event, spinner_task)

        await change_energy(user_id, -ENERGY_COST_PER_READING)
        await message.answer(final_reply)
        add_chat_message(user_id, "assistant", final_reply)

        last_reading[user_id] = {
            "question": lr.get("question", ""),
            "spread_name": lr.get("spread_name", ""),
            "cards": lr.get("cards", []),
            "short": (lr.get("short", "") + "\n\n[Уточнення]\n" + final_reply)[:900],
        }
        return

    # 3) Якщо користувач реально питає/просить — робимо розклад без уточнень
    if wants_spread_now(user_text) and not is_smalltalk_question(user_text):
        decision = {"mode": "spread", "reply": "", "amount": None}
    else:
        decision = await manager_decide(user_id, user_text)

    # 4) CHAT режим — відповідаємо “як людина”
    if decision["mode"] == "chat":
        reply = await generate_human_chat_reply(
            user_id,
            user_text,
            hint="Режим CHAT. Будь живим співрозмовником. Без розкладу. Максимум 1 питання."
        )
        await message.answer(reply)
        add_chat_message(user_id, "assistant", reply)
        return

    # 5) CLARIFY режим — тільки якщо реально треба і не було недавно
    if decision["mode"] == "clarify":
        need_clarify = is_too_vague_for_spread(user_id, user_text)
        if need_clarify and can_clarify_now(user_id):
            # 1 уточнення, коротко
            reply = decision.get("reply") or "Щоб зробити точний розклад, уточни, будь ласка, одну річ: що саме ти хочеш прояснити?"
            reply = _limit_questions(reply, max_q=1)
            await message.answer(reply)
            add_chat_message(user_id, "assistant", reply)
            mark_clarified(user_id)
            return
        else:
            forced_reply = "Зрозумів(ла). Не будемо тягнути — зроблю розклад по тому, що ти написав(ла) 🔮"
            await message.answer(forced_reply)
            add_chat_message(user_id, "assistant", forced_reply)
            decision["mode"] = "spread"

    # 6) SPREAD -> перевірка енергії
    current = await get_energy(user_id)
    if current < ENERGY_COST_PER_READING:
        await state.clear()
        kb = build_main_menu(user_id)
        await message.answer(
            "🔋 <b>Енергія закінчилась</b> — щоб зробити розклад, потрібно поповнити ⚡\n\n"
            f"Потрібно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
            f"У вас: <b>{current}</b> ✨",
            parse_mode="HTML",
            reply_markup=kb,
        )
        await open_energy_panel_here(message)
        return

    # 7) підбір розкладу: manager amount -> rules -> gpt selector
    amount = decision.get("amount")
    if amount not in (3, 4, 5, 10):
        rb = rule_based_amount(user_text)
        if rb:
            amount = rb
            spread_name, positions = choose_spread_layout(amount, user_text)
        else:
            amount, spread_name, positions = await choose_spread_via_gpt(user_text)
    else:
        amount = int(amount)
        spread_name, positions = choose_spread_layout(amount, user_text)

    # 8) тягнемо карти
    cards = draw_cards(amount)

    await message.answer(f"🃏 Роблю розклад: {spread_name}")
    await asyncio.sleep(0.15)

    img_paths = [c["image"] for c in cards]
    uprights = [c["upright"] for c in cards]

    final_img = combine_spread_image(
        img_paths,
        uprights,
        amount,
        background_path=BACKGROUND_PATH,
        background_path10=BACKGROUND_PATH10,
    )

    lines = []
    for i, c in enumerate(cards, start=1):
        arrow = "⬆️" if c["upright"] else "⬇️"
        lines.append(f"{i}. {c['ua']} {arrow}")

    caption = "🃏 <b>Витягнуті карти:</b>\n" + "\n".join(lines)
    await message.answer_photo(photo=FSInputFile(final_img), caption=caption, parse_mode="HTML")

    try:
        os.remove(final_img)
    except Exception:
        pass

    # 9) GPT тлумачення (строго по витягнутих картах)
    payload = build_cards_payload_ready(spread_name, positions, user_text, cards)

    spinner_msg = stop_event = spinner_task = None
    try:
        spinner_msg, stop_event, spinner_task = await start_spinner(message)

        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": TAROT_SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            max_tokens=2000,
            temperature=0.82,
        )
        final_reply = (resp.choices[0].message.content or "").strip()
        final_reply = strip_bad_phrases(final_reply)

    except Exception:
        if spinner_msg and stop_event and spinner_task:
            await stop_spinner(spinner_msg, stop_event, spinner_task)
        await message.answer("⚠️ Не вдалося отримати тлумачення. Спробуй ще раз.")
        return

    if spinner_msg and stop_event and spinner_task:
        await stop_spinner(spinner_msg, stop_event, spinner_task)

    await change_energy(user_id, -ENERGY_COST_PER_READING)
    await message.answer(final_reply)
    add_chat_message(user_id, "assistant", final_reply)

    last_reading[user_id] = {
        "question": user_text,
        "spread_name": spread_name,
        "cards": cards,
        "short": final_reply[:450],
    }
