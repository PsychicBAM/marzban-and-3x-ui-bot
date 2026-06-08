from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.config.settings import Settings


class IsAdminFilter(BaseFilter):
    async def __call__(self, message: Message, settings: Settings) -> bool:
        user = message.from_user
        return user is not None and settings.is_admin(user.id)


class IsAdminCallbackFilter(BaseFilter):
    async def __call__(self, callback: CallbackQuery, settings: Settings) -> bool:
        user = callback.from_user
        return user is not None and settings.is_admin(user.id)
