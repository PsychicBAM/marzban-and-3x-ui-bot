from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.application.services.admin_log_service import AdminLogService
from app.application.services.expiry_notification_service import ExpiryNotificationService
from app.application.services.settings_service import (
    CHECK_INTERVAL_DAILY,
    CHECK_INTERVAL_EVERY_1_MINUTE,
    CHECK_INTERVAL_EVERY_10_MINUTES,
    CHECK_INTERVAL_HOURLY,
    SettingsService,
)
from app.config.settings import Settings
from app.domain.enums import AdminActionType
from app.infrastructure.db.session import session_scope
from app.infrastructure.db.uow import UnitOfWork

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)

JOB_ID = "expiry_notifications"

_scheduler_instance: ExpiryNotificationScheduler | None = None


def get_expiry_scheduler() -> ExpiryNotificationScheduler | None:
    return _scheduler_instance


def set_expiry_scheduler(scheduler: ExpiryNotificationScheduler) -> None:
    global _scheduler_instance
    _scheduler_instance = scheduler


class ExpiryNotificationScheduler:
    """APScheduler wrapper for expiry notification jobs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._scheduler = AsyncIOScheduler(timezone=settings.timezone)
        self._bot: Bot | None = None

    def start(self, bot: Bot) -> None:
        self._bot = bot
        if not self._scheduler.running:
            self._scheduler.start()
        logger.info("Expiry notification scheduler started")

    async def bootstrap(self) -> None:
        interval = await self._load_interval()
        self.reschedule(interval)

    def reschedule(self, interval: str) -> bool:
        if not self._scheduler.running:
            return False
        trigger = self._trigger_for(interval)
        self._scheduler.add_job(
            self._run_job,
            trigger=trigger,
            id=JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("Expiry notification job rescheduled", extra={"interval": interval})
        return True

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Expiry notification scheduler stopped")

    async def _run_job(self) -> None:
        if self._bot is None:
            return
        try:
            async with session_scope() as session:
                uow = UnitOfWork(session)
                settings_service = SettingsService(uow, self._settings)
                admin_log = AdminLogService(uow)
                service = ExpiryNotificationService(
                    uow=uow,
                    settings=self._settings,
                    settings_service=settings_service,
                    admin_log_service=admin_log,
                )
                result = await service.run_scheduled_job(self._bot)
                logger.info(
                    "Expiry notification job finished",
                    extra={
                        "processed": result.processed,
                        "sent": result.sent,
                        "skipped": result.skipped,
                        "failed": result.failed,
                        "test_mode": result.test_mode,
                    },
                )
        except Exception as exc:
            safe_error = str(exc)[:500]
            logger.exception("Expiry notification job failed", extra={"error": safe_error})
            try:
                async with session_scope() as session:
                    uow = UnitOfWork(session)
                    await AdminLogService(uow).log(
                        admin_telegram_id=0,
                        action=AdminActionType.NOTIFICATION_JOB_FAILED,
                        details={"error": safe_error},
                    )
            except Exception:
                logger.exception("Failed to write notification job failure log")

    async def _load_interval(self) -> str:
        async with session_scope() as session:
            uow = UnitOfWork(session)
            config = await SettingsService(uow, self._settings).get_notification_settings()
            return config.check_interval

    @staticmethod
    def _trigger_for(interval: str) -> IntervalTrigger:
        mapping = {
            CHECK_INTERVAL_DAILY: {"days": 1},
            CHECK_INTERVAL_HOURLY: {"hours": 1},
            CHECK_INTERVAL_EVERY_10_MINUTES: {"minutes": 10},
            CHECK_INTERVAL_EVERY_1_MINUTE: {"minutes": 1},
        }
        kwargs = mapping.get(interval, {"days": 1})
        return IntervalTrigger(**kwargs)
