import logging
import random
import secrets
import time
from dataclasses import dataclass, field
from io import BytesIO

from aiogram import F, Router, types
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from openai import AsyncOpenAI
from PIL import Image

import config
from cards_data import TAROT_CARDS
from modules.telegram_text import answer_long_text, clean_generated_text


logger = logging.getLogger(__name__)
spread_extension_router = Router()
_CONTEXT_TTL_SECONDS = 24 * 60 * 60
_MAX_CONTEXTS = 1000


@dataclass
class SpreadExtensionContext:
    user_id: int
    question: str
    spread_name: str
    original_interpretation: str
    excluded_cards: set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.monotonic)
    used: bool = False


_contexts: dict[str, SpreadExtensionContext] = {}
_client = AsyncOpenAI(
    api_key=config.DEEPSEEK_API_KEY,
    base_url=config.DEEPSEEK_BASE_URL,
)


def _cleanup_contexts() -> None:
    now = time.monotonic()
    expired = [
        token
        for token, context in _contexts.items()
        if now - context.created_at > _CONTEXT_TTL_SECONDS
    ]
    for token in expired:
        _contexts.pop(token, None)

    if len(_contexts) > _MAX_CONTEXTS:
        oldest = sorted(_contexts, key=lambda token: _contexts[token].created_at)
        for token in oldest[: len(_contexts) - _MAX_CONTEXTS]:
            _contexts.pop(token, None)


def _extension_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Доповнити розклад · 1 карта",
                    callback_data=f"spread_extend:{token}",
                )
            ]
        ]
    )


async def offer_spread_extension(
    message: types.Message,
    *,
    question: str,
    spread_name: str,
    original_interpretation: str,
    excluded_cards: list[str] | set[str] | None = None,
) -> types.Message:
    """Додає під готовим розкладом одноразову кнопку уточнення."""
    _cleanup_contexts()
    token = secrets.token_urlsafe(6)
    _contexts[token] = SpreadExtensionContext(
        user_id=message.from_user.id,
        question=(question or "").strip(),
        spread_name=(spread_name or "Розклад").strip(),
        original_interpretation=(original_interpretation or "").strip(),
        excluded_cards={card for card in (excluded_cards or []) if card},
    )
    return await message.answer(
        "✨ Розклад готовий. Його можна доповнити ще однією картою:",
        reply_markup=_extension_keyboard(token),
    )


def _draw_extra_card(excluded_cards: set[str]) -> tuple[str, dict, bool]:
    available = [name for name in TAROT_CARDS if name not in excluded_cards]
    if not available:
        available = list(TAROT_CARDS)
    name = random.choice(available)
    return name, TAROT_CARDS[name], random.choice([True, False])


def _card_photo(card_info: dict, upright: bool) -> BufferedInputFile:
    with Image.open(card_info["image"]) as source:
        image = source.convert("RGB")
        if not upright:
            image = image.rotate(180)
        output = BytesIO()
        image.save(output, format="JPEG", quality=92)
    return BufferedInputFile(output.getvalue(), filename="extra_tarot_card.jpg")


async def _interpret_extension(
    context: SpreadExtensionContext,
    card_name: str,
    card_info: dict,
    upright: bool,
) -> str:
    direction = "пряма" if upright else "перевернута"
    meaning_key = "meaning_upright" if upright else "meaning_reversed"
    meaning = card_info.get(meaning_key, "")
    prompt = f"""
Запит користувача: {context.question[:1000]}
Розклад: {context.spread_name}

Попереднє тлумачення:
{context.original_interpretation[:3000]}

Додаткова карта: {card_info['ua_name']} ({card_name}), {direction}
Базове значення: {meaning}

Поясни лише новий нюанс цієї карти та як вона доповнює попередній розклад.
Не повторюй увесь розклад і не вигадуй інших карт.
"""
    system_prompt = """
Ти — досвідчений таролог-наставник. Відповідай мовою запиту користувача.
Пиши лаконічно, тепло, структуровано й без фаталізму.
Не використовуй Markdown, HTML, зірочки, решітки чи зворотні лапки.
Між блоками залишай один порожній рядок.

Структура:
🃏 Що додає карта: 2–3 короткі речення.
🔄 Як вона уточнює розклад: 1–2 речення.
💡 На що звернути увагу: один конкретний крок.
"""
    response = await _client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.75,
    )
    return clean_generated_text(response.choices[0].message.content or "")


def _fallback_interpretation(card_info: dict, upright: bool) -> str:
    meaning_key = "meaning_upright" if upright else "meaning_reversed"
    meaning = card_info.get(meaning_key, "Карта пропонує подивитися на ситуацію під новим кутом.")
    return (
        f"🃏 Що додає карта\n{meaning}\n\n"
        "💡 На що звернути увагу\nНе поспішайте з остаточним висновком — врахуйте цей новий нюанс."
    )


@spread_extension_router.callback_query(F.data.startswith("spread_extend:"))
async def extend_spread(callback: types.CallbackQuery) -> None:
    _cleanup_contexts()
    token = callback.data.split(":", 1)[1]
    context = _contexts.get(token)

    if context is None:
        await callback.answer("Ця кнопка вже неактивна. Зробіть новий розклад.", show_alert=True)
        return
    if callback.from_user.id != context.user_id:
        await callback.answer("Це доповнення належить іншому користувачу.", show_alert=True)
        return
    if context.used:
        await callback.answer("Цей розклад уже було доповнено.", show_alert=True)
        return

    # Позначаємо до першого await, щоб подвійне натискання не витягнуло дві карти.
    context.used = True
    await callback.answer("Витягую додаткову карту… 🔮")

    try:
        await callback.message.edit_text("✅ Розклад доповнено однією картою.")
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    card_name, card_info, upright = _draw_extra_card(context.excluded_cards)
    arrow = "⬆️" if upright else "⬇️"

    try:
        await callback.message.answer_photo(
            _card_photo(card_info, upright),
            caption=f"🃏 <b>Додаткова карта</b>\n{card_info['ua_name']} {arrow}",
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(f"🃏 Додаткова карта: {card_info['ua_name']} {arrow}")

    loading_message = await callback.message.answer("🔮 Читаю доповнення до розкладу…")
    try:
        interpretation = await _interpret_extension(context, card_name, card_info, upright)
        if not interpretation:
            raise ValueError("The model returned an empty extension")
    except Exception:
        logger.exception("Failed to interpret an extra spread card")
        interpretation = _fallback_interpretation(card_info, upright)
    finally:
        try:
            await loading_message.delete()
        except Exception:
            pass

    await answer_long_text(
        callback.message,
        f"✨ Доповнення до розкладу «{context.spread_name}»\n\n{interpretation}",
        parse_mode=None,
    )
