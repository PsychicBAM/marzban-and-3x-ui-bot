from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.application.services.user_service import UserService
from app.presentation.i18n import DEFAULT_LANG


def _telegram_id_from_event(event: TelegramObject) -> int | None:
    if isinstance(event, Message) and event.from_user is not None:
        return event.from_user.id
    if isinstance(event, CallbackQuery) and event.from_user is not None:
        return event.from_user.id
    return None


class UserLanguageMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        lang = DEFAULT_LANG
        user_service: UserService | None = data.get("user_service")
        telegram_id = _telegram_id_from_event(event)
        if user_service is not None and telegram_id is not None:
            lang = await user_service.get_user_language(telegram_id=telegram_id)
        data["lang"] = lang
        return await handler(event, data)
