from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_telegram_ids: list[int] = Field(default_factory=list, alias="ADMIN_TELEGRAM_IDS")

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # Application
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    timezone: str = Field("Europe/Moscow", alias="TIMEZONE")
    default_issuing_mode: Literal["marzban", "xui", "both"] = Field(
        "both",
        alias="DEFAULT_ISSUING_MODE",
    )

    # Marzban
    marzban_enabled: bool = Field(False, alias="MARZBAN_ENABLED")
    marzban_base_url: str = Field("", alias="MARZBAN_BASE_URL")
    marzban_username: str = Field("", alias="MARZBAN_USERNAME")
    marzban_password: str = Field("", alias="MARZBAN_PASSWORD")
    marzban_verify_ssl: bool = Field(True, alias="MARZBAN_VERIFY_SSL")
    marzban_inbound_vless: str = Field("vless-tcp-reality", alias="MARZBAN_INBOUND_VLESS")
    marzban_inbound_trojan: str = Field("trojan-tcp-notls", alias="MARZBAN_INBOUND_TROJAN")
    marzban_inbound_vmess: str = Field("vmess-tcp-notls", alias="MARZBAN_INBOUND_VMESS")
    marzban_api_token: str = Field("", alias="MARZBAN_API_TOKEN")
    marzban_subscription_base_url: str = Field("", alias="MARZBAN_SUBSCRIPTION_BASE_URL")

    # 3x-ui
    xui_enabled: bool = Field(False, alias="XUI_ENABLED")
    xui_base_url: str = Field("", alias="XUI_BASE_URL")
    xui_api_token: str = Field("", alias="XUI_API_TOKEN")
    xui_username: str = Field("", alias="XUI_USERNAME")
    xui_password: str = Field("", alias="XUI_PASSWORD")
    xui_inbound_id: int = Field(1, alias="XUI_INBOUND_ID")
    xui_verify_ssl: bool = Field(True, alias="XUI_VERIFY_SSL")
    xui_subscription_base_url: str = Field("", alias="XUI_SUBSCRIPTION_BASE_URL")

    # Defaults (overridable via DB settings later)
    payment_details: str = Field("", alias="PAYMENT_DETAILS")
    support_username: str = Field("", alias="SUPPORT_USERNAME")
    support_url: str = Field("", alias="SUPPORT_URL")
    support_text: str = Field("", alias="SUPPORT_TEXT")
    instruction_text: str = Field("", alias="INSTRUCTION_TEXT")
    instruction_url: str = Field("", alias="INSTRUCTION_URL")
    instruction_enabled: bool = Field(True, alias="INSTRUCTION_ENABLED")

    # Expiry notifications (overridable via DB settings)
    notifications_enabled: bool = Field(True, alias="NOTIFICATIONS_ENABLED")
    notification_days: str = Field("7,3,1", alias="NOTIFICATION_DAYS")
    notification_check_interval: Literal[
        "daily",
        "hourly",
        "every_10_minutes",
        "every_1_minute",
    ] = Field("daily", alias="NOTIFICATION_CHECK_INTERVAL")
    notification_test_mode: bool = Field(False, alias="NOTIFICATION_TEST_MODE")
    notify_expired_enabled: bool = Field(True, alias="NOTIFY_EXPIRED_ENABLED")

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return [int(part) for part in parts]
        raise ValueError("ADMIN_TELEGRAM_IDS must be a comma-separated list of integers")

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.admin_telegram_ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
