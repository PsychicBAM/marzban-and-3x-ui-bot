from __future__ import annotations

from aiogram.types import User as TelegramUser

from app.application.dto.user import TelegramUserData


def map_telegram_user(user: TelegramUser) -> TelegramUserData:
    return TelegramUserData(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
