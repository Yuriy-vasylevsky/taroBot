from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from modules.user_stats_db import track_user_activity


class ActivityLoggerMiddleware(BaseMiddleware):
    """
    Логує:
    ✔ натискання reply-кнопок
    ✔ натискання inline-кнопок (callback)
    ✔ текст, який юзер вводить вручну
    """

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:

        # 1️⃣ Обробка текстових повідомлень (всі, що юзер сам пише або жме reply-кнопку)
        if isinstance(event, Message):
            if event.text:
                await track_user_activity(
                    user_id=event.from_user.id,
                    username=event.from_user.username,
                    full_name=event.from_user.full_name,
                    action=f"Натиснув / написав: {event.text}",
                )

        # 2️⃣ Inline-кнопки (callback_query)
        if isinstance(event, CallbackQuery):
            await track_user_activity(
                user_id=event.from_user.id,
                username=event.from_user.username,
                full_name=event.from_user.full_name,
                action=f"Inline-кнопка: {event.data}",
            )

        # Продовжуємо виконання хендлерів
        return await handler(event, data)
