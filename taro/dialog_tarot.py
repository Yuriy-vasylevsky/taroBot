# # dialog_tarot_chat.py

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
# from PIL import Image  # для повороту 1-2 уточнюючих карт

# import config
# from cards_data import TAROT_CARDS
# from modules.menu import build_main_menu
# from modules.user_stats_db import get_energy, change_energy
# from modules.tarot_spread_image import combine_spread_image  # ✅ малювання 3/4/5/10


# dialog_router = Router()
# client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

# # ======================
# # SETTINGS
# # ======================
# ENERGY_COST_PER_READING = 2          # ✅ списується ТІЛЬКИ за розклад (включно уточнення 1-2 карти)
# BACKGROUND_PATH = "background.png"
# BACKGROUND_PATH10 = "bg.png"
# EXIT_TEXT = "⬅️ Завершити бесіду"

# # ======================
# # PROMPTS FROM CONFIG (fallbacks)
# # ======================
# DEFAULT_TAROT_SYSTEM_PROMPT = """
# Ти — професійний таролог-наставник. Тон живий, емпатичний, але може бути прямим і жорстким,
# якщо карти реально на це вказують (без образ, без залякувань).

# ГОЛОВНЕ:
# - Ти НЕ вигадуєш карти. Тлумачиш ТІЛЬКИ ті, що в блоці “Витягнуті карти”.
# - Ти НЕ дякуєш за карти/запит і НЕ пишеш, що “чекаєш карти”.
# - Ти НЕ питаєш згоду (“чи підходить?”). Подаєш як уже виконаний розклад.

# ФОРМАТ (PLAIN TEXT, без markdown і без HTML):
# 🎯 Фокус: 1 коротке речення.
# 🔮 Розклад: <назва>
# 🧩 По позиціях:
# 1) <позиція> — <карта> (⬆️/⬇️): 2–4 речення
# ...
# ✨ Зв’язки між картами: 3–6 речень
# 🧭 Висновок: 2–4 речення
# ✅ Практична порада:
# - 3 конкретні кроки

# ПСИХОЛОГІЧНА БЕЗПЕКА:
# - “важкі” карти — без залякувань, як сигнали/теми уваги.
# - Здоровʼя — без діагнозів.
# """

# DEFAULT_SPREAD_SELECTOR_PROMPT = """
# Ти — асистент, який ВИБИРАЄ ТІЛЬКИ розклад Таро під запит користувача.
# Ти НЕ тлумачиш карти. НЕ ставиш питань. Повертаєш ТІЛЬКИ валідний JSON.

# Доступно: 3,4,5,10.
# Формат:
# {
#   "amount": 3|4|5|10,
#   "spread_name": "…",
#   "positions": ["…", "..."],
#   "scheme_hint": "коротко чому"
# }
# """

# DEFAULT_CHAT_MANAGER_PROMPT = r"""
# Ти — живий таро-чат (як людина). Твоя задача: зрозуміти, що треба зараз:
# - просто підтримка/розмова
# - коротке уточнення (1 питання), якщо запит дуже розмитий
# - зробити розклад (якщо питання вже сформоване і це доречно)

# ВАЖЛИВО:
# - Якщо користувач просто подякував/ок/👍 — відповідай як людина і НЕ запускай розклад.
# - Не вигадуй, що карти вже витягнуті.
# - Пиши мовою користувача.

# Поверни ТІЛЬКИ JSON (без markdown), формат:
# {
#   "mode": "chat" | "clarify" | "spread",
#   "reply": "живий текст відповіді мовою користувача",
#   "amount": 3|4|5|10|null,
#   "why": "коротко для логу (1 рядок)"
# }

# Правила підбору amount (коли mode=spread):
# - Стосунки/між нами/він-вона/почуття → 4
# - Робота/гроші/переїзд/вибір/план → 5
# - Криза/по колу/дуже складно/комплексно → 10
# - Інакше → 3
# """

# TAROT_SYSTEM_PROMPT = getattr(config, "TAROT_SYSTEM_PROMPT", DEFAULT_TAROT_SYSTEM_PROMPT)
# SPREAD_SELECTOR_PROMPT = getattr(config, "TAROT_SPREAD_SELECTOR_PROMPT", DEFAULT_SPREAD_SELECTOR_PROMPT)
# CHAT_MANAGER_PROMPT = getattr(config, "TAROT_CHAT_MANAGER_PROMPT", DEFAULT_CHAT_MANAGER_PROMPT)

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


