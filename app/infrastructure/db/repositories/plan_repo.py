from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.plan import Plan


class PlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(Plan)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_all(self) -> list[Plan]:
        stmt = select(Plan).order_by(Plan.is_active.desc(), Plan.duration_days.asc(), Plan.price.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active(self) -> list[Plan]:
        stmt = (
            select(Plan)
            .where(Plan.is_active.is_(True))
            .order_by(Plan.duration_days.asc(), Plan.price.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, plan_id: int) -> Plan | None:
        stmt = select(Plan).where(Plan.id == plan_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        price: Decimal,
        duration_days: int,
        traffic_limit_gb: int,
        ip_limit: int,
        issuing_mode: str,
        is_active: bool = True,
        description: str | None = None,
    ) -> Plan:
        plan = Plan(
            name=name,
            price=price,
            duration_days=duration_days,
            traffic_limit_gb=traffic_limit_gb,
            ip_limit=ip_limit,
            issuing_mode=issuing_mode,
            is_active=is_active,
            description=description,
        )
        self._session.add(plan)
        await self._session.flush()
        await self._session.refresh(plan)
        return plan

    async def update_fields(
        self,
        plan: Plan,
        *,
        name: str | None = None,
        price: Decimal | None = None,
        duration_days: int | None = None,
        traffic_limit_gb: int | None = None,
        ip_limit: int | None = None,
        issuing_mode: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> Plan:
        if name is not None:
            plan.name = name
        if price is not None:
            plan.price = price
        if duration_days is not None:
            plan.duration_days = duration_days
        if traffic_limit_gb is not None:
            plan.traffic_limit_gb = traffic_limit_gb
        if ip_limit is not None:
            plan.ip_limit = ip_limit
        if issuing_mode is not None:
            plan.issuing_mode = issuing_mode
        if description is not None:
            plan.description = description
        if is_active is not None:
            plan.is_active = is_active
        await self._session.flush()
        await self._session.refresh(plan)
        return plan
