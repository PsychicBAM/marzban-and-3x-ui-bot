from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.setting import Setting


class SettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> str | None:
        stmt = select(Setting).where(Setting.key == key)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row.value if row else None

    async def set(self, key: str, value: str) -> Setting:
        stmt = select(Setting).where(Setting.key == key)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = Setting(key=key, value=value)
            self._session.add(row)
        else:
            row.value = value
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete(self, key: str) -> bool:
        stmt = select(Setting).where(Setting.key == key)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def list_all(self) -> list[Setting]:
        stmt = select(Setting).order_by(Setting.key.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