# def build_welcome_text(lang: str) -> str:
#     if lang == "ru":
#         return "✨ Привет! Я рядом ❤️\nМожешь просто выговориться или написать вопрос — помогу разобраться."
#     if lang == "en":
#         return "✨ Hey! I’m here with you ❤️\nYou can just talk, or ask a question — I’ll help you sort it out."
#     return "✨ Привіт! Я поруч ❤️\nМожеш просто виговоритись або написати питання — я допоможу розібратися."


# def build_help_text(lang: str) -> str:
#     if lang == "ru":
#         return (
#             "ℹ️ <b>Как пользоваться Живым Таро-чатом</b>\n\n"
#             "• Пиши как в обычном чате.\n"
#             "• Когда нужна ясность — сделаю расклад и разберу по позициям.\n\n"
#             "Расклады:\n"
#             "3 — быстро/коротко\n"
#             "4 — отношения ❤️\n"
#             "5 — деньги/работа/выбор/переезд 💼💰🧭\n"
#             "10 — глубоко/кризис/комплексно 🔮\n\n"
#             f"⚡ Списывается только за расклад: <b>{ENERGY_COST_PER_READING}</b> энергии."
#         )
#     if lang == "en":
#         return (
#             "ℹ️ <b>How to use the Live Tarot chat</b>\n\n"
#             "• Text me like a normal chat.\n"
#             "• When you need clarity — I’ll do a spread and explain it by positions.\n\n"
#             "Spreads:\n"
#             "3 — quick/short\n"
#             "4 — relationships ❤️\n"
#             "5 — money/work/choice/moving 💼💰🧭\n"
#             "10 — deep/crisis/complex 🔮\n\n"
#             f"⚡ Charged only for a spread: <b>{ENERGY_COST_PER_READING}</b> energy."
#         )
#     return (
#         "ℹ️ <b>Як користуватись Живим Таро-чатом</b>\n\n"
#         "• Пиши як у звичайному чаті.\n"
#         "• Коли потрібна ясність — зроблю розклад і поясню по позиціях.\n\n"
#         "Розклади:\n"
#         "3 — швидко/коротко\n"
#         "4 — стосунки ❤️\n"
#         "5 — гроші/робота/вибір/переїзд 💼💰🧭\n"
#         "10 — глибоко/криза/комплексно 🔮\n\n"
#         f"⚡ Списується тільки за розклад: <b>{ENERGY_COST_PER_READING}</b> енергії."
#     )

# # ================== LANGUAGE DETECT ==================
# def detect_lang(text: str) -> str:
#     t = (text or "").strip()
#     if not t:
#         return "uk"
#     low = t.lower()
#     # EN if mostly ascii
#     ascii_cnt = sum(1 for ch in low if ord(ch) < 128 and ch.isalpha())
#     cyr_cnt = sum(1 for ch in low if "а" <= ch <= "я" or ch in "іїєґёыэъ")
#     if ascii_cnt > cyr_cnt * 2 and ascii_cnt >= 6:
#         return "en"

#     # UA markers
#     if any(ch in low for ch in "іїєґ"):
#         return "uk"
#     # RU markers
#     if any(ch in low for ch in "ёыэъ"):
#         return "ru"
#     # fallback: if has cyrillic → uk default
#     if cyr_cnt > 0:
#         return "uk"
#     return "en"


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
#         role = "User" if m["role"] == "user" else "Bot"
#         lines.append(f"{role}: {m['content']}")
#     return "\n".join(lines).strip()


# # ================== THANKS / SMALLTALK FILTER ==================
# SMALLTALK_PHRASES = {
#     "дякую", "дякс", "спасибі", "мерсі", "thanks", "thank you",
#     "ок", "окей", "okay", "ok",
#     "добре", "ясно", "зрозуміло", "супер", "круто", "топ", "клас",
#     "ага", "угу",
#     "добре дякую", "дякую тобі", "дякую вам",
# }
# ONLY_EMOJI_RE = re.compile(r"^[\s\.\,\!\?\-…:;()\[\]{}\"'«»🙂😉😊😀😅😂🤣😍❤️💔👍🙏💛✨🔥💯✅]+$")


