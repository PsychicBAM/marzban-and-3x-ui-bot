from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TelegramUserData:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None = None

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(part for part in parts if part) or "Пользователь"


@dataclass(slots=True)
class UserInfo:
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    is_admin: bool
    language_code: str = "ru"

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        from app.presentation.i18n import t

        default = t(self.language_code, "user.default_name")
        return " ".join(part for part in parts if part) or default
