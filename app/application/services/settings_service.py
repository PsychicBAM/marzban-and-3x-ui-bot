from __future__ import annotations

from app.application.dto.instruction_settings import InstructionSettings
from app.application.dto.notification_settings import NotificationSettings
from app.application.dto.support_settings import SupportSettings
from app.application.exceptions import PlanValidationError
from app.config.settings import Settings
from app.infrastructure.db.uow import UnitOfWork

PAYMENT_DETAILS_KEY = "payment_details"
SUPPORT_USERNAME_KEY = "support_username"
SUPPORT_URL_KEY = "support_url"
SUPPORT_TEXT_KEY = "support_text"
INSTRUCTION_TEXT_KEY = "instruction_text"
INSTRUCTION_URL_KEY = "instruction_url"
INSTRUCTION_ENABLED_KEY = "instruction_enabled"

DEFAULT_INSTRUCTION_TEXT = (
    "📖 <b>Инструкция по подключению</b>\n\n"
    "1. Откройте приложение VPN (v2rayNG, Streisand, Hiddify и др.).\n"
    "2. Перейдите в раздел «📊 Мой VPN» и получите ссылку или QR-код.\n"
    "3. Импортируйте подписку в приложение.\n"
    "4. Включите VPN и проверьте подключение."
)

NOTIFICATIONS_ENABLED_KEY = "notifications_enabled"
NOTIFICATION_DAYS_KEY = "notification_days"
NOTIFICATION_CHECK_INTERVAL_KEY = "notification_check_interval"
NOTIFICATION_TEST_MODE_KEY = "notification_test_mode"
NOTIFY_EXPIRED_ENABLED_KEY = "notify_expired_enabled"

CHECK_INTERVAL_DAILY = "daily"
CHECK_INTERVAL_HOURLY = "hourly"
CHECK_INTERVAL_EVERY_10_MINUTES = "every_10_minutes"
CHECK_INTERVAL_EVERY_1_MINUTE = "every_1_minute"

VALID_CHECK_INTERVALS: tuple[str, ...] = (
    CHECK_INTERVAL_DAILY,
    CHECK_INTERVAL_HOURLY,
    CHECK_INTERVAL_EVERY_10_MINUTES,
    CHECK_INTERVAL_EVERY_1_MINUTE,
)

CHECK_INTERVAL_LABELS: dict[str, str] = {
    CHECK_INTERVAL_DAILY: "Раз в сутки",
    CHECK_INTERVAL_HOURLY: "Каждый час",
    CHECK_INTERVAL_EVERY_10_MINUTES: "Каждые 10 минут",
    CHECK_INTERVAL_EVERY_1_MINUTE: "Каждую минуту (только для теста)",
}

MAX_REMINDER_DAY = 365


