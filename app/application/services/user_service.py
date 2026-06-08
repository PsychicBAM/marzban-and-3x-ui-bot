from __future__ import annotations

import logging

from app.application.dto.user import TelegramUserData, UserInfo
from app.config.settings import Settings
from app.infrastructure.db.models.user import User
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def register_or_update(self, data: TelegramUserData) -> UserInfo:
        is_admin = self._settings.is_admin(data.telegram_id)
        existing = await self._uow.users.get_by_telegram_id(data.telegram_id)

        if existing is None:
            user = await self._uow.users.create(
                telegram_id=data.telegram_id,
                username=data.username,
                first_name=data.first_name,
                last_name=data.last_name,
                is_admin=is_admin,
            )
            logger.info(
                "New user registered",
                extra={"telegram_id": data.telegram_id, "user_id": user.id},
            )
            return self._to_info(user)

        user = await self._uow.users.update_profile(
            existing,
            username=data.username,
            first_name=data.first_name,
            last_name=data.last_name,
            is_admin=is_admin,
        )
        logger.debug(
            "User profile updated",
            extra={"telegram_id": data.telegram_id, "user_id": user.id},
        )
        return self._to_info(user)

    @staticmethod
    def _to_info(user: User) -> UserInfo:
        return UserInfo(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_admin=user.is_admin,
        )