# def is_non_query_message(text: str) -> bool:
#     if not text:
#         return True
#     raw = text.strip()
#     t = raw.lower().replace("’", "'").replace("‘", "'").strip()

#     if ONLY_EMOJI_RE.match(raw):
#         return True

#     # if has explicit question sign — not smalltalk
#     if "?" in raw:
#         return False

#     # exact short phrases
#     if t in SMALLTALK_PHRASES:
#         return True

#     # "дякую ..." without any clear intent words → smalltalk
#     starts = ("дякую", "спасибі", "дякс", "ок", "окей", "добре", "ясно", "зрозуміло")
#     if t.startswith(starts):
#         intent_words = ["що", "як", "коли", "чи", "порада", "вибір", "робота", "гроші", "стосун", "переїзд", "розклад"]
#         if any(w in t for w in intent_words):
#             return False
#         return True

#     # very short non-question
#     if len(t) <= 5:
#         return True

#     return False


# def smalltalk_reply(lang: str) -> str:
#     variants_uk = [
#         "❤️ Радий бути поруч. Якщо захочеш — напиши, що зараз найбільше хвилює.",
#         "Завжди будь ласка ❤️ Якщо хочеш — продовжимо: що саме болить/не дає спокою?",
#         "Ок 😊 Я поруч. Скажи, куди копати далі?",
#     ]
#     variants_ru = [
#         "❤️ Рад быть рядом. Если захочешь — напиши, что сейчас больше всего тревожит.",
#         "Всегда пожалуйста ❤️ Если хочешь — продолжим: что именно не дает покоя?",
#         "Ок 😊 Я рядом. Куда копаем дальше?",
#     ]
#     variants_en = [
#         "❤️ I’m here with you. If you want — tell me what’s bothering you most right now.",
#         "Anytime ❤️ If you want, we can continue: what exactly feels heavy?",
#         "Okay 😊 I’m here. Where do we go next?",
#     ]
#     if lang == "ru":
#         return random.choice(variants_ru)
#     if lang == "en":
#         return random.choice(variants_en)
#     return random.choice(variants_uk)


# # ================== FOLLOW-UP (CLARIFY CARDS) ==================
# FOLLOWUP_HINTS = [
#     "поясни детальніше", "детальніше", "уточни", "уточнення", "поясни", "розшифруй",
#     "що означає", "проясни", "можеш глибше", "а якщо", "а що з", "а як щодо",
#     "подивись ще", "дотягни", "дотягни карту", "ще карту", "ще 1 карту", "ще 2 карти",
#     "покажи додатково",
#     # RU
#     "поясни подробнее", "подробнее", "уточни", "уточнение", "расшифруй", "что значит",
#     "проясни", "можешь глубже", "посмотри еще", "дотяни", "еще карту", "еще 1 карту", "еще 2 карты",
#     # EN
#     "more details", "explain more", "clarify", "clarification", "what does it mean", "go deeper", "one more card", "two more cards",
# ]


# def is_followup_request(user_id: int, text: str) -> bool:
#     if user_id not in last_reading:
#         return False
#     t = (text or "").lower()
#     if any(h in t for h in FOLLOWUP_HINTS):
#         return True
#     # very short "why?" after reading
#     if len(t.strip()) <= 12 and any(w in t for w in ["чому", "почему", "why"]):
#         return True
#     return False


# def choose_clarifier_amount(text: str) -> int:
#     t = (text or "").lower()
#     # user explicitly asks 1 or 2
#     if re.search(r"(\b1\b|\bодн|\bone\b).*карт", t) or "one more card" in t:
#         return 1
#     if re.search(r"(\b2\b|\bдв|\btwo\b).*карт", t) or "two more cards" in t:
#         return 2
#     # default: 2 for "детальніше/глибше", else 1
#     if any(x in t for x in ["детальніше", "подробнее", "more details", "глибше", "глубже", "go deeper"]):
#         return 2
#     return 1


# # ================== HELP CALLBACKS ==================
# @dialog_router.callback_query(F.data == "tarot_help_open")
# async def tarot_help_open(callback: types.CallbackQuery):
#     await callback.answer()
#     lang = detect_lang(callback.message.text or "")
#     try:
#         await callback.message.edit_text(build_help_text(lang), reply_markup=help_back_inline_kb(), parse_mode="HTML")
#     except Exception:
#         await callback.message.answer(build_help_text(lang), reply_markup=help_back_inline_kb(), parse_mode="HTML")


