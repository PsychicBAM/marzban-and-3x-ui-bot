from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.customer_event import CustomerEvent


class CustomerEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user_id(self, user_id: int, *, limit: int = 200) -> list[CustomerEvent]:
        stmt = (
            select(CustomerEvent)
            .where(CustomerEvent.user_id == user_id)
            .order_by(CustomerEvent.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
