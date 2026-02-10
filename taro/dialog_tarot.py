import os
import re
import json
import random
import asyncio
import tempfile
import time
import logging
from io import BytesIO
from typing import List, Dict, Tuple, Optional, Any

from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    BufferedInputFile,
)

from openai import AsyncOpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config
from cards_data import TAROT_CARDS
from modules.menu import build_main_menu
from modules.user_stats_db import get_energy, change_energy
from modules.tarot_spread_image import combine_spread_image  # ✅ 3/4/5/10

# ======================
# LOGGING
# ======================
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

# ======================
# ROUTER + OPENAI
# ======================
dialog_router = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

# ======================
# SETTINGS
# ======================
ENERGY_COST_PER_READING = 2  # списується тільки за розклад / уточнення (1 карта)
BACKGROUND_PATH = "background.png"
BACKGROUND_PATH10 = "bg.png"
EXIT_TEXT = "⬅️ Завершити бесіду"
WELCOME_IMAGE = "assets/1.png"
# Clarify throttling (щоб бот рідко уточнював і частіше робив розклади)
CLARIFY_COOLDOWN_SECONDS = 15 * 60  # не частіше ніж раз на 15 хв
CLARIFY_MIN_TEXT_LEN = 18  # якщо дуже коротко і без теми — тоді можна уточнити

# Cleanup / memory hygiene
SESSION_TTL_SECONDS = 6 * 60 * 60  # 6 годин без активності -> чистимо дані юзера
CLEANUP_PROBABILITY = 0.06  # ~6% шанс запуску чистки на повідомлення (дешево)

# OpenAI timeouts/retries
OPENAI_TIMEOUT_SEC = 30
OPENAI_RETRIES = 2  # 1 + 2 ретраї = 3 спроби
OPENAI_BACKOFF_BASE = 1.3

# ======================
# OPENAI EXCEPTIONS (safe import)
# ======================
try:
    from openai import RateLimitError, APIConnectionError, APITimeoutError, APIError  # type: ignore
