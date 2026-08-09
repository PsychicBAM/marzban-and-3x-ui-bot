from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TelegramUser

from app.application.services.user_service import UserService
from app.presentation.i18n import DEFAULT_LANG
from app.presentation.utils.telegram import map_telegram_user


def _from_user(event: TelegramObject) -> TelegramUser | None:
    if isinstance(event, Message):
        return event.from_user
    if isinstance(event, CallbackQuery):
        return event.from_user
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
        telegram_user = _from_user(event)
        if user_service is not None and telegram_user is not None:
            # Keep Telegram profile fields fresh on every customer interaction.
            try:
                user_info = await user_service.register_or_update(map_telegram_user(telegram_user))
                lang = user_info.language_code
            except Exception:
                lang = await user_service.get_user_language(telegram_id=telegram_user.id)
        data["lang"] = lang
        return await handler(event, data)