class SettingsService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def get_payment_details(self) -> str | None:
        value, _ = await self._resolve_payment_details()
        return value

    async def set_payment_details(self, value: str) -> None:
        text = value.strip()
        if not text:
            raise PlanValidationError("Реквизиты не могут быть пустыми.")
        await self._uow.settings.set(PAYMENT_DETAILS_KEY, text)

    async def clear_payment_details(self) -> None:
        await self._uow.settings.delete(PAYMENT_DETAILS_KEY)

    async def get_support_settings(self) -> SupportSettings:
        username = await self._resolve_optional_field(
            SUPPORT_USERNAME_KEY,
            self._settings.support_username,
        )
        url = await self._resolve_optional_field(SUPPORT_URL_KEY, self._settings.support_url)
        text = await self._resolve_optional_field(SUPPORT_TEXT_KEY, self._settings.support_text)
        return SupportSettings(username=username, url=url, text=text)

    async def update_support_settings(
        self,
        *,
        username: str | None = None,
        url: str | None = None,
        text: str | None = None,
    ) -> None:
        if username is not None:
            await self._uow.settings.set(SUPPORT_USERNAME_KEY, self.normalize_support_username(username))
        if url is not None:
            await self._uow.settings.set(SUPPORT_URL_KEY, self.validate_support_url(url))
        if text is not None:
            await self._uow.settings.set(SUPPORT_TEXT_KEY, text.strip())

    async def clear_support_settings(self) -> None:
        for key in (SUPPORT_USERNAME_KEY, SUPPORT_URL_KEY, SUPPORT_TEXT_KEY):
            await self._uow.settings.delete(key)

    async def get_instruction_settings(self) -> InstructionSettings:
        text = await self._resolve_optional_field(
            INSTRUCTION_TEXT_KEY,
            self._settings.instruction_text,
        )
        url = await self._resolve_optional_field(
            INSTRUCTION_URL_KEY,
            self._settings.instruction_url,
        )
        enabled = await self._get_bool(
            INSTRUCTION_ENABLED_KEY,
            default=self._settings.instruction_enabled,
        )
        return InstructionSettings(text=text, url=url, enabled=enabled)

    async def update_instruction_settings(
        self,
        *,
        text: str | None = None,
        url: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        if text is not None:
            await self._uow.settings.set(INSTRUCTION_TEXT_KEY, text.strip())
        if url is not None:
            await self._uow.settings.set(INSTRUCTION_URL_KEY, self.validate_support_url(url))
        if enabled is not None:
            await self._uow.settings.set(INSTRUCTION_ENABLED_KEY, "true" if enabled else "false")

    async def clear_instruction_settings(self) -> None:
        for key in (INSTRUCTION_TEXT_KEY, INSTRUCTION_URL_KEY, INSTRUCTION_ENABLED_KEY):
            await self._uow.settings.delete(key)

    async def format_payment_details_admin(self) -> str:
        value, source = await self._resolve_payment_details()
        return self._build_payment_admin_text(value, source)

    def format_support_settings_admin(self, config: SupportSettings) -> str:
        username = f"@{config.username.lstrip('@')}" if config.username else "—"
        url = config.url or "—"
        text = config.text or "—"
        return (
            "🆘 <b>Поддержка</b>\n\n"
            f"Username: <b>{username}</b>\n"
            f"Ссылка: {url}\n"
            f"Текст: {text}"
        )

    def format_instruction_settings_admin(self, config: InstructionSettings) -> str:
        status = "✅ включена" if config.enabled else "🚫 выключена"
        text = config.text or "—"
        url = config.url or "—"
        return (
            "ℹ️ <b>Инструкция</b>\n\n"
            f"Статус: {status}\n"
            f"Текст: {text}\n"
            f"Ссылка: {url}"
        )

    def format_customer_support(self, config: SupportSettings) -> str:
        if config.text:
            lines = [config.text]
        else:
            lines = ["🆘 <b>Поддержка</b>"]
        if config.username:
            lines.append(f"Telegram: @{config.username.lstrip('@')}")
        if config.url:
            lines.append(f"Ссылка: {config.url}")
        if not config.text and not config.username and not config.url:
            return "🆘 Контакт поддержки пока не настроен."
        return "\n\n".join(lines)

    def format_customer_instruction(self, config: InstructionSettings) -> str:
        if not config.enabled:
            return "Инструкция временно недоступна."
        parts: list[str] = []
        if config.text:
            parts.append(config.text)
        if config.url:
            parts.append(f"🔗 {config.url}")
        if parts:
            return "\n\n".join(parts)
        return DEFAULT_INSTRUCTION_TEXT

    @staticmethod
    def normalize_support_username(raw: str) -> str:
        value = raw.strip().lstrip("@")
        if not value:
            raise PlanValidationError("Username не может быть пустым.")
        return value

    @staticmethod
    def validate_support_url(raw: str) -> str:
        value = raw.strip()
        if not value:
            return ""
        if not value.startswith(("http://", "https://")):
            raise PlanValidationError("URL должен начинаться с http:// или https://")
        return value

    async def _resolve_payment_details(self) -> tuple[str | None, str | None]:
        db_value = await self._uow.settings.get(PAYMENT_DETAILS_KEY)
        if db_value is not None and db_value.strip():
            return db_value.strip(), "база данных"
        env_value = self._settings.payment_details
        if env_value and env_value.strip():
            return env_value.strip(), ".env"
        return None, None

    def _build_payment_admin_text(self, value: str | None, source: str | None) -> str:
        if not value:
            return "💳 <b>Реквизиты оплаты</b>\n\nРеквизиты оплаты не настроены."
        source_line = f"\n\n<i>Источник: {source}</i>" if source else ""
        return f"💳 <b>Реквизиты оплаты</b>\n\n{value}{source_line}"

    async def _resolve_optional_field(self, key: str, env_value: str) -> str | None:
        db_value = await self._uow.settings.get(key)
        if db_value is not None:
            stripped = db_value.strip()
            return stripped if stripped else None
        if env_value and env_value.strip():
            return env_value.strip()
        return None

    async def get_notification_settings(self) -> NotificationSettings:
        enabled = await self._get_bool(
            NOTIFICATIONS_ENABLED_KEY,
            default=self._settings.notifications_enabled,
        )
        days_raw = await self._uow.settings.get(NOTIFICATION_DAYS_KEY)
        if days_raw is None or not days_raw.strip():
            days_raw = self._settings.notification_days
        reminder_days = self.parse_notification_days(days_raw)

        interval = await self._uow.settings.get(NOTIFICATION_CHECK_INTERVAL_KEY)
        if not interval or interval not in VALID_CHECK_INTERVALS:
            interval = self._settings.notification_check_interval

        test_mode = await self._get_bool(
            NOTIFICATION_TEST_MODE_KEY,
            default=self._settings.notification_test_mode,
        )
        notify_expired = await self._get_bool(
            NOTIFY_EXPIRED_ENABLED_KEY,
            default=self._settings.notify_expired_enabled,
        )

        return NotificationSettings(
            enabled=enabled,
            reminder_days=reminder_days,
            check_interval=interval,
            test_mode=test_mode,
            notify_expired_enabled=notify_expired,
        )

    async def set_notifications_enabled(self, enabled: bool) -> None:
        await self._uow.settings.set(NOTIFICATIONS_ENABLED_KEY, "true" if enabled else "false")

    async def set_notification_days(self, days: list[int]) -> None:
        value = ",".join(str(day) for day in sorted(days, reverse=True))
        await self._uow.settings.set(NOTIFICATION_DAYS_KEY, value)

    async def set_notification_check_interval(self, interval: str) -> None:
        if interval not in VALID_CHECK_INTERVALS:
            raise PlanValidationError("Некорректный интервал проверки.")
        await self._uow.settings.set(NOTIFICATION_CHECK_INTERVAL_KEY, interval)

    async def set_notification_test_mode(self, enabled: bool) -> None:
        await self._uow.settings.set(NOTIFICATION_TEST_MODE_KEY, "true" if enabled else "false")

    async def set_notify_expired_enabled(self, enabled: bool) -> None:
        await self._uow.settings.set(NOTIFY_EXPIRED_ENABLED_KEY, "true" if enabled else "false")

    def format_notification_settings(self, config: NotificationSettings) -> str:
        days = ", ".join(str(day) for day in config.reminder_days) or "—"
        interval_label = CHECK_INTERVAL_LABELS.get(config.check_interval, config.check_interval)
        return (
            "🔔 <b>Уведомления об истечении VPN</b>\n\n"
            f"Статус: {'✅ включены' if config.enabled else '🚫 выключены'}\n"
            f"Дни напоминаний: <b>{days}</b>\n"
            f"Интервал проверки: <b>{interval_label}</b>\n"
            f"Тестовый режим: {'🧪 включён' if config.test_mode else 'выключен'}\n"
            f"Уведомление «истёк»: {'✅ включено' if config.notify_expired_enabled else '🚫 выключено'}\n\n"
            "<i>Режим «каждую минуту» — только для проверки scheduler.</i>"
        )

    @staticmethod
    def parse_notification_days(raw_value: str) -> list[int]:
        text = (raw_value or "").strip()
        if not text:
            raise PlanValidationError("Укажите хотя бы один день.")
        parts = [part.strip() for part in text.split(",") if part.strip()]
        days: list[int] = []
        seen: set[int] = set()
        for part in parts:
            if not part.isdigit():
                raise PlanValidationError("Дни должны быть положительными целыми числами.")
            day = int(part)
            if day <= 0:
                raise PlanValidationError("Дни должны быть больше 0.")
            if day > MAX_REMINDER_DAY:
                raise PlanValidationError(f"Максимальное значение дня: {MAX_REMINDER_DAY}.")
            if day in seen:
                raise PlanValidationError("Дни не должны повторяться.")
            seen.add(day)
            days.append(day)
        return sorted(days, reverse=True)

    async def _get_bool(self, key: str, *, default: bool) -> bool:
        raw = await self._uow.settings.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}
