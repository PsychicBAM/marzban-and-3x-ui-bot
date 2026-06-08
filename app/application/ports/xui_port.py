from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class XuiClientInfo:
    client_uuid: str
    email: str
    enable: bool
    expiry_time: datetime | None
    total_gb: int
    limit_ip: int
    used_traffic_bytes: int
    subscription_url: str | None


class XuiPort(ABC):
    @abstractmethod
    async def get_client(self, email: str) -> XuiClientInfo | None:
        raise NotImplementedError

    @abstractmethod
    async def create_client(
        self,
        *,
        email: str,
        expiry_time: datetime,
        total_gb: int,
        limit_ip: int,
    ) -> XuiClientInfo:
        raise NotImplementedError

    @abstractmethod
    async def update_client(
        self,
        *,
        email: str,
        expiry_time: datetime,
        total_gb: int,
        limit_ip: int,
        enable: bool,
    ) -> XuiClientInfo:
        raise NotImplementedError

    @abstractmethod
    async def disable_client(self, email: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def enable_client(self, email: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_client(self, email: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_client_traffic(self, email: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def get_subscription_link(self, email: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def reset_client_ips(self, email: str) -> bool:
        raise NotImplementedError
