
import os
import re
import json
import random
import asyncio
import time
import logging
import tempfile
from pathlib import Path
from io import BytesIO
from typing import List, Dict, Tuple, Optional, Any
from contextlib import asynccontextmanager

from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
    BufferedInputFile,
)

from openai import AsyncOpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config
from cards_data import TAROT_CARDS
from modules.menu import build_main_menu
from modules.user_stats_db import get_energy, change_energy
from modules.tarot_spread_image import combine_spread_image
from modules.energy_panel import build_no_energy_kb

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
client = AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)

# ======================
# PATHS + SETTINGS
# ======================
BASE_DIR = Path(__file__).parent.resolve()

# ENERGY_COST_PER_READING = 2
# BACKGROUND_PATH = "background.png"
# BACKGROUND_PATH10 =  "bg.png"
# EXIT_TEXT = "⬅️ Завершити бесіду"
# WELCOME_IMAGE =   "assets" / "1.png"
SPINNER_ANIM_PATH = "thinking.mp4"

ENERGY_COST_PER_READING = 2
BACKGROUND_PATH = "background.png"
BACKGROUND_PATH10 = "bg.png"
EXIT_TEXT = "⬅️ Завершити бесіду"
WELCOME_IMAGE = "assets/1.png"

# Rate-limit: 1 повідомлення кожні 1.8 секунди на користувача
RATE_LIMIT_SECONDS = 1.8

CLARIFY_COOLDOWN_SECONDS = 15 * 60
CLARIFY_MIN_TEXT_LEN = 18

# TODO: Replace in-memory session state with Redis for multi-instance / restart safety.
# All dicts below are process-local and reset on restart.
SESSION_TTL_SECONDS = 6 * 60 * 60
CLEANUP_PROBABILITY = 0.06

OPENAI_TIMEOUT_SEC = 45
OPENAI_RETRIES = 2

