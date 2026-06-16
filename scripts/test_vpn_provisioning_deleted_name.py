"""
Regression: new purchase reuses panel users after deleted historical vpn_account.

Usage:
    python scripts/test_vpn_provisioning_deleted_name.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

from app.application.dto.provisioning import PanelProvisionResult
from app.application.exceptions import VpnPanelConflictError
from app.application.ports.marzban_port import MarzbanUserInfo
from app.application.services.vpn_provisioning_service import VpnProvisioningService
from app.domain.enums import IssuingMode, PaymentRequestType, VpnAccountStatus
from app.infrastructure.integrations.xui.mappers import map_client_info


@dataclass
class FakeVpnAccount:
    id: int
    user_id: int
    vpn_account_name: str
    status: str = VpnAccountStatus.ACTIVE.value
    deleted_at: datetime | None = None
    marzban_username: str | None = None
    marzban_subscription_url: str | None = None
    marzban_status: str | None = None
    xui_email: str | None = None
    xui_client_uuid: str | None = None
    xui_subscription_url: str | None = None
    xui_status: str | None = None
    expiry_date: datetime | None = None
    plan_id: int | None = None
    traffic_limit_gb: int = 0
    ip_limit: int = 1
    display_name: str | None = None
    is_primary: bool = False


@dataclass
class FakeVpnAccountRepo:
    accounts: dict[int, FakeVpnAccount] = field(default_factory=dict)
    _next_id: int = 1

    async def get_active_by_name(self, name: str) -> FakeVpnAccount | None:
        for account in self.accounts.values():
            if account.vpn_account_name == name and account.status != VpnAccountStatus.DELETED.value:
                return account
        return None

    async def count_deleted_by_name(self, name: str) -> int:
        return sum(
            1
            for account in self.accounts.values()
            if account.vpn_account_name == name and account.status == VpnAccountStatus.DELETED.value
        )

    async def get_renewal_candidate(self, user_id: int, *, vpn_account_id: int | None = None) -> FakeVpnAccount | None:
        return None

    async def has_active_vpn(self, user_id: int) -> bool:
        return False

    async def count_non_deleted_for_user(self, user_id: int) -> int:
        return sum(
            1
            for account in self.accounts.values()
            if account.user_id == user_id and account.status != VpnAccountStatus.DELETED.value
        )

    async def get_by_id(self, account_id: int) -> FakeVpnAccount | None:
        return self.accounts.get(account_id)

    async def create(self, **kwargs) -> FakeVpnAccount:
        account = FakeVpnAccount(id=self._next_id, **kwargs)
        self._next_id += 1
        self.accounts[account.id] = account
        return account

    async def update_provision(self, account: FakeVpnAccount, **kwargs) -> FakeVpnAccount:
        for key, value in kwargs.items():
            if value is not None and hasattr(account, key):
                setattr(account, key, value)
        return account


class FakeUow:
    def __init__(self, repo: FakeVpnAccountRepo) -> None:
        self.vpn_accounts = repo
        self.session = SimpleNamespace(begin_nested=lambda: _NullContext())


class _NullContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeMarzban:
    def __init__(self, username: str, subscription_url: str) -> None:
        self._username = username
        self._url = subscription_url
        self.create_user = AsyncMock(side_effect=self._create_conflict)
        self.get_user = AsyncMock(side_effect=self._get_user)
        self.update_user = AsyncMock(side_effect=self._update_user)
        self.get_subscription_link = AsyncMock(return_value=subscription_url)

    async def _get_user(self, username: str) -> MarzbanUserInfo | None:
        if username != self._username:
            return None
        return MarzbanUserInfo(
            username=username,
            subscription_url=self._url,
            status="active",
            used_traffic_bytes=0,
            data_limit_bytes=0,
            expire_at=datetime.now(UTC) + timedelta(days=30),
        )

    async def _create_conflict(self, **kwargs: object) -> MarzbanUserInfo:
        raise VpnPanelConflictError("exists", panel="marzban")

    async def _update_user(self, **kwargs: object) -> MarzbanUserInfo:
        username = str(kwargs.get("username") or self._username)
        return MarzbanUserInfo(
            username=username,
            subscription_url=self._url,
            status="active",
            used_traffic_bytes=0,
            data_limit_bytes=0,
            expire_at=kwargs.get("expire_at") or datetime.now(UTC) + timedelta(days=30),
        )


class FakeXui:
    def __init__(self, email: str, subscription_url: str) -> None:
        self._email = email
        self._url = subscription_url
        self.create_client = AsyncMock(side_effect=self._create_client)
        self.update_client = AsyncMock(side_effect=self._update_client)

    async def _create_client(self, **kwargs: object) -> object:
        email = str(kwargs.get("email") or self._email)
        client = {
            "id": "uuid-1",
            "email": email,
            "subId": "sub-1",
            "enable": True,
        }
        return map_client_info(client, subscription_url=self._url)

    async def _update_client(self, **kwargs: object) -> object:
        return await self._create_client(**kwargs)


async def run_scenario() -> None:
    deleted = FakeVpnAccount(
        id=1,
        user_id=10,
        vpn_account_name="abdallahbahi_old_1",
        status=VpnAccountStatus.DELETED.value,
        deleted_at=datetime.now(UTC),
        marzban_username="abdallahbahi",
        marzban_status="active",
    )
    repo = FakeVpnAccountRepo(accounts={1: deleted})
    uow = FakeUow(repo)

    marzban_url = "https://panel.example/sub/token123"
    xui_url = "https://ui.example/vpn/sub-1"
    marzban = FakeMarzban("abdallahbahi", marzban_url)
    xui = FakeXui("abdallahbahi", xui_url)

    settings = SimpleNamespace(
        marzban_enabled=True,
        xui_enabled=True,
    )
    service = VpnProvisioningService(uow=uow, settings=settings, marzban=marzban, xui=xui)

    user = SimpleNamespace(id=10, username="abdallahbahi", vpn_account_name=None, telegram_id=123)
    plan = SimpleNamespace(
        id=1,
        name="Test",
        duration_days=30,
        traffic_limit_gb=100,
        ip_limit=2,
        issuing_mode=IssuingMode.BOTH.value,
    )
    request = SimpleNamespace(
        id=8,
        user=user,
        plan=plan,
        request_type=PaymentRequestType.PURCHASE.value,
        target_vpn_account_name=None,
        target_display_name=None,
        vpn_account_id=None,
        extra_days_from_promo=0,
    )

    result = await service.provision_for_payment_request(request)

    assert not result.partial, f"expected full success, panels={result.panel_results}"
    assert result.vpn_account_id is not None
    saved = repo.accounts[result.vpn_account_id]
    assert saved.vpn_account_name == "abdallahbahi"
    assert saved.marzban_username == "abdallahbahi"
    assert saved.marzban_subscription_url == marzban_url
    assert saved.marzban_status == "active"
    assert saved.xui_email == "abdallahbahi"
    assert saved.xui_subscription_url == xui_url
    assert saved.xui_status == "active"
    assert result.subscription_links["Marzban"] == marzban_url
    assert result.subscription_links["3x-ui"] == xui_url
    marzban.get_user.assert_awaited()
    marzban.update_user.assert_awaited()
    print("Regression passed: deleted historical name reuse persists Marzban and 3x-ui URLs.")


def main() -> None:
    asyncio.run(run_scenario())


if __name__ == "__main__":
    main()
