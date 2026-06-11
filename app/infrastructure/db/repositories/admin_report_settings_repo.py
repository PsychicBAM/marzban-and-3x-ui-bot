from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.admin_report_settings import AdminReportSettings


class AdminReportSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_settings(self) -> AdminReportSettings:
        stmt = select(AdminReportSettings).order_by(AdminReportSettings.id).limit(1)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = AdminReportSettings()
            self._session.add(row)
            await self._session.flush()
            await self._session.refresh(row)
        return row

    async def update_settings(
        self,
        settings: AdminReportSettings,
        *,
        is_enabled: bool | None = None,
        report_hour: int | None = None,
        report_minute: int | None = None,
    ) -> AdminReportSettings:
        if is_enabled is not None:
            settings.is_enabled = is_enabled
        if report_hour is not None:
            settings.report_hour = report_hour
        if report_minute is not None:
            settings.report_minute = report_minute
        settings.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(settings)
        return settings