# @dialog_router.callback_query(F.data == "tarot_help_back")
# async def tarot_help_back(callback: types.CallbackQuery):
#     await callback.answer()
#     lang = detect_lang(callback.message.text or "")
#     try:
#         await callback.message.edit_text(build_welcome_text(lang), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
#     except Exception:
#         await callback.message.answer(build_welcome_text(lang), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")


# # ================== ENERGY PANEL (inline) ==================
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


# # ================== SPREAD SELECTION (more exact) ==================
# EXPLICIT_AMOUNT_RE = re.compile(r"(?<!\d)(3|4|5|10)(?!\d)")


# def parse_explicit_amount(text: str) -> Optional[int]:
#     t = (text or "").lower()
#     if "кельт" in t or "celtic" in t:
#         return 10
#     m = EXPLICIT_AMOUNT_RE.search(t)
#     if m and re.search(rf"{m.group(1)}\s*(карт|карти|cards|карты|расклад)", t):
#         n = int(m.group(1))
#         if n in (3, 4, 5, 10):
#             return n
#     return None


# def rule_based_amount(text: str) -> Optional[int]:
#     t = (text or "").lower()

#     rel = ["стосун", "відносин", "взаємин", "кохан", "любов", "партнер", "екс", "колишн", "між нами",
#            "отношен", "любов", "партнер", "бывш", "между нами", "он", "она"]
#     work_money = ["робот", "кар'єр", "гроші", "дохід", "борг", "переїзд", "план", "вибір", "рішення",
#                   "работ", "карьер", "деньги", "долг", "переезд", "план", "выбор", "решен",
#                   "job", "career", "money", "debt", "move", "moving", "choice", "decision", "plan"]
#     deep = ["криза", "тупик", "по колу", "детально", "глибок", "безвихід", "все одразу", "роками",
#             "кризис", "тупик", "по кругу", "детально", "глубок", "безвыход", "всё сразу", "годами",
#             "crisis", "stuck", "loop", "deep", "complex", "detailed"]

#     rel_score = sum(1 for w in rel if w in t)
#     wm_score = sum(1 for w in work_money if w in t)
#     deep_score = sum(1 for w in deep if w in t)

#     # strong decision
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
#     future_words = ["коли", "чи буде", "буде", "в майбутньому", "прогноз", "через", "наступ",
#                     "когда", "будет ли", "будет", "прогноз", "через", "следующ",
#                     "when", "will", "future", "forecast", "next"]
#     action_words = ["що робити", "як бути", "як діяти", "вибір", "виріш", "порада", "план", "крок", "чи варто",
#                     "что делать", "как быть", "как поступ", "выбор", "реш", "совет", "план", "шаг", "стоит ли",
#                     "what should i do", "how to", "advice", "plan", "step", "should i"]

#     tl = t.lower()
#     if any(w in tl for w in future_words):
#         return ("Три карти (3): Минуле—Теперішнє—Майбутнє", ["Минуле", "Теперішнє", "Майбутнє"])
#     if any(w in tl for w in action_words):
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

#     # GPT selector as fallback
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
#         data = _extract_json_object(raw)
#         if not data:
#             raise ValueError("No JSON")

#         amount = int(data.get("amount"))
#         if amount not in (3, 4, 5, 10):
#             raise ValueError("Bad amount")

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
#         # safe fallback
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


# def build_cards_payload_ready(spread_name: str, positions: List[str], user_text: str, cards: List[dict], lang: str) -> str:
#     amount = len(cards)
#     pos_lines = "\n".join([f"{i}. {positions[i-1]}" for i in range(1, amount + 1)])
#     cards_lines = "\n".join(
#         f"{i}. {c['ua']} ({c['code']}) {('⬆️' if c['upright'] else '⬇️')} — {'upright' if c['upright'] else 'reversed'}"
#         for i, c in enumerate(cards, start=1)
#     )

#     return (
#         f"LANGUAGE: {lang}\n"
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


# # ================== SINGLE CARD IMAGE (for 1-2 clarifiers) ==================
# def _save_temp_jpg(img: Image.Image) -> str:
#     tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
#     tmp.close()
#     img.convert("RGB").save(tmp.name, "JPEG", quality=92)
#     return tmp.name


