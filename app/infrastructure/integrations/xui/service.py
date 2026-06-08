from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.application.dto.vpn import VpnAccountResult, VpnCreateInput, VpnInboundInfo, VpnStatusInfo, VpnTrafficInfo
from app.application.exceptions import VpnPanelConflictError, VpnPanelNotFoundError
from app.application.ports.xui_port import XuiClientInfo, XuiPort
from app.application.utils.vpn_username import normalize_vpn_account_name
from app.config.settings import Settings
from app.infrastructure.integrations.xui.client import XuiApiClient
from app.infrastructure.integrations.xui.mappers import (
    build_client_payload,
    build_subscription_url,
    datetime_to_ms,
    find_client_in_inbound,
    map_account_result,
    map_client_info,
    map_inbound_info,
    map_status_info,
    map_traffic_info,
)

logger = logging.getLogger(__name__)


class XuiService(XuiPort):
    """Business-level 3x-ui operations."""

    def __init__(self, client: XuiApiClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._subscription_base = settings.xui_subscription_base_url or None

    async def list_inbounds(self) -> list[VpnInboundInfo]:
        inbounds = await self._client.list_inbounds_raw()
        return [map_inbound_info(item) for item in inbounds]

    async def get_inbound(self, inbound_id: int | None = None) -> VpnInboundInfo | None:
        target_id = inbound_id or self._client.inbound_id
        inbound = await self._client.get_inbound_raw(target_id)
        if inbound is None:
            return None
        return map_inbound_info(inbound)

    async def _load_client(self, email: str) -> tuple[dict[str, Any], dict[str, Any]]:
        account_name = normalize_vpn_account_name(email)
        inbound = await self._client.get_inbound_raw(self._client.inbound_id)
        if inbound is None:
            raise VpnPanelNotFoundError(
                f"3x-ui inbound {self._client.inbound_id} not found",
                panel="xui",
            )
        client = find_client_in_inbound(inbound, account_name)
        if client is None:
            raise VpnPanelNotFoundError(f"3x-ui client '{account_name}' not found", panel="xui")
        return inbound, client

    def _subscription_for_client(self, client: dict[str, Any]) -> str | None:
        return build_subscription_url(
            sub_id=str(client.get("subId") or "") or None,
            subscription_base_url=self._subscription_base,
            panel_base_url=self._settings.xui_base_url,
        )

    async def get_client(self, email: str) -> XuiClientInfo | None:
        account_name = normalize_vpn_account_name(email)
        inbound = await self._client.get_inbound_raw(self._client.inbound_id)
        if inbound is None:
            return None
        client = find_client_in_inbound(inbound, account_name)
        if client is None:
            return None
        traffic = await self._client.get_client_traffic_raw(account_name)
        info = map_client_info(client, subscription_url=self._subscription_for_client(client))
        if traffic:
            up = int(traffic.get("up") or 0)
            down = int(traffic.get("down") or 0)
            info.used_traffic_bytes = up + down
        return info

    async def get_status(self, email: str) -> VpnStatusInfo | None:
        try:
            _, client = await self._load_client(email)
        except VpnPanelNotFoundError:
            return None
        return map_status_info(client, subscription_url=self._subscription_for_client(client))

    async def create_client(
        self,
        *,
        email: str,
        expiry_time: datetime,
        total_gb: int,
        limit_ip: int,
    ) -> XuiClientInfo:
        result = await self.create_account(
            VpnCreateInput(
                account_name=email,
                expire_at=expiry_time,
                traffic_limit_gb=total_gb,
                ip_limit=limit_ip,
            ),
        )
        info = await self.get_client(result.account_name)
        if info is None:
            raise VpnPanelNotFoundError("3x-ui client was created but cannot be loaded", panel="xui")
        return info

    async def create_account(self, data: VpnCreateInput) -> VpnAccountResult:
        account_name = normalize_vpn_account_name(data.account_name)
        inbound = await self._client.get_inbound_raw(self._client.inbound_id)
        if inbound is None:
            raise VpnPanelNotFoundError(
                f"3x-ui inbound {self._client.inbound_id} not found",
                panel="xui",
            )

        if find_client_in_inbound(inbound, account_name) is not None:
            raise VpnPanelConflictError(
                f"3x-ui client '{account_name}' already exists",
                panel="xui",
            )

        client_uuid = str(uuid.uuid4())
        sub_id = self._client.generate_sub_id()
        client_payload = build_client_payload(
            email=account_name,
            client_uuid=client_uuid,
            sub_id=sub_id,
            expiry_ms=datetime_to_ms(data.expire_at),
            total_gb=data.traffic_limit_gb,
            limit_ip=data.ip_limit,
            enable=True,
        )
        await self._client.add_client_raw(self._client.inbound_id, client_payload)
        logger.info("3x-ui client created", extra={"email": account_name, "uuid": client_uuid})
        subscription_url = build_subscription_url(
            sub_id=sub_id,
            subscription_base_url=self._subscription_base,
            panel_base_url=self._settings.xui_base_url,
        )
        return map_account_result(
            client_payload,
            subscription_url=subscription_url,
            traffic_limit_gb=data.traffic_limit_gb,
            ip_limit=data.ip_limit,
        )

    async def update_client(
        self,
        *,
        email: str,
        expiry_time: datetime,
        total_gb: int,
        limit_ip: int,
        enable: bool,
    ) -> XuiClientInfo:
        account_name = normalize_vpn_account_name(email)
        _, existing = await self._load_client(account_name)
        updated = build_client_payload(
            email=account_name,
            client_uuid=str(existing.get("id") or ""),
            sub_id=str(existing.get("subId") or self._client.generate_sub_id()),
            expiry_ms=datetime_to_ms(expiry_time),
            total_gb=total_gb,
            limit_ip=limit_ip,
            enable=enable,
        )
        await self._client.update_client_raw(
            self._client.inbound_id,
            str(existing.get("id") or ""),
            updated,
        )
        logger.info("3x-ui client updated", extra={"email": account_name, "enable": enable})
        info = await self.get_client(account_name)
        if info is None:
            raise VpnPanelNotFoundError("3x-ui client updated but cannot be loaded", panel="xui")
        return info

    async def disable_client(self, email: str) -> None:
        info = await self.get_client(email)
        if info is None:
            raise VpnPanelNotFoundError(f"3x-ui client '{email}' not found", panel="xui")
        await self.update_client(
            email=email,
            expiry_time=info.expiry_time or datetime.now(UTC),
            total_gb=info.total_gb,
            limit_ip=info.limit_ip,
            enable=False,
        )

    async def enable_client(self, email: str) -> None:
        info = await self.get_client(email)
        if info is None:
            raise VpnPanelNotFoundError(f"3x-ui client '{email}' not found", panel="xui")
        await self.update_client(
            email=email,
            expiry_time=info.expiry_time or datetime.now(UTC),
            total_gb=info.total_gb,
            limit_ip=info.limit_ip,
            enable=True,
        )

    async def delete_client(self, email: str) -> None:
        account_name = normalize_vpn_account_name(email)
        _, client = await self._load_client(account_name)
        await self._client.delete_client_raw(
            self._client.inbound_id,
            str(client.get("id") or ""),
        )
        logger.info("3x-ui client deleted", extra={"email": account_name})

    async def get_client_traffic(self, email: str) -> int:
        account_name = normalize_vpn_account_name(email)
        traffic = await self.get_traffic(account_name)
        return traffic.used_traffic_bytes if traffic else 0

    async def get_traffic(self, email: str) -> VpnTrafficInfo | None:
        account_name = normalize_vpn_account_name(email)
        payload = await self._client.get_client_traffic_raw(account_name)
        if payload is None:
            return None
        online_list = await self._client.list_online_clients_raw()
        online = account_name in online_list
        return map_traffic_info(account_name, payload, online=online)

    async def get_subscription_link(self, email: str) -> str | None:
        info = await self.get_client(email)
        return info.subscription_url if info else None

    async def reset_client_ips(self, email: str) -> bool:
        account_name = normalize_vpn_account_name(email)
        cleared = await self._client.clear_client_ips_raw(account_name)
        logger.info("3x-ui client IPs cleared", extra={"email": account_name, "ok": cleared})
        return cleared
