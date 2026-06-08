from __future__ import annotations

import logging
from typing import Any

from app.domain.enums import AdminActionType
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


class AdminLogService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def log(
        self,
        *,
        admin_telegram_id: int,
        action: AdminActionType | str,
        details: dict[str, Any] | None = None,
    ) -> None:
        action_value = action.value if isinstance(action, AdminActionType) else action
        await self._uow.admin_logs.create(
            admin_telegram_id=admin_telegram_id,
            action_type=action_value,
            details=details,
        )
        logger.info(
            "Admin action logged",
            extra={"admin_telegram_id": admin_telegram_id, "action": action_value},
        )