# def prepare_single_card_image(path: str, upright: bool) -> str:
#     img = Image.open(path)
#     if not upright:
#         img = img.rotate(180, expand=True)
#     return _save_temp_jpg(img)


# async def send_clarifier_cards(message: types.Message, cards: List[dict], lang: str):
#     # відправляємо 1-2 карти окремо (бо combine_spread_image підтримує 3/4/5/10)
#     for idx, c in enumerate(cards, start=1):
#         tmp = prepare_single_card_image(c["image"], c["upright"])
#         arrow = "⬆️" if c["upright"] else "⬇️"
#         if lang == "ru":
#             cap = f"🃏 Уточняющая карта {idx}: {c['ua']} {arrow}"
#         elif lang == "en":
#             cap = f"🃏 Clarifier card {idx}: {c['ua']} {arrow}"
#         else:
#             cap = f"🃏 Уточнююча карта {idx}: {c['ua']} {arrow}"
#         await message.answer_photo(photo=FSInputFile(tmp), caption=cap)
#         try:
#             os.remove(tmp)
#         except Exception:
#             pass


# # ================== GPT CHAT MANAGER ==================
# async def chat_manager_decide(user_id: int, user_text: str, lang: str) -> Dict[str, Any]:
#     # hard block for thanks/smalltalk
#     if is_non_query_message(user_text):
#         return {"mode": "chat", "reply": smalltalk_reply(lang), "amount": None, "why": "smalltalk"}

#     lr = last_reading.get(user_id)
#     last_info = ""
#     if lr:
#         last_info = (
#             f"LAST_READING_EXISTS: yes\n"
#             f"LAST_SPREAD: {lr.get('spread_name')}\n"
#             f"LAST_USER_QUESTION: {lr.get('question')}\n"
#         )
#     else:
#         last_info = "LAST_READING_EXISTS: no\n"

#     payload = (
#         f"LANGUAGE: {lang}\n"
#         f"{last_info}\n"
#         f"CONTEXT:\n{short_context(user_id)}\n\n"
#         f"USER_MESSAGE:\n{user_text}"
#     )

#     sys_prompt = CHAT_MANAGER_PROMPT + f"\n\nВАЖЛИВО: Відповідай мовою: {lang} (same as user)."

#     try:
#         try:
#             r = await client.chat.completions.create(
#                 model="gpt-4.1-mini",
#                 messages=[
#                     {"role": "system", "content": sys_prompt},
#                     {"role": "user", "content": payload},
#                 ],
#                 max_tokens=280,
#                 temperature=0.8,
#                 response_format={"type": "json_object"},
#             )
#         except TypeError:
#             r = await client.chat.completions.create(
#                 model="gpt-4.1-mini",
#                 messages=[
#                     {"role": "system", "content": sys_prompt},
#                     {"role": "user", "content": payload},
#                 ],
#                 max_tokens=280,
#                 temperature=0.8,
#             )

#         raw = (r.choices[0].message.content or "").strip()
#         data = _extract_json_object(raw) or {}

#         mode = str(data.get("mode", "chat")).strip().lower()
#         if mode not in ("chat", "clarify", "spread"):
#             mode = "chat"

#         reply = str(data.get("reply", "")).strip()
#         if not reply:
#             reply = smalltalk_reply(lang)

#         amount = data.get("amount", None)
#         if amount is not None:
#             try:
#                 amount = int(amount)
#             except Exception:
#                 amount = None
#             if amount not in (3, 4, 5, 10):
#                 amount = None

#         why = str(data.get("why", "")).strip()[:120]
#         return {"mode": mode, "reply": reply, "amount": amount, "why": why or "ok"}

#     except Exception:
#         return {"mode": "chat", "reply": smalltalk_reply(lang), "amount": None, "why": "manager_fallback"}


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


# # ================== START / EXIT ==================
# class TarotChatFSM(StatesGroup):
#     chatting = State()


# @dialog_router.message(F.text == "🔮 Живий Таро-чат")
# async def start_dialog(message: types.Message, state: FSMContext):
#     await state.set_state(TarotChatFSM.chatting)
#     user_id = message.from_user.id
#     chat_histories[user_id] = []

#     lang = detect_lang(message.from_user.language_code or "")  # rough, not critical
#     await message.answer(build_welcome_text(lang), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
#     await message.answer("👇", reply_markup=dialog_kb())


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