except Exception:  # pragma: no cover
    RateLimitError = APIConnectionError = APITimeoutError = APIError = Exception  # type: ignore

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
""",
)

TAROT_SYSTEM_PROMPT = getattr(
    config, "TAROT_SYSTEM_PROMPT", DEFAULT_TAROT_SYSTEM_PROMPT
)
SPREAD_SELECTOR_PROMPT = getattr(
    config, "TAROT_SPREAD_SELECTOR_PROMPT", DEFAULT_SPREAD_SELECTOR_PROMPT
)
CHAT_MANAGER_PROMPT = getattr(
    config, "TAROT_CHAT_MANAGER_PROMPT", DEFAULT_CHAT_MANAGER_PROMPT
)
HUMAN_CHAT_PROMPT = getattr(
    config, "TAROT_HUMAN_CHAT_PROMPT", DEFAULT_HUMAN_CHAT_PROMPT
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
    return ReplyKeyboardMarkup(
        resize_keyboard=True, keyboard=[[KeyboardButton(text=EXIT_TEXT)]]
    )


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


def build_welcome_text() -> str:
    return (
        "✨ <b>Вітаю в Живому Таро-чаті!</b>\n\n"
        "Я — твій особистий таролог-наставник 🔮\n\n"
        "💬 Пиши як у звичайному чаті — а я зроблю розклад і дам детальне поснення для твоєї ситуації ❤️\n"

    )


def build_help_text() -> str:
    return (
        "ℹ️ <b>Як користуватись Живим Таро-чатом</b>\n\n"
        "<b>🗣 Спілкування:</b>\n"
        "• Пиши природно, як другу\n"
        "• Розкажи про ситуацію або поділись тим, що турбує\n"
        "• Можеш просто поспілкуватись — я підтримаю\n\n"
        "<b>🔮 Розклади:</b>\n"
        "Коли потрібна ясність, я автоматично зроблю розклад:\n"
        "• <b>3 карти</b> — швидка відповідь на питання\n"
        "• <b>4 карти</b> — стосунки, почуття ❤️\n"
        "• <b>5 карт</b> — робота, гроші, вибір 💼💰\n"
        "• <b>10 карт</b> — глибокий аналіз складної ситуації 🌟\n\n"
        "• <b>💡 Ви можете обрати самостійно бажаний тип розкладу, просто вкажіть кількість карт у вашому питанні 💡</b>\n\n"


        "<b>🃏 Уточнення:</b>\n"
        "Після розкладу можеш попросити:\n"
        "«Доповни розклад» / «Дотягни карту» / «Поясни детальніше»\n\n"
        f"⚡ <b>Вартість:</b> {ENERGY_COST_PER_READING} енергії за розклад або уточнення"
    )


# ================== SESSION STATE (in-memory) ==================
# ⚠️ Для продакшна краще Redis/DB, але зараз тримаємо в пам’яті + TTL-cleanup
chat_histories: Dict[int, List[Dict[str, str]]] = {}
last_reading: Dict[int, Dict[str, Any]] = {}

# clarify timestamps — monotonic
last_clarify_ts: Dict[int, float] = {}
user_last_seen: Dict[int, float] = {}

# per-user lock (проти подвійних паралельних обробок)
_user_locks: Dict[int, asyncio.Lock] = {}


def _get_user_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


def _touch_user(user_id: int):
    user_last_seen[user_id] = time.monotonic()


def _maybe_cleanup_sessions():
    # запускаємо рідко, щоб не гальмувати
    if random.random() > CLEANUP_PROBABILITY:
        return
    now = time.monotonic()
    stale = [
        uid for uid, ts in user_last_seen.items() if (now - ts) > SESSION_TTL_SECONDS
    ]
    for uid in stale:
        user_last_seen.pop(uid, None)
        chat_histories.pop(uid, None)
        last_reading.pop(uid, None)
        last_clarify_ts.pop(uid, None)
        _user_locks.pop(uid, None)


def get_chat_history(user_id: int) -> List[Dict[str, str]]:
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    return chat_histories[user_id]


def add_chat_message(user_id: int, role: str, content: str):
    h = get_chat_history(user_id)
    h.append({"role": role, "content": content})
    # тримаємо компактно
    if len(h) > 24:
        chat_histories[user_id] = h[-24:]


def short_context(user_id: int) -> str:
    h = get_chat_history(user_id)[-10:]
    lines = []
    for m in h:
        role = "Користувач" if m["role"] == "user" else "Бот"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines).strip()


# ================== TEXT INTENT HELPERS ==================
SMALLTALK_SET = {
    "дякую",
    "дякс",
    "спасибі",
    "мерсі",
    "ок",
    "окей",
    "добре",
    "ясно",
    "зрозуміло",
    "супер",
    "круто",
    "клас",
    "топ",
    "ага",
    "угу",
    "👍",
    "❤️",
    "🙏",
    "✅",
}
ONLY_EMOJI_RE = re.compile(
    r"^[\s\.\,\!\?\-…:;()\[\]{}\"'«»🙂😉😊😀😅😂🤣😍❤️💔👍🙏💛✨🔥💯✅]+$"
)

SHORT_BUT_VALID_TOPICS = {
    "гроші",
    "робота",
    "любов",
    "екс",
    "вибір",
    "переїзд",
    "стосунки",
    "здоров'я",
    "здоров’я",
}

VAGUE_WORDS = {
    "підкажи",
    "порада",
    "розклад",
    "скажеш",
    "допоможи",
    "поясни",
    "підкажіть",
}

SMALLTALK_Q_PHRASES = [
    "як ти",
    "як справи",
    "що нового",
    "ти тут",
    "ти де",
    "хто ти",
    "чим займаєшся",
    "що робиш",
    "як день",
    "як настрій",
]

FOLLOWUP_TRIGGERS = [
    "доповни",
    "поглиб",
    "уточни",
    "детальніше",
    "поясни детальніше",
    "дотягни",
    "дотягни карту",
    "додай карту",
    "ще карту",
    "ще одну карту",
    "уточнення",
    "проясни",
    "розшир",
    "розширене трактування",
    "розшифруй",
]
FOLLOWUP_RE = re.compile(
    r"(доповн|поглиб|уточн|детальніш|проясн|дотягн|додай|ще\s+карт|ще\s+одн|розшир|розшифруй)",
    re.IGNORECASE,
)

EXPLICIT_AMOUNT_RE = re.compile(r"(?<!\d)(3|4|5|10)(?!\d)")


def normalize_text(text: str) -> str:
    return (text or "").strip().lower().replace("’", "'").replace("‘", "'")


def is_smalltalk_question(text: str) -> bool:
    t = normalize_text(text)
    return any(p in t for p in SMALLTALK_Q_PHRASES)


def has_topic_markers(text: str) -> bool:
    t = normalize_text(text)
    if rule_based_amount(t) is not None:
        return True
    markers = [
        "він",
        "вона",
        "ми",
        "партнер",
        "чоловік",
        "дружина",
        "колишн",
        "екс",
        "робот",
        "грош",
        "борг",
        "дохід",
        "кар'єр",
        "карʼєр",
        "переїзд",
        "місто",
        "країна",
        "вибір",
        "рішення",
        "варто",
        "коли",
        "чи буде",
        "що робити",
        "як бути",
    ]
    return any(m in t for m in markers)


def parse_explicit_amount(text: str) -> Optional[int]:
    t = normalize_text(text)
    if "кельт" in t:
        return 10
    m = EXPLICIT_AMOUNT_RE.search(t)
    if m and re.search(rf"{m.group(1)}\s*(карт|карти|розклад)", t):
        n = int(m.group(1))
        if n in (3, 4, 5, 10):
            return n
    return None


def rule_based_amount(text: str) -> Optional[int]:
    t = normalize_text(text)

    rel = [
        "стосун",
        "відносин",
        "взаємин",
        "кохан",
        "любов",
        "партнер",
        "екс",
        "колишн",
        "між нами",
    ]
    work_money = [
        "робот",
        "кар'єр",
        "карʼєр",
        "гроші",
        "дохід",
        "борг",
        "переїзд",
        "план",
        "вибір",
        "рішення",
    ]
    deep = [
        "криза",
        "тупик",
        "по колу",
        "детально",
        "глибок",
        "безвихід",
        "все одразу",
        "роками",
    ]

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


def is_non_query_message(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return True

    t = normalize_text(raw)

    # pure emoji / punctuation => non-query
    if ONLY_EMOJI_RE.match(raw):
        return True

    # if question mark and not smalltalk -> likely query
    if "?" in raw and not is_smalltalk_question(raw):
        return False

    # exact smalltalk tokens
    if t in SMALLTALK_SET:
        return True

    # very short: treat as non-query, but allow “topic-words”
    if len(t) <= 7:
        if t in SHORT_BUT_VALID_TOPICS:
            return False
        if rule_based_amount(t) is not None:
            return False
        return True

    # if explicitly mentions tarot/spread/cards -> query
    if any(w in t for w in ["розклад", "таро", "карти", "карту", "прогноз"]):
        return False

    # if has topic markers -> query
    if has_topic_markers(t):
        return False

    # otherwise: likely just chat
    return False


def wants_spread_now(text: str) -> bool:
    t = normalize_text(text)
    if not t:
        return False

    if any(
        w in t
        for w in [
            "розклад",
            "таро",
            "карти",
            "карту",
            "прогноз",
            "подивись",
            "поглянь",
            "витягни",
        ]
    ):
        return True

    if parse_explicit_amount(t) is not None:
        return True

    if has_topic_markers(t):
        return True

    if "?" in t and not is_smalltalk_question(t):
        return True

    return False


def is_followup_request(user_id: int, text: str) -> bool:
    if user_id not in last_reading:
        return False
    t = normalize_text(text)
    if not t:
        return False
    if FOLLOWUP_RE.search(t):
        return True
    if any(x in t for x in FOLLOWUP_TRIGGERS):
        return True
    if len(t) <= 12 and "чому" in t:
        return True
    return False


def is_too_vague_for_spread(user_id: int, text: str) -> bool:
    t = normalize_text(text)
    if not t:
        return True

    # якщо вже є контекст — ми майже завжди робимо розклад без уточнень
    if get_chat_history(user_id):
        if len(t) < CLARIFY_MIN_TEXT_LEN and t in VAGUE_WORDS:
            return True
        return False

    # перше повідомлення
    if has_topic_markers(t):
        return False
    if len(t) >= CLARIFY_MIN_TEXT_LEN:
        return False
    if len(t) < CLARIFY_MIN_TEXT_LEN and (t in VAGUE_WORDS or len(t.split()) <= 2):
        return True

    return False


def can_clarify_now(user_id: int) -> bool:
    now = time.monotonic()
    last = last_clarify_ts.get(user_id, 0.0)
    return (now - last) >= CLARIFY_COOLDOWN_SECONDS


def mark_clarified(user_id: int):
    last_clarify_ts[user_id] = time.monotonic()


def smalltalk_reply() -> str:
    variants = [
        "❤️ Я поруч. Якщо захочеш — напиши, що саме зараз найбільше хвилює.",
        "Добре 😊 Розкажи, що хочеш прояснити або що не дає спокою.",
        "Ок ✨ Якщо треба — можемо глибше розібрати ситуацію.",
    ]
    return random.choice(variants)


# ================== OPENAI HELPERS ==================
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


async def _openai_create_with_retry(
    *,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    want_json: bool = False,
    timeout: int = OPENAI_TIMEOUT_SEC,
    retries: int = OPENAI_RETRIES,
) -> Any:
    last_err: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            kwargs = dict(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # json_object only if supported by current client version
            if want_json:
                try:
                    kwargs["response_format"] = {"type": "json_object"}
                except Exception:
                    pass

            coro = client.chat.completions.create(**kwargs)
            return await asyncio.wait_for(coro, timeout=timeout)

        except (
            asyncio.TimeoutError,
            RateLimitError,
            APIConnectionError,
            APITimeoutError,
            APIError,
        ) as e:
            last_err = e if isinstance(e, Exception) else Exception(str(e))
            if attempt >= retries:
                break
            sleep_s = (OPENAI_BACKOFF_BASE**attempt) + random.random() * 0.35
            await asyncio.sleep(sleep_s)

        except Exception as e:
            # нетипова помилка — не ретраїмо бездумно
            last_err = e
            break

    raise last_err or RuntimeError("OpenAI request failed")


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


async def generate_human_chat_reply(
    user_id: int, user_text: str, hint: str = ""
) -> str:
    payload = (
        f"Короткий контекст (останні повідомлення):\n{short_context(user_id)}\n\n"
        f"Повідомлення користувача:\n{user_text}\n"
    )
    if hint:
        payload += f"\nНотатка:\n{hint}\n"

    try:
        resp = await _openai_create_with_retry(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": HUMAN_CHAT_PROMPT},
                {"role": "user", "content": payload},
            ],
            max_tokens=420,
            temperature=0.95,
            want_json=False,
        )
        text = (resp.choices[0].message.content or "").strip()
        text = _limit_questions(text, max_q=1)
        return text or smalltalk_reply()
    except Exception:
        logger.exception("human_chat_reply failed")
        return smalltalk_reply()


async def manager_decide(user_id: int, user_text: str) -> Dict[str, Any]:
    # Менеджер викликаємо лише коли реально треба (сумнівні кейси).
    payload = (
        "ТИП: Диспетчер\n"
        "Мова: українська\n\n"
        f"Короткий контекст:\n{short_context(user_id)}\n\n"
        f"Повідомлення користувача:\n{user_text}"
    )

    try:
        r = await _openai_create_with_retry(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": CHAT_MANAGER_PROMPT},
                {"role": "user", "content": payload},
            ],
            max_tokens=260,
            temperature=0.35,
            want_json=True,
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

        reply = str(data.get("reply", "")).strip()
        reply = _limit_questions(reply, max_q=1)

        return {"mode": mode, "reply": reply, "amount": amount}
    except Exception:
        logger.exception("manager_decide failed")
        return {"mode": "chat", "reply": "", "amount": None}


# ================== SPREAD SELECTION ==================
def choose_spread_layout(amount: int, user_text: str) -> Tuple[str, List[str]]:
    t = normalize_text(user_text)

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

    future_words = [
        "коли",
        "чи буде",
        "буде",
        "в майбутньому",
        "прогноз",
        "через",
        "наступ",
    ]
    action_words = [
        "що робити",
        "як бути",
        "як діяти",
        "вибір",
        "виріш",
        "порада",
        "план",
        "крок",
        "чи варто",
    ]

    if any(w in t for w in future_words):
        return (
            "Три карти (3): Минуле—Теперішнє—Майбутнє",
            ["Минуле", "Теперішнє", "Майбутнє"],
        )
    if any(w in t for w in action_words):
        return (
            "Три карти (3): Допомагає—Заважає—Порада",
            ["Що допомагає", "Що заважає", "Порада / як діяти"],
        )
    return (
        "Три карти (3): Суть—Виклик—Порада",
        ["Суть ситуації", "Ключовий виклик", "Порада / напрям"],
    )


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
        r = await _openai_create_with_retry(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SPREAD_SELECTOR_PROMPT},
                {"role": "user", "content": user_text},
            ],
            max_tokens=260,
            temperature=0.15,
            want_json=True,
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
        logger.exception("choose_spread_via_gpt failed")
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


def build_cards_payload_ready(
    spread_name: str, positions: List[str], user_text: str, cards: List[dict]
) -> str:
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


# ================== OUTPUT SANITIZER ==================
# Робимо м’яко: прибираємо тільки типові “службові” фрази, не з’їдаючи зміст.
BAD_LINE_PATTERNS = [
    re.compile(r"^\s*дякую\s+за\s+запит\b", re.IGNORECASE),
    re.compile(r"^\s*thanks\s+for\s+your\s+question\b", re.IGNORECASE),
    re.compile(r"\bколи\s+будеш\s+готов", re.IGNORECASE),
    re.compile(r"\bчекаю\s+на\b", re.IGNORECASE),
    re.compile(r"\bскажи\s+когда\b", re.IGNORECASE),
]


def strip_bad_phrases(text: str) -> str:
    if not text:
        return ""
    cleaned: List[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        low = s.lower()
        # прибираємо лише явні службові рядки
        if any(p.search(low) for p in BAD_LINE_PATTERNS):
            continue
        cleaned.append(ln)
    return "\n".join(cleaned).strip()


# ================== IMAGE RENDER (CACHED, BYTES) ==================
_BG_CACHE: Dict[str, Image.Image] = {}
_FONT_CACHE: Dict[int, ImageFont.ImageFont] = {}


def _safe_bg_cached(path: str) -> Image.Image:
    # кешуємо фон, але повертаємо .copy() щоб не “псувати” кеш при малюванні
    if path and os.path.exists(path):
        if path not in _BG_CACHE:
            _BG_CACHE[path] = Image.open(path).convert("RGBA")
        return _BG_CACHE[path].copy()
    # fallback
    return Image.new("RGBA", (1200, 800), (20, 20, 20, 255))


def _load_font_cached(size: int) -> ImageFont.ImageFont:
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        try:
            font = ImageFont.truetype(p, size)
            _FONT_CACHE[size] = font
            return font
        except Exception:
            continue
    font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


def make_single_card_on_background_bytes(
    card_path: str,
    upright: bool,
    background_path: str = BACKGROUND_PATH,
    label_text: str = "Уточнення",
) -> bytes:
    bg = _safe_bg_cached(background_path)
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
    font = _load_font_cached(28)

    bbox = draw.textbbox((0, 0), label_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 16, 10
    rw, rh = tw + px * 2, th + py * 2
    lx, ly = x + 18, y + 18
    draw.rounded_rectangle((lx, ly, lx + rw, ly + rh), radius=14, fill=(0, 0, 0, 150))
    draw.text((lx + px, ly + py), label_text, font=font, fill=(255, 255, 255, 255))
    bg.alpha_composite(overlay)

    buf = BytesIO()
    bg.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _safe_remove(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ================== SPINNER (optimized) ==================
SPINNER_FRAMES = [
    "🔮 Дивлюсь уважно твої карти",
    "🔮 Роблю аналіз",
    "🔮 ретельно перевіряю",
    "🔮 Готую відповідь",
]
SPINNER_ANIM_PATH = "thinking.mp4"


class SpinnerHandle:
    def __init__(
        self,
        anim_msg: types.Message,
        text_msg: types.Message,
        stop_event: asyncio.Event,
        task: asyncio.Task,
    ):
        self.anim_msg = anim_msg
        self.text_msg = text_msg
        self.stop_event = stop_event
        self.task = task

    async def stop(self):
        """Зупинка спінера та видалення повідомлень"""
        # 1. Зупиняємо анімацію тексту
        self.stop_event.set()

        # 2. Чекаємо завершення таску
        try:
            await asyncio.wait_for(self.task, timeout=3.5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        # 3. Затримка для стабільності
        await asyncio.sleep(0.3)

        # 4. Видаляємо текстове повідомлення (з retry)
        deleted_text = await self._safe_delete(self.text_msg, "text", retries=3)

        # 5. Затримка перед видаленням анімації
        if deleted_text:
            await asyncio.sleep(0.4)

        # 6. Видаляємо анімацію (з retry)
        await self._safe_delete(self.anim_msg, "animation", retries=3)

    async def _safe_delete(
        self, msg: types.Message, msg_type: str, retries: int = 3
    ) -> bool:
        """
        Безпечне видалення повідомлення з retry та exponential backoff

        Returns:
            True якщо видалення успішне, False якщо ні
        """
        for attempt in range(retries):
            try:
                await msg.delete()
                logger.debug(
                    f"Successfully deleted {msg_type} message (attempt {attempt + 1})"
                )
                return True

            except Exception as e:
                error_msg = str(e).lower()

                # Якщо повідомлення вже видалене - це успіх
                if (
                    "message to delete not found" in error_msg
                    or "message can't be deleted" in error_msg
                ):
                    logger.debug(f"{msg_type} message already deleted")
                    return True

                # Якщо остання спроба - логуємо помилку
                if attempt >= retries - 1:
                    logger.warning(
                        f"Failed to delete {msg_type} message after {retries} attempts: {e}"
                    )
                    return False

                # Exponential backoff
                wait_time = 0.3 * (2**attempt)
                await asyncio.sleep(wait_time)

        return False


async def _run_spinner(
    text_msg: types.Message, stop: asyncio.Event, interval: float = 1.0
):
    """Анімація текстового спінера"""
    i = 0
    last_text = None
    last_typing_ts = 0.0

    while not stop.is_set():
        text = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
        i += 1

        # Оновлюємо текст тільки якщо він змінився
        if text != last_text:
            try:
                await text_msg.edit_text(text)
                last_text = text
            except Exception as e:
                # Якщо повідомлення видалене - виходимо
                if "message to edit not found" in str(e).lower():
                    break

        # Періодично показуємо typing
        now = time.monotonic()
        if now - last_typing_ts >= 4.0:
            last_typing_ts = now
            try:
                await text_msg.bot.send_chat_action(text_msg.chat.id, "typing")
            except Exception:
                pass

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue


async def start_spinner(message: types.Message) -> SpinnerHandle:
    """
    Запуск спінера з анімацією та текстом

    Returns:
        SpinnerHandle для управління спінером
    """
    # 1. Відправляємо анімацію
    try:
        anim = FSInputFile(SPINNER_ANIM_PATH)
        anim_msg = await message.answer_animation(anim)
    except Exception as e:
        logger.warning(f"Failed to send animation: {e}")
        # Fallback - просто текстове повідомлення
        anim_msg = await message.answer("🔮")

    # 2. Відправляємо текстовий спінер
    text_msg = await message.answer(SPINNER_FRAMES[0])

    # 3. Запускаємо анімацію тексту
    stop_event = asyncio.Event()
    task = asyncio.create_task(_run_spinner(text_msg, stop_event, interval=1.0))

    return SpinnerHandle(
        anim_msg=anim_msg, text_msg=text_msg, stop_event=stop_event, task=task
    )


# ================== ENERGY PANEL ==================
def energy_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💛 Написати касиру", callback_data="energy_topup"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Запросити друзів", callback_data="energy_invite"
                )
            ],
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


async def reserve_energy(user_id: int, cost: int) -> bool:
    # Завдяки per-user lock це стає достатньо безпечним для поточного MVP.
    current = await get_energy(user_id)
    if current < cost:
        return False
    await change_energy(user_id, -cost)
    return True


async def refund_energy(user_id: int, cost: int):
    try:
        await change_energy(user_id, cost)
    except Exception:
        pass


# ================== FSM ==================
class TarotChatFSM(StatesGroup):
    chatting = State()


# ================== HELP CALLBACKS ==================
@dialog_router.callback_query(F.data == "tarot_help_open")
async def tarot_help_open(callback: types.CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_text(
            build_help_text(), reply_markup=help_back_inline_kb(), parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            build_help_text(), reply_markup=help_back_inline_kb(), parse_mode="HTML"
        )


@dialog_router.callback_query(F.data == "tarot_help_back")
async def tarot_help_back(callback: types.CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_text(
            build_welcome_text(),
            reply_markup=help_welcome_inline_kb(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            build_welcome_text(),
            reply_markup=help_welcome_inline_kb(),
            parse_mode="HTML",
        )


# ================== START / EXIT ==================
# @dialog_router.message(F.text == "🔮 Живий Таро-чат")
# async def start_dialog(message: types.Message, state: FSMContext):
#     await state.set_state(TarotChatFSM.chatting)
#     user_id = message.from_user.id
#     _touch_user(user_id)
#     chat_histories[user_id] = []
#     await message.answer(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
#     await message.answer("👇 Напиши, що хвилює", reply_markup=dialog_kb())
@dialog_router.message(F.text == "🔮 Живий Таро-чат")

async def start_dialog(message: types.Message, state: FSMContext):
    await state.set_state(TarotChatFSM.chatting)
    user_id = message.from_user.id
    _touch_user(user_id)
    chat_histories[user_id] = []

    # Відправляємо привітання з фото
    try:
        await message.answer_photo(
            photo=FSInputFile(WELCOME_IMAGE),
            caption=build_welcome_text(),
            reply_markup=help_welcome_inline_kb(),
            parse_mode="HTML",
        )
    except FileNotFoundError:
        # Fallback без фото
        await message.answer(
            build_welcome_text(),
            reply_markup=help_welcome_inline_kb(),
            parse_mode="HTML",
        )

    # Клавіатура для виходу
    await message.answer(
        "👇 Напиши, що хвилює, і я допоможу розібратись", reply_markup=dialog_kb()
    )


@dialog_router.message(F.text == EXIT_TEXT)
async def exit_dialog(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    _touch_user(user_id)
    try:
        await message.delete()
    except Exception:
        pass
    kb = build_main_menu(user_id)
    await message.bot.send_message(
        message.chat.id, "🔙 Повертаю в головне меню.", reply_markup=kb
    )
    await state.clear()


# ================== MAIN FLOW DECISION ==================
async def decide_flow(user_id: int, user_text: str) -> Dict[str, Any]:
    """
    Єдиний центр рішення (ідея: clarify — дуже рідко).
    Повертає: {"mode": "chat|clarify|spread", "reply": str, "amount": Optional[int]}
    """
    # 1) очевидний non-query -> chat
    if is_non_query_message(user_text):
        return {"mode": "chat", "reply": "", "amount": None}

    # 2) якщо явно просять розклад -> spread (без уточнень)
    if wants_spread_now(user_text) and not is_smalltalk_question(user_text):
        return {"mode": "spread", "reply": "", "amount": rule_based_amount(user_text)}

    # 3) якщо це smalltalk питання -> chat
    if is_smalltalk_question(user_text):
        return {"mode": "chat", "reply": "", "amount": None}

    # 4) якщо дуже туманно і це перший контакт — allow clarify (але тільки якщо cooldown дозволяє)
    if is_too_vague_for_spread(user_id, user_text) and can_clarify_now(user_id):
        # спробуємо manager для формулювання 1 короткого уточнення
        mgr = await manager_decide(user_id, user_text)
        if mgr.get("mode") == "clarify":
            return {"mode": "clarify", "reply": mgr.get("reply") or "", "amount": None}
        # якщо manager не clarify — все одно уточнимо коротко
        return {
            "mode": "clarify",
            "reply": "Щоб не робити розклад “в нікуди”, уточни одну річ: про яку сферу йдеться — стосунки, гроші/робота чи інше?",
            "amount": None,
        }

    # 5) неочевидні кейси — manager, але clarify гейтимо
    mgr = await manager_decide(user_id, user_text)
    mode = mgr.get("mode", "chat")
    amount = mgr.get("amount", None)

    if mode == "clarify":
        # clarify дозволяємо тільки якщо реально туманно + cooldown
        if is_too_vague_for_spread(user_id, user_text) and can_clarify_now(user_id):
            return {"mode": "clarify", "reply": mgr.get("reply") or "", "amount": None}
        # інакше форсимо spread
        return {
            "mode": "spread",
            "reply": "Зрозумів(ла). Не тягну час — зроблю розклад по тому, що ти написав(ла) 🔮",
            "amount": amount,
        }

    if mode == "spread":
        return {"mode": "spread", "reply": mgr.get("reply") or "", "amount": amount}

    # default chat
    return {"mode": "chat", "reply": mgr.get("reply") or "", "amount": None}


# ================== MAIN CHAT HANDLER ==================
@dialog_router.message(TarotChatFSM.chatting)
async def chat(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = (message.text or "").strip()
    if not user_text:
        return

    _touch_user(user_id)
    _maybe_cleanup_sessions()

    lock = _get_user_lock(user_id)
    async with lock:
        add_chat_message(user_id, "user", user_text)

        # FOLLOW-UP: рівно 1 уточнююча карта
        if is_followup_request(user_id, user_text):
            # енергію резервуємо одразу
            ok = await reserve_energy(user_id, ENERGY_COST_PER_READING)
            if not ok:
                await state.clear()
                kb = build_main_menu(user_id)
                current = await get_energy(user_id)
                await message.answer(
                    "🔋 <b>Енергія закінчилась</b> — щоб доповнити розклад, потрібно поповнити ⚡\n\n"
                    f"Потрібно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
                    f"У вас: <b>{current}</b> ✨",
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                await open_energy_panel_here(message)
                return

            spinner: Optional[SpinnerHandle] = None
            try:
                await message.answer(
                    "Добре 🔎 Дотягую 1 уточнюючу карту і розширюю трактування…"
                )

                clar_card = draw_cards(1)[0]
                arrow = "⬆️" if clar_card["upright"] else "⬇️"

                # картинка в пам’яті (без tmp)
                img_bytes = make_single_card_on_background_bytes(
                    clar_card["image"],
                    clar_card["upright"],
                    BACKGROUND_PATH,
                    label_text="Уточнення",
                )
                await message.answer_photo(
                    photo=BufferedInputFile(img_bytes, filename="clarify.png"),
                    caption=f"🃏 Уточнююча карта: {clar_card['ua']} {arrow}",
                )

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

                spinner = await start_spinner(message)

                resp = await _openai_create_with_retry(
                    model="gpt-4.1-mini",
                    messages=[
                        {"role": "system", "content": CLARIFIER_PROMPT},
                        {"role": "user", "content": payload},
                    ],
                    max_tokens=1600,
                    temperature=0.82,
                    want_json=False,
                )
                final_reply = (resp.choices[0].message.content or "").strip()
                final_reply = strip_bad_phrases(final_reply)

                await message.answer(final_reply)
                add_chat_message(user_id, "assistant", final_reply)

                last_reading[user_id] = {
                    "question": lr.get("question", ""),
                    "spread_name": lr.get("spread_name", ""),
                    "cards": lr.get("cards", []),
                    "short": (lr.get("short", "") + "\n\n[Уточнення]\n" + final_reply)[
                        :900
                    ],
                }
                return

            except Exception:
                logger.exception("followup clarifier failed")
                await refund_energy(user_id, ENERGY_COST_PER_READING)
                await message.answer(
                    "⚠️ Не вдалося доповнити трактування. Спробуй ще раз."
                )
                return
            finally:
                if spinner:
                    await spinner.stop()

        # Рішення: chat/clarify/spread
        decision = await decide_flow(user_id, user_text)

        # CHAT режим — як людина
        if decision["mode"] == "chat":
            hint = "Режим CHAT. Будь живим співрозмовником. Без розкладу. Максимум 1 питання."
            if decision.get("reply"):
                # якщо менеджер дав короткий “людський” підхват — додамо
                base = decision["reply"].strip()
                base = _limit_questions(base, max_q=1)
                await message.answer(base)
                add_chat_message(user_id, "assistant", base)
                return

            reply = await generate_human_chat_reply(user_id, user_text, hint=hint)
            await message.answer(reply)
            add_chat_message(user_id, "assistant", reply)
            return

        # CLARIFY режим — 1 коротке уточнення + cooldown
        if decision["mode"] == "clarify":
            reply = (
                decision.get("reply")
                or "Уточни, будь ласка, одну річ: що саме ти хочеш прояснити в цій ситуації?"
            )
            reply = _limit_questions(reply, max_q=1)
            await message.answer(reply)
            add_chat_message(user_id, "assistant", reply)
            mark_clarified(user_id)
            return

        # SPREAD: якщо менеджер дав короткий підхват — покажемо 1 речення
        if decision.get("reply"):
            warm = decision["reply"].strip()
            warm = strip_bad_phrases(warm)
            warm = _limit_questions(warm, max_q=1)
            if warm:
                await message.answer(warm)
                add_chat_message(user_id, "assistant", warm)

        # Резервуємо енергію одразу (щоб не було “зробив роботу — а енергії вже нема”)
        ok = await reserve_energy(user_id, ENERGY_COST_PER_READING)
        if not ok:
            await state.clear()
            kb = build_main_menu(user_id)
            current = await get_energy(user_id)
            await message.answer(
                "🔋 <b>Енергія закінчилась</b> — щоб зробити розклад, потрібно поповнити ⚡\n\n"
                f"Потрібно: <b>{ENERGY_COST_PER_READING}</b> ✨\n"
                f"У вас: <b>{current}</b> ✨",
                parse_mode="HTML",
                reply_markup=kb,
            )
            await open_energy_panel_here(message)
            return

        spinner = None
        final_img_path = ""
        try:
            # підбір розкладу: decision amount -> rules -> gpt selector
            amount = decision.get("amount")
            if amount not in (3, 4, 5, 10):
                rb = rule_based_amount(user_text)
                if rb:
                    amount = rb
                    spread_name, positions = choose_spread_layout(amount, user_text)
                else:
                    amount, spread_name, positions = await choose_spread_via_gpt(
                        user_text
                    )
            else:
                amount = int(amount)
                spread_name, positions = choose_spread_layout(amount, user_text)

            # тягнемо карти
            cards = draw_cards(amount)

            await message.answer(f"🃏 Роблю розклад: {spread_name}")
            await asyncio.sleep(0.12)

            img_paths = [c["image"] for c in cards]
            uprights = [c["upright"] for c in cards]

            # combine_spread_image повертає PATH (модуль зовнішній) — читаємо bytes і чистимо
            final_img_path = combine_spread_image(
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

            img_bytes = _read_file_bytes(final_img_path)
            await message.answer_photo(
                photo=BufferedInputFile(img_bytes, filename=f"spread_{amount}.png"),
                caption=caption,
                parse_mode="HTML",
            )

            # GPT тлумачення (строго по витягнутих картах)
            payload = build_cards_payload_ready(
                spread_name, positions, user_text, cards
            )

            spinner = await start_spinner(message)

            resp = await _openai_create_with_retry(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": TAROT_SYSTEM_PROMPT},
                    {"role": "user", "content": payload},
                ],
                max_tokens=2000,
                temperature=0.82,
                want_json=False,
            )
            final_reply = (resp.choices[0].message.content or "").strip()
            final_reply = strip_bad_phrases(final_reply)

            await message.answer(final_reply)
            add_chat_message(user_id, "assistant", final_reply)

            last_reading[user_id] = {
                "question": user_text,
                "spread_name": spread_name,
                "cards": cards,
                "short": final_reply[:450],
            }
            return

        except Exception:
            logger.exception("spread flow failed")
            await refund_energy(user_id, ENERGY_COST_PER_READING)
            await message.answer(
                "⚠️ Не вдалося зробити розклад/тлумачення. Спробуй ще раз."
            )
            return

        finally:
            if spinner:
                await spinner.stop()
            _safe_remove(final_img_path)
