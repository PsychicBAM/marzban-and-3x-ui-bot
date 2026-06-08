from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MarzbanUserInfo:
    username: str
    status: str
    expire_at: datetime | None
    subscription_url: str | None
    used_traffic_bytes: int
    data_limit_bytes: int


class MarzbanPort(ABC):
    @abstractmethod
    async def get_user(self, username: str) -> MarzbanUserInfo | None:
        raise NotImplementedError

    @abstractmethod
    async def create_user(
        self,
        *,
        username: str,
        expire_at: datetime,
        data_limit_gb: int,
        ip_limit: int,
    ) -> MarzbanUserInfo:
        raise NotImplementedError

    @abstractmethod
    async def update_user(
        self,
        *,
        username: str,
        expire_at: datetime,
        data_limit_gb: int,
        ip_limit: int,
        enable: bool,
    ) -> MarzbanUserInfo:
        raise NotImplementedError

    @abstractmethod
    async def disable_user(self, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def enable_user(self, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_user(self, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_subscription_link(self, username: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def reset_user_ips(self, username: str) -> bool:
        raise NotImplementedError