#     lang = detect_lang(user_text)

#     # save user message
#     add_chat_message(user_id, "user", user_text)

#     # 0) якщо це “уточни/детальніше” і є попередній розклад → дотягуємо 1-2 карти
#     if is_followup_request(user_id, user_text):
#         current = await get_energy(user_id)
#         if current < ENERGY_COST_PER_READING:
#             await state.clear()
#             kb = build_main_menu(user_id)
#             if lang == "ru":
#                 txt = (
#                     "🔋 <b>Энергия закончилась</b> — чтобы уточнить расклад, нужно пополнить ⚡\n\n"
#                     f"Нужно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
#                     f"У вас: <b>{current}</b> ✨"
#                 )
#             elif lang == "en":
#                 txt = (
#                     "🔋 <b>Not enough energy</b> — to clarify the reading you need to top up ⚡\n\n"
#                     f"Needed: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
#                     f"You have: <b>{current}</b> ✨"
#                 )
#             else:
#                 txt = (
#                     "🔋 <b>Енергія закінчилась</b> — щоб уточнити розклад, потрібно поповнити ⚡\n\n"
#                     f"Потрібно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
#                     f"У вас: <b>{current}</b> ✨"
#                 )
#             await message.answer(txt, parse_mode="HTML", reply_markup=kb)
#             await open_energy_panel_here(message)
#             return

#         # живий перехід
#         if lang == "ru":
#             await message.answer("Ок, уточню 🔎 Дотягиваю 1–2 карты…")
#         elif lang == "en":
#             await message.answer("Okay, let’s clarify 🔎 I’ll pull 1–2 clarifier cards…")
#         else:
#             await message.answer("Ок, уточню 🔎 Дотягую 1–2 карти…")

#         clar_n = choose_clarifier_amount(user_text)
#         clar_cards = draw_cards(clar_n)
#         await send_clarifier_cards(message, clar_cards, lang)

#         lr = last_reading.get(user_id, {})
#         prev_summary = (
#             f"Попередній контекст (НЕ тлумач заново, тільки привʼяжи):\n"
#             f"- Запит: {lr.get('question','')}\n"
#             f"- Розклад: {lr.get('spread_name','')}\n"
#             f"- Короткий підсумок (якщо є): {lr.get('short','')}\n"
#             f"\nНове уточнення користувача: {user_text}"
#         )

#         spread_name = "Уточнення до попереднього розкладу"
#         positions = [f"Уточнення {i}" for i in range(1, clar_n + 1)]
#         payload = build_cards_payload_ready(spread_name, positions, prev_summary, clar_cards, lang)

#         spinner_msg = stop_event = spinner_task = None
#         try:
#             spinner_msg, stop_event, spinner_task = await start_spinner(message)

#             sys_prompt = TAROT_SYSTEM_PROMPT + f"\n\nВАЖЛИВО: відповідай мовою користувача: {lang}."
#             resp = await client.chat.completions.create(
#                 model="gpt-4.1-mini",
#                 messages=[
#                     {"role": "system", "content": sys_prompt},
#                     {"role": "user", "content": payload},
#                 ],
#                 max_tokens=1700,
#                 temperature=0.75,
#             )

#             final_reply = (resp.choices[0].message.content or "").strip()
#             final_reply = strip_bad_phrases(final_reply)

#         except Exception:
#             if spinner_msg and stop_event and spinner_task:
#                 await stop_spinner(spinner_msg, stop_event, spinner_task)
#             await message.answer("⚠️ Не вдалося отримати тлумачення. Спробуй ще раз.")
#             return

#         if spinner_msg and stop_event and spinner_task:
#             await stop_spinner(spinner_msg, stop_event, spinner_task)

#         await change_energy(user_id, -ENERGY_COST_PER_READING)
#         await message.answer(final_reply)
#         add_chat_message(user_id, "assistant", final_reply)
#         return

#     # 1) якщо “дякую/ок/👍” → НЕ робимо розклад, відповідаємо як людина
#     if is_non_query_message(user_text):
#         reply = smalltalk_reply(lang)
#         await message.answer(reply)
#         add_chat_message(user_id, "assistant", reply)
#         return

#     # 2) GPT-менеджер вирішує: chat / clarify / spread
#     decision = await chat_manager_decide(user_id, user_text, lang)

