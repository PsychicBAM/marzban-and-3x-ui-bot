from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TelegramUserData:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None

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

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(part for part in parts if part) or "Пользователь"
