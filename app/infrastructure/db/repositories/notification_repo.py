from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.notification import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(
        self,
        *,
        vpn_account_id: int,
        notification_type: str,
        reminder_days_before: int | None,
    ) -> bool:
        stmt = select(Notification.id).where(
            Notification.vpn_account_id == vpn_account_id,
            Notification.notification_type == notification_type,
            Notification.reminder_days_before == reminder_days_before,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        *,
        user_id: int,
        vpn_account_id: int,
        notification_type: str,
        reminder_days_before: int | None = None,
        channel: str = "telegram",
        details: str | None = None,
    ) -> Notification:
        row = Notification(
            user_id=user_id,
            vpn_account_id=vpn_account_id,
            notification_type=notification_type,
            reminder_days_before=reminder_days_before,
            channel=channel,
            details=details,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def find_existing(
        self,
        *,
        vpn_account_id: int,
        notification_type: str,
        reminder_days_before: int | None,
    ) -> Notification | None:
        stmt = select(Notification).where(
            Notification.vpn_account_id == vpn_account_id,
            Notification.notification_type == notification_type,
            Notification.reminder_days_before == reminder_days_before,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