#     # завжди надсилаємо “живу” відповідь
#     await message.answer(decision["reply"])
#     add_chat_message(user_id, "assistant", decision["reply"])

#     if decision["mode"] in ("chat", "clarify"):
#         return

#     # 3) mode == spread → перевірка енергії
#     current = await get_energy(user_id)
#     if current < ENERGY_COST_PER_READING:
#         await state.clear()
#         kb = build_main_menu(user_id)
#         if lang == "ru":
#             txt = (
#                 "🔋 <b>Энергия закончилась</b> — чтобы сделать расклад, нужно пополнить ⚡\n\n"
#                 f"Нужно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
#                 f"У вас: <b>{current}</b> ✨"
#             )
#         elif lang == "en":
#             txt = (
#                 "🔋 <b>Not enough energy</b> — to do a spread you need to top up ⚡\n\n"
#                 f"Needed: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
#                 f"You have: <b>{current}</b> ✨"
#             )
#         else:
#             txt = (
#                 "🔋 <b>Енергія закінчилась</b> — щоб зробити розклад, потрібно поповнити ⚡\n\n"
#                 f"Потрібно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
#                 f"У вас: <b>{current}</b> ✨"
#             )
#         await message.answer(txt, parse_mode="HTML", reply_markup=kb)
#         await open_energy_panel_here(message)
#         return

#     # 4) підбір розкладу (точніше): manager amount -> rule-based -> gpt selector
#     amount = decision.get("amount")
#     if amount not in (3, 4, 5, 10):
#         rb = rule_based_amount(user_text)
#         if rb:
#             amount = rb
#             spread_name, positions = choose_spread_layout(amount, user_text)
#         else:
#             amount, spread_name, positions = await choose_spread_via_gpt(user_text)
#     else:
#         spread_name, positions = choose_spread_layout(int(amount), user_text)
#         amount = int(amount)

#     # 5) тягнемо карти
#     cards = draw_cards(amount)

#     # 6) 1 зображення розкладу
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

#     # 7) GPT тлумачить СТРОГО витягнуті карти
#     payload = build_cards_payload_ready(spread_name, positions, user_text, cards, lang)

#     spinner_msg = stop_event = spinner_task = None
#     try:
#         spinner_msg, stop_event, spinner_task = await start_spinner(message)

#         sys_prompt = TAROT_SYSTEM_PROMPT + f"\n\nВАЖЛИВО: відповідай мовою користувача: {lang}."
#         resp = await client.chat.completions.create(
#             model="gpt-4.1-mini",
#             messages=[
#                 {"role": "system", "content": sys_prompt},
#                 {"role": "user", "content": payload},
#             ],
#             max_tokens=2000,
#             temperature=0.75,
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

#     # 8) списуємо енергію тільки якщо тлумачення успішне
#     await change_energy(user_id, -ENERGY_COST_PER_READING)

#     await message.answer(final_reply)
#     add_chat_message(user_id, "assistant", final_reply)

#     # зберігаємо “останній розклад” для уточнень
#     last_reading[user_id] = {
#         "question": user_text,
#         "spread_name": spread_name,
#         "cards": cards,
#         "short": final_reply[:400],
#     }


# dialog_tarot_chat.py
# ✅ Живий таро-чат: спілкування + розклади
# ✅ "дякую/ок/👍" НЕ запускає розклад
# ✅ "доповни/поглиб/дотягни карту" -> тягне РІВНО 1 карту і дає розширене трактування
# ✅ для 1 карти робиться окрема картинка (фон + карта)
# ✅ мова за замовчуванням: українська

import os
import re
import json
import random
import asyncio
import tempfile
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

DEFAULT_CHAT_MANAGER_PROMPT = r"""
Ти — живий таро-чат. Твоя задача: зрозуміти, що треба зараз:
- просто розмова/підтримка
- зробити розклад (коли питання вже сформоване)
- або поставити ОДНЕ коротке уточнення, якщо дуже розмито

ВАЖЛИВО:
- Якщо користувач просто подякував/ок/👍 — НЕ запускай розклад.
- Не вигадуй, що карти вже витягнуті.
- Пиши українською.

Поверни ТІЛЬКИ JSON:
{
  "mode": "chat" | "clarify" | "spread",
  "reply": "текст відповіді українською",
  "amount": 3|4|5|10|null
}

Підбір amount (коли mode=spread):
- Стосунки/між нами/почуття/він-вона/екс → 4
- Робота/гроші/переїзд/вибір/план → 5
- Криза/по колу/дуже складно/комплексно → 10
- Інакше → 3
"""

