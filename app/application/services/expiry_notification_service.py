from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from aiogram import Bot

from app.application.dto.notification_settings import ExpiryNotificationJobResult, NotificationSettings
from app.application.services.admin_log_service import AdminLogService
from app.application.services.settings_service import SettingsService
from app.application.utils.notification_type import expiry_reminder_type
from app.config.settings import Settings
from app.domain.enums import AdminActionType, NotificationType, VpnAccountStatus
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.uow import UnitOfWork
from app.presentation.keyboards.customer import customer_main_keyboard

logger = logging.getLogger(__name__)

SYSTEM_ADMIN_ID = 0
EXPIRED_REMINDER_DAYS_SENTINEL = 0


class ExpiryNotificationService:
    """Send configurable expiry reminders and expired notices with duplicate protection."""

    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        settings_service: SettingsService,
        admin_log_service: AdminLogService,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._settings_service = settings_service
        self._admin_log = admin_log_service

    async def run_scheduled_job(self, bot: Bot) -> ExpiryNotificationJobResult:
        config = await self._settings_service.get_notification_settings()
        result = ExpiryNotificationJobResult(
            processed=0,
            sent=0,
            skipped=0,
            failed=0,
            test_mode=config.test_mode,
        )
        if not config.enabled:
            return result

        if config.test_mode:
            logger.info("Expiry notification job skipped: test mode enabled")
            return result

        accounts = await self._uow.vpn_accounts.list_active_for_expiry_notifications()
        now = datetime.now(UTC)

        for account in accounts:
            result.processed += 1
            try:
                sent, skipped, failed = await self._process_account(bot, account, config, now=now)
                result.sent += sent
                result.skipped += skipped
                result.failed += failed
            except Exception as exc:
                result.failed += 1
                safe_error = str(exc)[:500]
                logger.exception(
                    "Expiry notification account processing failed",
                    extra={"vpn_account_id": account.id, "error": safe_error},
                )
                await self._admin_log.log(
                    admin_telegram_id=SYSTEM_ADMIN_ID,
                    action=AdminActionType.NOTIFICATION_JOB_FAILED,
                    details={"vpn_account_id": account.id, "error": safe_error},
                )
        return result

    async def send_test_to_admin(self, bot: Bot, *, admin_telegram_id: int) -> str:
        config = await self._settings_service.get_notification_settings()
        sample = self._format_reminder_message(
            days=7,
            plan_name="Демо-тариф",
            expiry_at=datetime.now(UTC),
            test_mode=True,
        )
        await bot.send_message(
            admin_telegram_id,
            sample,
            reply_markup=customer_main_keyboard(),
        )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.NOTIFICATION_TEST_SENT,
            details={"test_mode": config.test_mode},
        )
        return "✅ Тестовое уведомление отправлено вам в личные сообщения."

    async def _process_account(
        self,
        bot: Bot,
        account: VpnAccount,
        config: NotificationSettings,
        *,
        now: datetime,
    ) -> tuple[int, int, int]:
        user = account.user
        if user is None:
            return 0, 1, 0

        expiry = account.expiry_date
        if expiry is None:
            return 0, 1, 0
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)

        days_left = (expiry.date() - now.date()).days
        sent = 0
        skipped = 0
        failed = 0

        plan_name = await self._plan_name(account.plan_id)

        for reminder_day in config.reminder_days:
            if days_left != reminder_day:
                continue
            notification_type = expiry_reminder_type(reminder_day)
            if await self._uow.notifications.exists(
                vpn_account_id=account.id,
                notification_type=notification_type,
                reminder_days_before=reminder_day,
            ):
                skipped += 1
                continue

            message = self._format_reminder_message(
                days=reminder_day,
                plan_name=plan_name,
                expiry_at=expiry,
                test_mode=False,
            )
            ok = await self._send_telegram(bot, user.telegram_id, message)
            if not ok:
                failed += 1
                continue

            await self._uow.notifications.create(
                user_id=user.id,
                vpn_account_id=account.id,
                notification_type=notification_type,
                reminder_days_before=reminder_day,
                details=json.dumps({"days_left": reminder_day}),
            )
            await self._admin_log.log(
                admin_telegram_id=SYSTEM_ADMIN_ID,
                action=AdminActionType.EXPIRY_NOTIFICATION_SENT,
                details={
                    "user_id": user.id,
                    "vpn_account_id": account.id,
                    "days": reminder_day,
                },
            )
            sent += 1

        if config.notify_expired_enabled and expiry <= now:
            if await self._uow.notifications.exists(
                vpn_account_id=account.id,
                notification_type=NotificationType.EXPIRED.value,
                reminder_days_before=EXPIRED_REMINDER_DAYS_SENTINEL,
            ):
                skipped += 1
            else:
                message = self._format_expired_message(plan_name=plan_name, expiry_at=expiry)
                ok = await self._send_telegram(bot, user.telegram_id, message)
                if ok:
                    await self._uow.notifications.create(
                        user_id=user.id,
                        vpn_account_id=account.id,
                        notification_type=NotificationType.EXPIRED.value,
                        reminder_days_before=EXPIRED_REMINDER_DAYS_SENTINEL,
                        details=json.dumps({"expired_at": expiry.isoformat()}),
                    )
                    await self._uow.vpn_accounts.update_admin_state(
                        account,
                        status=VpnAccountStatus.EXPIRED.value,
                    )
                    await self._admin_log.log(
                        admin_telegram_id=SYSTEM_ADMIN_ID,
                        action=AdminActionType.EXPIRED_NOTIFICATION_SENT,
                        details={
                            "user_id": user.id,
                            "vpn_account_id": account.id,
                        },
                    )
                    sent += 1
                else:
                    failed += 1

        return sent, skipped, failed

    async def _plan_name(self, plan_id: int | None) -> str | None:
        if plan_id is None:
            return None
        plan = await self._uow.plans.get_by_id(plan_id)
        return plan.name if plan else None

    async def _send_telegram(self, bot: Bot, telegram_id: int, message: str) -> bool:
        try:
            await bot.send_message(telegram_id, message, reply_markup=customer_main_keyboard())
            return True
        except Exception as exc:
            logger.warning(
                "Failed to send expiry notification",
                extra={"telegram_id": telegram_id, "error": str(exc)[:300]},
            )
            return False

    @staticmethod
    def _format_reminder_message(
        *,
        days: int,
        plan_name: str | None,
        expiry_at: datetime,
        test_mode: bool,
    ) -> str:
        if days == 7:
            lead = (
                "🔔 Ваш VPN истекает через 7 дней. "
                "Чтобы продолжить пользоваться VPN, нажмите «🔄 Продлить VPN»."
            )
        elif days == 3:
            lead = "⚠️ Ваш VPN истекает через 3 дня."
        elif days == 1:
            lead = "⏰ Ваш VPN истекает завтра."
        else:
            lead = (
                f"🔔 Ваш VPN истекает через {days} дн. "
                "Чтобы продолжить пользоваться VPN, нажмите «🔄 Продлить VPN»."
            )

        lines = []
        if test_mode:
            lines.append("🧪 <b>Тестовое уведомление</b>")
            lines.append("")
        lines.append(lead)
        if plan_name:
            lines.append(f"📦 Тариф: {plan_name}")
        lines.append(f"📅 Действует до: {expiry_at.strftime('%d.%m.%Y %H:%M')}")
        return "\n".join(lines)

    @staticmethod
    def _format_expired_message(*, plan_name: str | None, expiry_at: datetime) -> str:
        lines = [
            "⛔ Ваш VPN истёк. Нажмите «🔄 Продлить VPN», чтобы продлить доступ.",
        ]
        if plan_name:
            lines.append(f"📦 Тариф: {plan_name}")
        lines.append(f"📅 Истёк: {expiry_at.strftime('%d.%m.%Y %H:%M')}")
        return "\n".join(lines)
