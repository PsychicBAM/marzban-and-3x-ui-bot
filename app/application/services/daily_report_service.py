from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot

from app.application.dto.daily_report import DailyReportSnapshot
from app.application.services.admin_log_service import AdminLogService
from app.application.services.system_status_service import SystemStatusService
from app.config.settings import Settings
from app.domain.enums import AdminActionType
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


class DailyReportService:
    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        system_status_service: SystemStatusService,
        admin_log_service: AdminLogService,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._system_status = system_status_service
        self._admin_log = admin_log_service

    async def get_settings(self):
        return await self._uow.admin_report_settings.get_settings()

    async def set_enabled(self, *, enabled: bool, admin_telegram_id: int):
        settings = await self.get_settings()
        await self._uow.admin_report_settings.update_settings(settings, is_enabled=enabled)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.ADMIN_DAILY_REPORT_SETTINGS_UPDATED,
            details={"is_enabled": enabled},
        )
        return settings

    async def set_time(self, *, hour: int, minute: int, admin_telegram_id: int):
        settings = await self.get_settings()
        await self._uow.admin_report_settings.update_settings(
            settings,
            report_hour=hour,
            report_minute=minute,
        )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.ADMIN_DAILY_REPORT_SETTINGS_UPDATED,
            details={"report_hour": hour, "report_minute": minute},
        )
        return settings

    async def collect(self) -> DailyReportSnapshot:
        tz = ZoneInfo(self._settings.timezone)
        now_local = datetime.now(tz)
        now_utc = datetime.now(UTC)
        start_today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        start_today_utc = start_today_local.astimezone(UTC)
        end_today_utc = (start_today_local + timedelta(days=1)).astimezone(UTC)
        start_7_days_utc = (start_today_local - timedelta(days=6)).astimezone(UTC)

        status = await self._system_status.collect()
        vpn_counts = await self._uow.statistics.get_vpn_account_counts()
        expiring = await self._uow.statistics.count_expiring_soon(now=now_utc)
        revenue_today, _, _ = await self._uow.statistics.get_revenue_for_period(
            start_utc=start_today_utc,
            end_utc=end_today_utc,
        )
        revenue_7_days, _, _ = await self._uow.statistics.get_revenue_for_period(start_utc=start_7_days_utc)

        return DailyReportSnapshot(
            database_ok=status.database_ok,
            database_error=status.database_error,
            marzban=status.marzban,
            xui=status.xui,
            total_users=status.total_users,
            active_subscriptions=status.active_subscriptions,
            expiring_in_3_days=expiring.in_3_days,
            expired_subscriptions=vpn_counts.expired,
            pending_payments=status.pending_payments,
            open_support_tickets=await self._uow.statistics.count_open_support_tickets(),
            referrals_today=await self._uow.statistics.count_referrals_since(start_today_utc),
            promo_redemptions_today=await self._uow.statistics.count_promo_redemptions_since(start_today_utc),
            broadcasts_today=await self._uow.statistics.count_broadcasts_sent_since(start_today_utc),
            revenue_today=revenue_today,
            revenue_7_days=revenue_7_days,
            last_backup=status.last_backup,
            generated_at_label=now_local.strftime("%d.%m.%Y %H:%M"),
        )

    def format_message(self, snapshot: DailyReportSnapshot) -> str:
        db_line = "OK" if snapshot.database_ok else f"ошибка ({snapshot.database_error or '—'})"
        marzban_line = self._panel_line(snapshot.marzban)
        xui_line = self._panel_line(snapshot.xui)
        backup = snapshot.last_backup or "не найден"
        return "\n".join(
            [
                "🩺 <b>Ежедневный отчёт KeyGate VPN</b>",
                "",
                "🤖 Бот: работает",
                f"🗄 База данных: {db_line}",
                f"📡 Marzban: {marzban_line}",
                f"📡 3x-ui: {xui_line}",
                "",
                f"👥 Пользователей: <b>{snapshot.total_users}</b>",
                f"✅ Активных подписок: <b>{snapshot.active_subscriptions}</b>",
                f"⏳ Истекают за 3 дня: <b>{snapshot.expiring_in_3_days}</b>",
                f"❌ Истёкших: <b>{snapshot.expired_subscriptions}</b>",
                f"📥 Заявок на проверке: <b>{snapshot.pending_payments}</b>",
                f"🆘 Открытых обращений: <b>{snapshot.open_support_tickets}</b>",
                f"🎁 Рефералы сегодня: <b>{snapshot.referrals_today}</b>",
                f"🎟 Использовано промокодов сегодня: <b>{snapshot.promo_redemptions_today}</b>",
                f"📣 Рассылки сегодня: <b>{snapshot.broadcasts_today}</b>",
                f"💰 Доход сегодня: <b>{int(snapshot.revenue_today)} ₽</b>",
                f"💰 Доход за 7 дней: <b>{int(snapshot.revenue_7_days)} ₽</b>",
                f"💾 Последний бэкап: <code>{backup}</code>",
                "",
                f"🕘 Проверено: {snapshot.generated_at_label}",
            ]
        )

    async def send_to_admins(self, bot: Bot) -> tuple[int, int]:
        admin_ids = self._settings.admin_telegram_ids
        if not admin_ids:
            logger.warning("Daily admin report skipped: no ADMIN_TELEGRAM_IDS")
            return 0, 0

        try:
            snapshot = await self.collect()
            text = self.format_message(snapshot)
        except Exception as exc:
            safe_error = str(exc)[:500]
            logger.exception("Daily admin report collection failed", extra={"error": safe_error})
            await self._admin_log.log(
                admin_telegram_id=0,
                action=AdminActionType.ADMIN_DAILY_REPORT_FAILED,
                details={"error": safe_error},
            )
            return 0, len(admin_ids)

        sent = 0
        failed = 0
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, text)
                sent += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Failed to send daily admin report",
                    extra={"admin_telegram_id": admin_id, "error": str(exc)[:300]},
                )

        await self._admin_log.log(
            admin_telegram_id=admin_ids[0],
            action=AdminActionType.ADMIN_DAILY_REPORT_SENT,
            details={"sent": sent, "failed": failed},
        )
        logger.info("admin_daily_report_sent", extra={"sent": sent, "failed": failed})
        return sent, failed

    @staticmethod
    def _panel_line(panel) -> str:
        if not panel.enabled:
            return "выключен"
        if panel.ok:
            return "OK"
        return f"ошибка ({panel.detail})"