TAROT_SYSTEM_PROMPT = getattr(config, "TAROT_SYSTEM_PROMPT", DEFAULT_TAROT_SYSTEM_PROMPT)
SPREAD_SELECTOR_PROMPT = getattr(config, "TAROT_SPREAD_SELECTOR_PROMPT", DEFAULT_SPREAD_SELECTOR_PROMPT)
CHAT_MANAGER_PROMPT = getattr(config, "TAROT_CHAT_MANAGER_PROMPT", DEFAULT_CHAT_MANAGER_PROMPT)

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
        # якщо в цьому є реальний запит — не блокуємо
        intent_words = ["що", "як", "коли", "чи", "порада", "вибір", "робота", "гроші", "стосун", "переїзд", "розклад"]
        if any(w in t for w in intent_words):
            return False
        return True
    if len(t) <= 5:
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
    # коротке "чому?" після розкладу
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
    work_money = ["робот", "кар'єр", "гроші", "дохід", "борг", "переїзд", "план", "вибір", "рішення"]
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

    # 3 cards
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

    # GPT selector fallback
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

    # resize card to fit nicely
    max_w = int(W * 0.42)
    max_h = int(H * 0.78)
    cw, ch = card.size
    scale = min(max_w / cw, max_h / ch)
    card = card.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)

    # shadow
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

    # small label "Уточнення"
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

# ================== GPT CHAT MANAGER ==================
async def manager_decide(user_id: int, user_text: str) -> Dict[str, Any]:
    if is_non_query_message(user_text):
        return {"mode": "chat", "reply": smalltalk_reply(), "amount": None}

    payload = (
        "ТИП: Живий чат\n"
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
                max_tokens=320,
                temperature=0.85,
                response_format={"type": "json_object"},
            )
        except TypeError:
            r = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": CHAT_MANAGER_PROMPT},
                    {"role": "user", "content": payload},
                ],
                max_tokens=320,
                temperature=0.85,
            )

        raw = (r.choices[0].message.content or "").strip()
        data = _extract_json_object(raw) or {}

        mode = str(data.get("mode", "chat")).strip().lower()
        if mode not in ("chat", "clarify", "spread"):
            mode = "chat"

        reply = str(data.get("reply", "")).strip()
        if not reply:
            reply = smalltalk_reply()

        amount = data.get("amount", None)
        if amount is not None:
            try:
                amount = int(amount)
            except Exception:
                amount = None
            if amount not in (3, 4, 5, 10):
                amount = None

        return {"mode": mode, "reply": reply, "amount": amount}

    except Exception:
        return {"mode": "chat", "reply": smalltalk_reply(), "amount": None}

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

    # 1) якщо подяка/ок/емоції — просто відповідаємо (НЕ розклад)
    if is_non_query_message(user_text):
        reply = smalltalk_reply()
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

        # картинка для 1 карти (фон + карта)
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
                temperature=0.78,
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

        # оновлюємо last_reading (додаємо уточнення до short)
        last_reading[user_id] = {
            "question": lr.get("question", ""),
            "spread_name": lr.get("spread_name", ""),
            "cards": lr.get("cards", []),
            "short": (lr.get("short", "") + "\n\n[Уточнення]\n" + final_reply)[:900],
        }
        return

    # 3) звичайний чат-менеджер: chat/clarify/spread
    decision = await manager_decide(user_id, user_text)
    await message.answer(decision["reply"])
    add_chat_message(user_id, "assistant", decision["reply"])

    if decision["mode"] in ("chat", "clarify"):
        return

    # 4) spread -> перевірка енергії
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

    # 5) підбір розкладу (точніше): manager amount -> rules -> gpt selector
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

    # 6) тягнемо карти
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

    # 7) GPT тлумачення (строго по витягнутих картах)
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
            temperature=0.78,
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

    # зберігаємо останній розклад для уточнення 1 картою
    last_reading[user_id] = {
        "question": user_text,
        "spread_name": spread_name,
        "cards": cards,
        "short": final_reply[:450],
    }