# ======================
# PROMPTS
# ======================
DEFAULT_TAROT_SYSTEM_PROMPT = """
Ти — професійний таролог-наставник. Тон живий, теплий, але може бути прямим і жорстким,
якщо карти реально на це вказують (без приниження, без залякувань).

ГОЛОВНЕ:
- Ти НЕ вигадуєш карти. Тлумачиш ТІЛЬКИ ті, що в блоці "Витягнуті карти".
- Ти НЕ пишеш "дякую за запит", НЕ просиш карти, НЕ кажеш що "чекаєш".
- Без HTML і без markdown. Тільки PLAIN TEXT.

ФОРМАТ ДЛЯ ОСНОВНОГО РОЗКЛАДУ:
🎯 Фокус запиту: 1 коротке речення.
🔮 Розклад: <назва>
🧩 По позиціях:
1) <позиція> — <карта> (⬆️/⬇️): 2–4 речення
...
✨ Зв'язки між картами: 3–6 речень
🧭 Висновок: 2–4 речення
✅ Практична порада:
- 3 конкретні кроки

ПСИХОЛОГІЧНА БЕЗПЕКА:
- "важкі" карти — як сигнал/тема уваги ⚠️, без фаталізму
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

TAROT_SYSTEM_PROMPT = getattr(config, "TAROT_SYSTEM_PROMPT", DEFAULT_TAROT_SYSTEM_PROMPT)
SPREAD_SELECTOR_PROMPT = getattr(config, "TAROT_SPREAD_SELECTOR_PROMPT", DEFAULT_SPREAD_SELECTOR_PROMPT)
CHAT_MANAGER_PROMPT = getattr(config, "TAROT_CHAT_MANAGER_PROMPT", DEFAULT_CHAT_MANAGER_PROMPT)
HUMAN_CHAT_PROMPT = getattr(config, "TAROT_HUMAN_CHAT_PROMPT", DEFAULT_HUMAN_CHAT_PROMPT)

# ================== UI ==================
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


def build_welcome_text() -> str:
    return "✨ <b>Вітаю в Живому Таро-чаті!</b>\n\nЯ — твій особистий таролог-наставник 🔮\n\n"


def build_help_text() -> str:
    return (
        "ℹ️ <b>Як користуватись Живим Таро-чатом</b>\n\n"
        "<b>🗣 Спілкування:</b>\n"
        "• Пиши природно, як другу\n"
        "• Розкажи про ситуацію або поділись тим, що турбує\n"
        "• Можеш просто поспілкуватись — я підтримаю\n\n"
        "<b>🔮 Розклади:</b>\n"
        "• <b>3 карти</b> — швидка відповідь (основний)\n"
        "• <b>4 карти</b> — стосунки, почуття\n"
        "• <b>5 карт</b> — робота, гроші, вибір\n"
        "• <b>10 карт</b> — глибокий аналіз\n\n"
        f"⚡ <b>Вартість:</b> {ENERGY_COST_PER_READING} енергії за розклад або уточнення"
    )


# ================== SESSION STATE ==================
# TODO: Replace with Redis for persistence across restarts and horizontal scaling.
# Example swap: use aioredis with get/set/expire and JSON serialization.
chat_histories: Dict[int, List[Dict[str, str]]] = {}
last_reading: Dict[int, Dict[str, Any]] = {}
last_clarify_ts: Dict[int, float] = {}
user_last_seen: Dict[int, float] = {}
last_significant_question: Dict[int, str] = {}
_user_locks: Dict[int, asyncio.Lock] = {}
_last_message_ts: Dict[int, float] = {}


def _get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


def _touch_user(user_id: int):
    user_last_seen[user_id] = time.monotonic()


def _maybe_cleanup_sessions():
    if random.random() > CLEANUP_PROBABILITY:
        return
    now = time.monotonic()
    stale = [uid for uid, ts in user_last_seen.items() if (now - ts) > SESSION_TTL_SECONDS]
    for uid in stale:
        user_last_seen.pop(uid, None)
        chat_histories.pop(uid, None)
        last_reading.pop(uid, None)
        last_clarify_ts.pop(uid, None)
        last_significant_question.pop(uid, None)
        _user_locks.pop(uid, None)
        _last_message_ts.pop(uid, None)  # FIX: очищаємо rate-limit dict теж


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
    lines = [f"{'Користувач' if m['role'] == 'user' else 'Бот'}: {m['content']}" for m in h]
    return "\n".join(lines).strip()


# ================== RATE LIMIT ==================
def is_rate_limited(user_id: int) -> bool:
    now = time.monotonic()
    last = _last_message_ts.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        logger.debug("Rate limited user %s (%.2fs since last)", user_id, now - last)
        return True
    _last_message_ts[user_id] = now
    return False


# ================== TEXT INTENT HELPERS ==================
SMALLTALK_SET = {
    "дякую", "дякс", "спасибі", "мерсі", "ок", "окей", "добре", "ясно", "зрозуміло",
    "супер", "круто", "клас", "топ", "ага", "угу", "👍", "❤️", "🙏", "✅",
}
ONLY_EMOJI_RE = re.compile(
    r"^[\s\.\,\!\?\-…:;()\[\]{}\"'«»🙂😉😊😀😅😂🤣😍❤️💔👍🙏💛✨🔥💯✅\U0001F000-\U0001FFFF]+$"
)

SHORT_BUT_VALID_TOPICS = {"гроші", "робота", "любов", "екс", "вибір", "переїзд", "стосунки", "здоров'я"}
VAGUE_WORDS = {"підкажи", "порада", "розклад", "скажеш", "допоможи", "поясни", "підкажіть"}
SMALLTALK_Q_PHRASES = ["як ти", "як справи", "що нового", "ти тут", "ти де", "хто ти", "чим займаєшся", "що робиш", "як день", "як настрій"]
FOLLOWUP_TRIGGERS = ["доповни", "поглиб", "уточни", "детальніше", "поясни детальніше", "дотягни", "дотягни карту", "додай карту", "ще карту", "ще одну карту", "уточнення", "проясни", "розшир", "розширене трактування", "розшифруй"]
FOLLOWUP_RE = re.compile(r"(доповн|поглиб|уточн|детальніш|проясн|дотягн|додай|ще\s+карт|ще\s+одн|розшир|розшифруй)", re.IGNORECASE)
EXPLICIT_AMOUNT_RE = re.compile(r"(?<!\d)(3|4|5|10)(?!\d)")


def normalize_text(text: str) -> str:
    return (text or "").strip().lower().replace("\u2019", "'").replace("\u2018", "'")


def is_smalltalk_question(text: str) -> bool:
    t = normalize_text(text)
    return any(p in t for p in SMALLTALK_Q_PHRASES)


def is_likely_question(text: str) -> bool:
    if not text:
        return False
    t = normalize_text(text)
    starters = ["що", "коли", "як", "чи", "де", "хто", "чому", "наскільки", "скільки", "який", "яка", "яке", "які"]
    if any(t.startswith(s + " ") or f" {s} " in " " + t for s in starters):
        return True
    if "?" in text:
        return True
    predict = ["завтра", "сьогодні", "цього тижня", "наступн", "чекає", "буде", "як пройде", "що принесе", "яка енергія", "що на мене", "як буде"]
    return any(w in t for w in predict)


def has_topic_markers(text: str) -> bool:
    t = normalize_text(text)
    if rule_based_amount(t) is not None:
        return True
    markers = ["він", "вона", "ми", "партнер", "чоловік", "дружина", "колишн", "екс", "робот", "грош", "борг", "дохід", "кар'єр", "карʼєр", "переїзд", "місто", "країна", "вибір", "рішення", "варто", "коли", "чи буде", "що робити", "як бути"]
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
    deep = ["криза", "тупик", "по колу", "детально", "глибок", "безвихід", "все одразу", "роками", "комплексно", "складно", "важко"]
    if any(w in t for w in deep):
        return 10
    work_money = ["робот", "кар'єр", "карʼєр", "кар'єра", "гроші", "дохід", "борг", "переїзд", "план", "вибір", "рішення", "праця", "співбесід", "зарплат", "бізнес"]
    if any(w in t for w in work_money):
        return 5
    rel = ["стосун", "відносин", "взаємин", "кохан", "любов", "партнер", "екс", "колишн", "між нами", "він мене", "вона мене"]
    if any(w in t for w in rel):
        return 4
    return None


def is_non_query_message(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return True
    t = normalize_text(raw)
    if ONLY_EMOJI_RE.match(raw):
        return True
    if "?" in raw and not is_smalltalk_question(raw):
        return False
    if t in SMALLTALK_SET:
        return True
    if len(t) <= 7:
        if t in SHORT_BUT_VALID_TOPICS or rule_based_amount(t) is not None:
            return False
        return True
    if any(w in t for w in ["розклад", "таро", "карти", "карту", "прогноз"]):
        return False
    if has_topic_markers(t):
        return False
    return True


def wants_spread_now(text: str) -> bool:
    t = normalize_text(text)
    if not t:
        return False
    if any(w in t for w in ["розклад", "таро", "карти", "витягни", "прогноз", "подивись", "поглянь"]):
        return True
    if parse_explicit_amount(t) is not None:
        return True
    if has_topic_markers(t):
        return True
    if is_likely_question(text) and not is_smalltalk_question(text):
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
    m = re.search(r"\{.*\}", raw, re.S | re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


async def _openai_create_with_retry(
    *,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    want_json: bool = False,
    user_id: int = 0,
) -> Any:
    last_err = None
    for attempt in range(OPENAI_RETRIES + 1):
        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if want_json:
                kwargs["response_format"] = {"type": "json_object"}

            async with asyncio.timeout(OPENAI_TIMEOUT_SEC):
                return await client.chat.completions.create(**kwargs)

        except asyncio.TimeoutError as e:
            last_err = e
            logger.warning("OpenAI timeout on attempt %s/%s", attempt + 1, OPENAI_RETRIES + 1,
                           extra={"user_id": user_id})
            # FIX: retry таймаутів теж повинен мати backoff, щоб не бити відразу
            if attempt < OPENAI_RETRIES:
                await asyncio.sleep((1.4 ** attempt) + random.random() * 0.4)

        except Exception as e:
            last_err = e
            if attempt >= OPENAI_RETRIES:
                break
            await asyncio.sleep((1.4 ** attempt) + random.random() * 0.4)

    logger.error("OpenAI failed after %s attempts", OPENAI_RETRIES + 1, extra={"user_id": user_id})
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


async def generate_human_chat_reply(user_id: int, user_text: str, hint: str = "") -> str:
    payload = f"Короткий контекст (останні повідомлення):\n{short_context(user_id)}\n\nПовідомлення користувача:\n{user_text}\n"
    if hint:
        payload += f"\nНотатка:\n{hint}\n"
    try:
        resp = await _openai_create_with_retry(
            model=config.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": HUMAN_CHAT_PROMPT},
                {"role": "user", "content": payload},
            ],
            temperature=0.95,
            user_id=user_id,
        )
        text = (resp.choices[0].message.content or "").strip()
        text = _limit_questions(text, max_q=1)
        return text or smalltalk_reply()
    except Exception:
        logger.exception("human_chat_reply failed", extra={"user_id": user_id})
        return smalltalk_reply()


async def manager_decide(user_id: int, user_text: str) -> Dict[str, Any]:
    payload = f"ТИП: Диспетчер\nМова: українська\n\nКороткий контекст:\n{short_context(user_id)}\n\nПовідомлення користувача:\n{user_text}"
    try:
        r = await _openai_create_with_retry(
            model=config.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": CHAT_MANAGER_PROMPT},
                {"role": "user", "content": payload},
            ],
            temperature=0.35,
            want_json=True,
            user_id=user_id,
        )
        raw = (r.choices[0].message.content or "").strip()
        data = _extract_json_object(raw) or {}

        mode = str(data.get("mode", "chat")).strip().lower()
        if mode not in ("chat", "clarify", "spread"):
            mode = "chat"

        amount = data.get("amount")
        if amount is not None:
            try:
                amount = int(amount)
                if amount not in (3, 4, 5, 10):
                    amount = None
            except Exception:
                amount = None

        reply = str(data.get("reply", "")).strip()
        reply = _limit_questions(reply, max_q=1)

        return {"mode": mode, "reply": reply, "amount": amount}
    except Exception:
        logger.exception("manager_decide failed", extra={"user_id": user_id})
        return {"mode": "chat", "reply": "", "amount": None}


# ================== SPREAD SELECTION ==================
def choose_spread_layout(amount: int, user_text: str) -> Tuple[str, List[str]]:
    t = normalize_text(user_text)
    if amount == 10:
        return "Кельтський хрест (10)", [
            "Поточна ситуація", "Головний виклик / що перехрещує", "Корінь / глибинна причина",
            "Минуле, що вплинуло", "Тенденція / що над ситуацією", "Найближче майбутнє",
            "Ти / твоє ставлення", "Зовнішні впливи / обставини", "Надії та побоювання",
            "Підсумок / результат",
        ]
    if amount == 4:
        return "Стосунки (4)", [
            "Як виглядає зв'язок загалом", "Почуття/намір між вами",
            "Що напружує / що заважає", "Куди це рухається (вектор)",
        ]
    if amount == 5:
        return "Поглиблений розклад ситуації (5)", [
            "Поточна ситуація", "Ресурс / що допомагає",
            "Виклик / що заважає", "Приховане / те, чого не видно",
            "Ймовірний напрямок / результат",
        ]
    future_words = ["коли", "чи буде", "буде", "в майбутньому", "прогноз", "через", "наступ"]
    action_words = ["що робити", "як бути", "як діяти", "вибір", "виріш", "порада", "план", "крок", "чи варто"]
    if any(w in t for w in future_words):
        return "Три карти (3): Минуле—Теперішнє—Майбутнє", ["Минуле", "Теперішнє", "Майбутнє"]
    if any(w in t for w in action_words):
        return "Три карти (3): Допомагає—Заважає—Порада", ["Що допомагає", "Що заважає", "Порада / як діяти"]
    return "Три карти (3): Суть—Виклик—Порада", ["Суть ситуації", "Ключовий виклик", "Порада / напрям"]


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
            model=config.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SPREAD_SELECTOR_PROMPT},
                {"role": "user", "content": user_text},
            ],
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


def build_cards_payload_ready(spread_name: str, positions: List[str], user_text: str, cards: List[dict]) -> str:
    amount = len(cards)
    pos_lines = "\n".join([f"{i}. {positions[i - 1]}" for i in range(1, amount + 1)])
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
        if any(p.search(low) for p in BAD_LINE_PATTERNS):
            continue
        cleaned.append(ln)
    return "\n".join(cleaned).strip()


# ================== IMAGE RENDERING ==================
# NOTE: _BG_CACHE is process-local. With multiple background variants it stays small.
_BG_CACHE: Dict[str, Image.Image] = {}
_FONT_CACHE: Dict[int, ImageFont.ImageFont] = {}


def _safe_bg_cached(path: str) -> Image.Image:
    if path and os.path.exists(path):
        if path not in _BG_CACHE:
            _BG_CACHE[path] = Image.open(path).convert("RGBA")
        return _BG_CACHE[path].copy()
    return Image.new("RGBA", (1200, 800), (20, 20, 20, 255))


def _load_font_cached(size: int) -> ImageFont.ImageFont:
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"]
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


# ================== SPINNER ==================
SPINNER_FRAMES = [
    "🔮 Дивлюсь уважно твої карти",
    "🔮 Роблю аналіз",
    "🔮 ретельно перевіряю",
    "🔮 Готую відповідь",
]


class SpinnerHandle:
    def __init__(self, anim_msg: types.Message, text_msg: types.Message,
                 stop_event: asyncio.Event, task: asyncio.Task):
        self.anim_msg = anim_msg
        self.text_msg = text_msg
        self.stop_event = stop_event
        self.task = task

    async def stop(self):
        self.stop_event.set()
        try:
            await asyncio.wait_for(self.task, timeout=3.5)
        except Exception:
            pass
        await asyncio.sleep(0.3)
        await self._safe_delete(self.text_msg)
        await asyncio.sleep(0.4)
        await self._safe_delete(self.anim_msg)

    async def _safe_delete(self, msg: types.Message):
        for attempt in range(3):
            try:
                await msg.delete()
                return
            except Exception as e:
                error = str(e).lower()
                if "message to delete not found" in error or "message can't be deleted" in error:
                    return
                await asyncio.sleep(0.3 * (2 ** attempt))


async def _run_spinner(text_msg: types.Message, stop: asyncio.Event, interval: float = 1.0):
    i = 0
    last_text = None
    last_typing_ts = 0.0
    while not stop.is_set():
        text = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
        i += 1
        if text != last_text:
            try:
                await text_msg.edit_text(text)
                last_text = text
            except Exception as e:
                if "message to edit not found" in str(e).lower():
                    break
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
    try:
        anim_msg = await message.answer_animation(FSInputFile(SPINNER_ANIM_PATH))
    except Exception:
        anim_msg = await message.answer("🔮")
    text_msg = await message.answer(SPINNER_FRAMES[0])
    stop_event = asyncio.Event()
    task = asyncio.create_task(_run_spinner(text_msg, stop_event, interval=1.0))
    return SpinnerHandle(anim_msg=anim_msg, text_msg=text_msg, stop_event=stop_event, task=task)


# ================== TELEGRAM SEND HELPERS ==================
async def _send_photo_with_retry(
    message: types.Message,
    photo_data: bytes,
    filename: str,
    caption: str = "",
    parse_mode: Optional[str] = None,
    retries: int = 3,
) -> types.Message:
    """Відправляє фото з retry при мережевих помилках Telegram."""
    last_err = None
    for attempt in range(retries):
        try:
            kwargs: Dict[str, Any] = {
                "photo": BufferedInputFile(photo_data, filename=filename),
            }
            if caption:
                kwargs["caption"] = caption
            if parse_mode:
                kwargs["parse_mode"] = parse_mode
            return await message.answer_photo(**kwargs)
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            # Не ретраємо якщо помилка не мережева (наприклад, невалідний файл)
            if "clientoserror" not in err_str and "networkerror" not in err_str and "timeout" not in err_str:
                raise
            logger.warning("Telegram sendPhoto failed attempt %s/%s: %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise last_err or RuntimeError("Failed to send photo")


# ================== ENERGY ==================
@asynccontextmanager
async def reserve_energy_context(user_id: int, cost: int):
    current = await get_energy(user_id)
    if current < cost:
        raise RuntimeError("Not enough energy")
    await change_energy(user_id, -cost)
    try:
        yield
    except Exception:
        await change_energy(user_id, cost)
        raise


# ================== DECIDE_FLOW ==================
async def decide_flow(user_id: int, user_text: str) -> Dict[str, Any]:
    t = normalize_text(user_text)
    original_text = (user_text or "").strip()

    explicit = parse_explicit_amount(user_text)
    if explicit:
        return {"mode": "spread", "reply": "", "amount": explicit}

    if any(w in t for w in ["розклад", "карти", "витягни", "зроби розклад", "прогноз"]):
        amount = rule_based_amount(user_text) or 3
        return {"mode": "spread", "reply": "", "amount": amount}

    if (
        (is_likely_question(original_text) or has_topic_markers(original_text))
        and len(original_text) > 8
        and not is_smalltalk_question(original_text)
    ):
        amount = rule_based_amount(user_text) or 3
        return {"mode": "spread", "reply": "Зрозумів, роблю розклад 🔮", "amount": amount}

    return await manager_decide(user_id, user_text)


# ================== FSM ==================
class TarotChatFSM(StatesGroup):
    chatting = State()


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


# ================== START / EXIT ==================
@dialog_router.message(F.text == "🔮 Живий Таро-чат")
async def start_dialog(message: types.Message, state: FSMContext):
    await state.set_state(TarotChatFSM.chatting)
    user_id = message.from_user.id
    _touch_user(user_id)
    chat_histories[user_id] = []
    # FIX: читаємо файл одразу в байти перед відправкою.
    # FSInputFile читає файл ЛІНИВО під час HTTP-запиту всередині aiohttp —
    # тому FileNotFoundError виникає глибоко в стеку і перетворюється на
    # ClientOSError / TelegramNetworkError, який звичайний except FileNotFoundError не ловить.
    welcome_path = Path(WELCOME_IMAGE)
    if welcome_path.exists():
        try:
            img_bytes = welcome_path.read_bytes()
            await message.answer_photo(
                photo=BufferedInputFile(img_bytes, filename="welcome.png"),
                caption=build_welcome_text(),
                reply_markup=help_welcome_inline_kb(),
                parse_mode="HTML",
            )
        except Exception:
            logger.warning("Failed to send welcome image, falling back to text", exc_info=True)
            await message.answer(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
    else:
        logger.warning("Welcome image not found: %s", WELCOME_IMAGE)
        await message.answer(build_welcome_text(), reply_markup=help_welcome_inline_kb(), parse_mode="HTML")
    await message.answer("👇 Напиши, що хвилює, і я допоможу розібратись", reply_markup=dialog_kb())


@dialog_router.message(F.text == EXIT_TEXT)
async def exit_dialog(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    _touch_user(user_id)
    try:
        await message.delete()
    except Exception:
        pass
    kb = build_main_menu(user_id)
    await message.bot.send_message(message.chat.id, "🔙 Повертаю в головне меню.", reply_markup=kb)
    await state.clear()


# ================== MAIN CHAT HANDLER ==================
@dialog_router.message(TarotChatFSM.chatting)
async def chat(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = (message.text or "").strip()
    if not user_text:
        return

    if is_rate_limited(user_id):
        return

    _touch_user(user_id)
    _maybe_cleanup_sessions()

    lock = _get_user_lock(user_id)
    async with lock:
        add_chat_message(user_id, "user", user_text)

        if (
            (is_likely_question(user_text) or has_topic_markers(user_text) or "про " in normalize_text(user_text))
            and len(user_text) > 8
        ):
            last_significant_question[user_id] = user_text

        # ── FOLLOW-UP ────────────────────────────────────────────────────────────
        if is_followup_request(user_id, user_text):
            spinner: Optional[SpinnerHandle] = None
            try:
                async with reserve_energy_context(user_id, ENERGY_COST_PER_READING):
                    await message.answer("Добре 🔎 Дотягую 1 уточнюючу карту...")

                    clar_card = draw_cards(1)[0]
                    arrow = "⬆️" if clar_card["upright"] else "⬇️"

                    img_bytes = make_single_card_on_background_bytes(
                        clar_card["image"], clar_card["upright"], BACKGROUND_PATH, "Уточнення"
                    )
                    await _send_photo_with_retry(
                        message, img_bytes, "clarify.png",
                        caption=f"🃏 Уточнююча карта: {clar_card['ua']} {arrow}",
                    )

                    lr = last_reading.get(user_id, {})
                    prev_summary = (
                        f"Попередній розклад: {lr.get('spread_name', '')}\n"
                        f"Попередній запит: {lr.get('question', '')}\n"
                        f"Короткий підсумок: {lr.get('short', '')}\n\n"
                        f"Уточнення від користувача: {user_text}"
                    )
                    payload = (
                        f"ПОПЕРЕДНІЙ КОНТЕКСТ:\n{prev_summary}\n\n"
                        f"Витягнута карта:\n1. {clar_card['ua']} ({clar_card['code']}) {arrow}"
                    )

                    spinner = await start_spinner(message)

                    resp = await _openai_create_with_retry(
                        model=config.DEEPSEEK_MODEL,
                        messages=[
                            {"role": "system", "content": CLARIFIER_PROMPT},
                            {"role": "user", "content": payload},
                        ],
                        temperature=0.82,
                        user_id=user_id,
                    )
                    final_reply = strip_bad_phrases((resp.choices[0].message.content or "").strip())

                    await spinner.stop()
                    spinner = None

                    await message.answer(final_reply)
                    add_chat_message(user_id, "assistant", final_reply)

                    last_reading[user_id] = {
                        "question": lr.get("question", ""),
                        "spread_name": lr.get("spread_name", ""),
                        "cards": lr.get("cards", []),
                        "short": (lr.get("short", "") + "\n\n[Уточнення]\n" + final_reply)[:900],
                    }
                    return

            except RuntimeError:
                # FIX: не викликаємо state.clear() — користувач ще в чаті,
                # просто без енергії. Клавіатура виходу залишається доступною.
                await message.answer(
                    "🔋 <b>Енергія закінчилась</b> — поповни, щоб продовжити 🔮",
                    parse_mode="HTML",
                    reply_markup=build_no_energy_kb(),
                )
                return
            except Exception:
                logger.exception("Follow-up failed", extra={"user_id": user_id})
                await message.answer("⚠️ Щось пішло не так. Спробуй ще раз.")
                return
            finally:
                if spinner is not None:
                    await spinner.stop()

        # ── DECISION ─────────────────────────────────────────────────────────────
        decision = await decide_flow(user_id, user_text)

        if decision["mode"] == "chat":
            if decision.get("reply"):
                await message.answer(decision["reply"])
                add_chat_message(user_id, "assistant", decision["reply"])
                return
            reply = await generate_human_chat_reply(user_id, user_text)
            await message.answer(reply)
            add_chat_message(user_id, "assistant", reply)
            return

        if decision["mode"] == "clarify":
            reply = decision.get("reply") or "Уточни, будь ласка, одну річ..."
            await message.answer(reply)
            add_chat_message(user_id, "assistant", reply)
            mark_clarified(user_id)
            return

        # ── SPREAD ───────────────────────────────────────────────────────────────
        spinner: Optional[SpinnerHandle] = None
        # FIX: використовуємо tempfile для гарантованого cleanup навіть при краші
        tmp_file: Optional[tempfile.NamedTemporaryFile] = None
        final_img_path: Optional[str] = None

        try:
            async with reserve_energy_context(user_id, ENERGY_COST_PER_READING):
                if decision.get("reply"):
                    warm = strip_bad_phrases(decision["reply"])
                    if warm:
                        await message.answer(warm)
                        add_chat_message(user_id, "assistant", warm)

                effective_question = user_text

                amount = decision.get("amount")
                if amount not in (3, 4, 5, 10):
                    amount = rule_based_amount(effective_question) or 3

                spread_name, positions = choose_spread_layout(amount, effective_question)
                cards = draw_cards(amount)

                await message.answer(f"🃏 Роблю розклад: {spread_name}")

                img_paths = [c["image"] for c in cards]
                uprights = [c["upright"] for c in cards]

                final_img_path = combine_spread_image(
                    img_paths, uprights, amount, BACKGROUND_PATH, BACKGROUND_PATH10
                )

                lines = [f"{i}. {c['ua']} {'⬆️' if c['upright'] else '⬇️'}" for i, c in enumerate(cards, 1)]

                # FIX: використовуємо with open() для гарантованого закриття файлу
                with open(final_img_path, "rb") as f:
                    img_data = f.read()

                await _send_photo_with_retry(
                    message, img_data, f"spread_{amount}.png",
                    caption="🃏 <b>Витягнуті карти:</b>\n" + "\n".join(lines),
                    parse_mode="HTML",
                )

                payload = build_cards_payload_ready(spread_name, positions, effective_question, cards)

                spinner = await start_spinner(message)

                resp = await _openai_create_with_retry(
                    model=config.DEEPSEEK_MODEL,
                    messages=[
                        {"role": "system", "content": TAROT_SYSTEM_PROMPT},
                        {"role": "user", "content": payload},
                    ],
                    temperature=0.82,
                    user_id=user_id,
                )
                final_reply = strip_bad_phrases((resp.choices[0].message.content or "").strip())

                await spinner.stop()
                spinner = None

                await message.answer(final_reply)
                add_chat_message(user_id, "assistant", final_reply)

                last_reading[user_id] = {
                    "question": effective_question,
                    "spread_name": spread_name,
                    "cards": cards,
                    "short": final_reply[:450],
                }

        except RuntimeError:
            # FIX: так само — не чистимо state, користувач залишається в чаті
            await message.answer(
                "🔋 <b>Енергія закінчилась</b> — поповни, щоб зробити розклад 🔮",
                parse_mode="HTML",
                reply_markup=build_no_energy_kb(),
            )
            return
        except Exception:
            logger.exception("Spread failed", extra={"user_id": user_id})
            await message.answer("⚠️ Не вдалося зробити розклад. Спробуй ще раз.")
            return
        finally:
            if spinner is not None:
                await spinner.stop()
            if final_img_path and os.path.exists(final_img_path):
                try:
                    os.remove(final_img_path)
                except Exception:
                    pass


logger.info("✅ Tarot dialog module loaded")
