from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.admin_log import AdminLog


class AdminLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        admin_telegram_id: int,
        action_type: str,
        details: dict[str, Any] | None = None,
    ) -> AdminLog:
        log = AdminLog(
            admin_telegram_id=admin_telegram_id,
            action_type=action_type,
            details=details,
        )
        self._session.add(log)
        await self._session.flush()
        await self._session.refresh(log)
        return log

    async def list_for_customer_user(
        self,
        user_id: int,
        action_types: tuple[str, ...],
        *,
        limit: int = 100,
    ) -> list[AdminLog]:
        stmt = (
            select(AdminLog)
            .where(AdminLog.action_type.in_(action_types))
            .order_by(AdminLog.created_at.desc())
            .limit(limit * 3)
        )
        result = await self._session.execute(stmt)
        logs = []
        for row in result.scalars().all():
            details = row.details or {}
            if details.get("user_id") == user_id:
                logs.append(row)
            if len(logs) >= limit:
                break
        return logs
