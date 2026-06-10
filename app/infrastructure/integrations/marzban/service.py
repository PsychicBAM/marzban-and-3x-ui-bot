from __future__ import annotations

import logging
from datetime import datetime

from app.application.dto.vpn import VpnAccountResult, VpnCreateInput, VpnStatusInfo, VpnTrafficInfo
from app.application.exceptions import VpnPanelConflictError, VpnPanelNotFoundError
from app.application.ports.marzban_port import MarzbanPort, MarzbanUserInfo
from app.application.utils.vpn_username import normalize_vpn_account_name
from app.config.settings import Settings
from app.infrastructure.integrations.marzban.client import MarzbanApiClient
from app.infrastructure.integrations.marzban.mappers import (
    datetime_to_unix,
    gb_to_bytes,
    map_account_result,
    map_status_info,
    map_traffic_info,
    map_user_info,
    normalize_marzban_subscription_url,
)
from app.infrastructure.integrations.marzban.verification import (
    require_user_payload,
    verify_marzban_ip_limit,
    verify_marzban_status,
)

logger = logging.getLogger(__name__)


class MarzbanService(MarzbanPort):
    """Business-level Marzban operations."""

    def __init__(self, client: MarzbanApiClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._subscription_base = settings.marzban_subscription_base_url or None

    async def _load_user_raw_required(self, username: str) -> dict:
        account_name = normalize_vpn_account_name(username)
        payload = await self._client.get_user_raw(account_name)
        return require_user_payload(payload, username=account_name)

    async def _verify_user_on_panel(
        self,
        username: str,
        *,
        expected_active: bool | None = None,
        expected_ip_limit: int | None = None,
    ) -> None:
        payload = await self._load_user_raw_required(username)
        if expected_active is not None:
            verify_marzban_status(payload, expected_active=expected_active)
        if expected_ip_limit is not None:
            verify_marzban_ip_limit(payload, expected=expected_ip_limit)

    async def get_user(self, username: str) -> MarzbanUserInfo | None:
        account_name = normalize_vpn_account_name(username)
        payload = await self._client.get_user_raw(account_name)
        if payload is None:
            return None
        return map_user_info(payload, subscription_base_url=self._subscription_base)

    async def get_status(self, username: str) -> VpnStatusInfo | None:
        account_name = normalize_vpn_account_name(username)
        payload = await self._client.get_user_raw(account_name)
        if payload is None:
            return None
        ip_limit = int(payload.get("limit_ip") or 0)
        return map_status_info(payload, subscription_base_url=self._subscription_base, ip_limit=ip_limit)

    async def get_traffic(self, username: str) -> VpnTrafficInfo | None:
        account_name = normalize_vpn_account_name(username)
        payload = await self._client.get_user_raw(account_name)
        if payload is None:
            return None
        return map_traffic_info(payload)

    async def create_user(
        self,
        *,
        username: str,
        expire_at: datetime,
        data_limit_gb: int,
        ip_limit: int,
    ) -> MarzbanUserInfo:
        result = await self.create_account(
            VpnCreateInput(
                account_name=username,
                expire_at=expire_at,
                traffic_limit_gb=data_limit_gb,
                ip_limit=ip_limit,
            ),
        )
        info = await self.get_user(result.account_name)
        if info is None:
            raise VpnPanelNotFoundError("Marzban user was created but cannot be loaded", panel="marzban")
        return info

    async def create_account(self, data: VpnCreateInput) -> VpnAccountResult:
        account_name = normalize_vpn_account_name(data.account_name)
        existing = await self._client.get_user_raw(account_name)
        if existing is not None:
            raise VpnPanelConflictError(
                f"Marzban user '{account_name}' already exists",
                panel="marzban",
            )

        vless_flow = (self._settings.marzban_vless_flow or "").strip() or None
        payload = self._client.build_user_payload(
            username=account_name,
            expire_unix=datetime_to_unix(data.expire_at),
            data_limit_bytes=gb_to_bytes(data.traffic_limit_gb),
            status="active",
            ip_limit=data.ip_limit,
            vless_flow=vless_flow,
        )
        created = await self._client.create_user_raw(payload)
        if vless_flow:
            logger.info("VLESS flow applied: %s", vless_flow)
        logger.info("Marzban user created", extra={"username": account_name})
        return map_account_result(
            created,
            subscription_base_url=self._subscription_base,
            traffic_limit_gb=data.traffic_limit_gb,
            ip_limit=data.ip_limit,
        )

    async def update_user(
        self,
        *,
        username: str,
        expire_at: datetime,
        data_limit_gb: int,
        ip_limit: int,
        enable: bool,
        verify_ip_limit: bool = False,
    ) -> MarzbanUserInfo:
        account_name = normalize_vpn_account_name(username)
        vless_flow = (self._settings.marzban_vless_flow or "").strip() or None
        payload = self._client.build_user_payload(
            username=account_name,
            expire_unix=datetime_to_unix(expire_at),
            data_limit_bytes=gb_to_bytes(data_limit_gb),
            status="active" if enable else "disabled",
            ip_limit=ip_limit,
            vless_flow=vless_flow,
        )
        payload.pop("username", None)
        await self._client.modify_user_raw(account_name, payload)
        await self._verify_user_on_panel(
            account_name,
            expected_active=enable,
            expected_ip_limit=ip_limit if verify_ip_limit else None,
        )
        if vless_flow:
            logger.info("VLESS flow applied: %s", vless_flow)
        logger.info("Marzban user updated", extra={"username": account_name, "enable": enable})
        verified = await self._load_user_raw_required(account_name)
        return map_user_info(verified, subscription_base_url=self._subscription_base)

    async def disable_user(self, username: str) -> None:
        account_name = normalize_vpn_account_name(username)
        await self._client.modify_user_raw(account_name, {"status": "disabled"})
        await self._verify_user_on_panel(account_name, expected_active=False)
        logger.info("Marzban user disabled", extra={"username": account_name})

    async def enable_user(self, username: str) -> None:
        account_name = normalize_vpn_account_name(username)
        await self._client.modify_user_raw(account_name, {"status": "active"})
        await self._verify_user_on_panel(account_name, expected_active=True)
        logger.info("Marzban user enabled", extra={"username": account_name})

    async def delete_user(self, username: str) -> None:
        account_name = normalize_vpn_account_name(username)
        await self._client.delete_user_raw(account_name)
        logger.info("Marzban user deleted", extra={"username": account_name})

    async def get_subscription_link(self, username: str) -> str | None:
        info = await self.get_user(username)
        if info is None:
            return None
        return self.normalize_subscription_url(info.subscription_url, username=info.username)

    def normalize_subscription_url(
        self,
        url: str | None,
        *,
        username: str | None = None,
    ) -> str | None:
        return normalize_marzban_subscription_url(
            url,
            subscription_base_url=self._subscription_base,
            username=username,
        )

    async def reset_user_ips(self, username: str) -> bool:
        account_name = normalize_vpn_account_name(username)
        reset = await self._client.reset_user_usage_raw(account_name)
        logger.info("Marzban user reset requested", extra={"username": account_name, "ok": reset})
        return reset
