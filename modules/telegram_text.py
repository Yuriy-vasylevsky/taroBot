import html
import re
from typing import Any, Optional

from aiogram import types
from aiogram.exceptions import TelegramBadRequest


TELEGRAM_TEXT_LIMIT = 4096
SAFE_TEXT_LIMIT = 3500
_HTML_TAG_RE = re.compile(r"</?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|a)(?:\s+[^>]*)?>", re.I)


def clean_generated_text(text: str) -> str:
    """Прибирає Markdown-сміття й зайві порожні рядки з відповідей моделі."""
    cleaned = (text or "").replace("*", "").replace("`", "")
    cleaned = re.sub(r"(?m)^\s*#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"(?m)^[ \t]+", "", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def split_long_text(text: str, limit: int = SAFE_TEXT_LIMIT) -> list[str]:
    """Ділить текст по абзацах/рядках/словах, не перевищуючи ліміт Telegram."""
    remaining = (text or "").strip()
    if not remaining:
        return [""]

    chunks: list[str] = []
    while len(remaining) > limit:
        cut = remaining.rfind("\n\n", 0, limit + 1)
        if cut < limit // 2:
            cut = remaining.rfind("\n", 0, limit + 1)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit + 1)
        if cut < limit // 2:
            cut = limit

        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    if remaining:
        chunks.append(remaining)
    return chunks


def _html_to_plain_text(text: str) -> str:
    # Для довгого HTML безпечніше прибрати розмітку, ніж розірвати тег між частинами.
    return html.unescape(_HTML_TAG_RE.sub("", text or ""))


async def answer_long_text(
    message: types.Message,
    text: str,
    *,
    parse_mode: Optional[str] = "HTML",
    reply_markup: Any = None,
) -> list[types.Message]:
    """Відправляє текст одним або кількома повідомленнями в межах ліміту Telegram."""
    if len(text or "") <= TELEGRAM_TEXT_LIMIT:
        try:
            sent = await message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
            return [sent]
        except TelegramBadRequest as error:
            if "message is too long" not in str(error).lower():
                raise

    safe_text = _html_to_plain_text(text) if parse_mode else text
    chunks = split_long_text(safe_text)
    sent_messages: list[types.Message] = []

    for index, chunk in enumerate(chunks):
        sent_messages.append(
            await message.answer(
                chunk,
                parse_mode=None,
                reply_markup=reply_markup if index == len(chunks) - 1 else None,
            )
        )

    return sent_messages
