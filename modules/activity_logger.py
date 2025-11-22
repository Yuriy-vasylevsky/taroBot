# modules/activity_logger.py
from typing import Callable, Awaitable, Dict, Any, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from modules.user_stats_db import track_user_activity


class ActivityLoggerMiddleware(BaseMiddleware):
    """
    Логує всі дії користувачів:
    - звичайні повідомлення (текст, кнопки, команди)
    - callback-кнопки
    - WebApp data
    """

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)

        if user:
            user_id = user.id
            username = user.username
            full_name = user.full_name

            action_text = self._extract_action_text(event)
            if action_text:
                try:
                    print(f"[ActivityLogger] {user_id} -> {action_text}")

                    await track_user_activity(
                        user_id=user_id,
                        username=username,
                        full_name=full_name,
                        action=action_text,
                    )
                except Exception as e:
                    print(f"[ActivityLogger] DB error: {e}")

        return await handler(event, data)

    def _extract_action_text(self, event: Any) -> Optional[str]:
        """
        Формує текст для логування:
        - Message: текст / тип / WebApp data
        - CallbackQuery: data
        """
        if isinstance(event, Message):
            if event.web_app_data:
                raw = event.web_app_data.data or ""
                if len(raw) > 120:
                    raw = raw[:117] + "..."
                return f"WebApp data: {raw}"

            if event.text:
                return f"Message: {event.text}"

            if event.caption:
                return f"Message (caption): {event.caption}"

            return f"Message type: {event.content_type}"

        if isinstance(event, CallbackQuery):
            data = event.data or ""
            if len(data) > 120:
                data = data[:117] + "..."
            return f"Callback: {data}"

        return None
