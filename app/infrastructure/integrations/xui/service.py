from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.application.dto.vpn import VpnAccountResult, VpnCreateInput, VpnInboundInfo, VpnStatusInfo, VpnTrafficInfo
from app.application.exceptions import VpnPanelConflictError, VpnPanelError, VpnPanelNotFoundError
from app.application.ports.xui_port import XuiClientInfo, XuiPort
from app.application.utils.vpn_username import normalize_vpn_account_name
from app.config.settings import Settings
from app.infrastructure.integrations.xui.client import XuiApiClient
from app.infrastructure.integrations.xui.inbound_mutations import (
    ClientDeleteCriteria,
    ClientUpdateExpectation,
    find_client_matching_delete_criteria,
    inbound_id_value,
)
from app.infrastructure.integrations.xui.mappers import (
    build_client_payload,
    build_subscription_url,
    datetime_to_ms,
    find_client_in_inbound,
    gb_to_panel_bytes,
    map_account_result,
    map_client_info,
    map_inbound_info,
    map_status_info,
    map_traffic_info,
    normalize_xui_subscription_url,
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
        return self.normalize_subscription_url(
            None,
            sub_id=str(client.get("subId") or "") or None,
            email=str(client.get("email") or ""),
        )

    def normalize_subscription_url(
        self,
        url: str | None,
        *,
        sub_id: str | None = None,
        email: str | None = None,
    ) -> str | None:
        return normalize_xui_subscription_url(
            url,
            subscription_base_url=self._subscription_base,
            panel_base_url=self._settings.xui_base_url,
            sub_id=sub_id,
            email=email,
        )

    @staticmethod
    def _is_vless_inbound(inbound: dict[str, Any]) -> bool:
        return str(inbound.get("protocol") or "").lower() == "vless"

    def _resolve_vless_flow(
        self,
        inbound: dict[str, Any],
        existing_client: dict[str, Any] | None = None,
    ) -> str | None:
        if not self._is_vless_inbound(inbound):
            return None
        if existing_client is not None:
            existing_flow = str(existing_client.get("flow") or "").strip()
            if existing_flow:
                return existing_flow
        configured = (self._settings.xui_vless_flow or "").strip()
        return configured or None

    def _resolve_vless_flow_for_provision_update(
        self,
        inbound: dict[str, Any],
        existing_client: dict[str, Any],
    ) -> str | None:
        if not self._is_vless_inbound(inbound):
            return None
        configured = (self._settings.xui_vless_flow or "").strip()
        if configured:
            return configured
        existing_flow = str(existing_client.get("flow") or "").strip()
        return existing_flow or None

    @staticmethod
    def _log_vless_flow(flow: str | None) -> None:
        if flow:
            logger.info("VLESS flow applied: %s", flow)

    def _build_client_payload_for_account(
        self,
        *,
        inbound: dict[str, Any],
        account_name: str,
        data: VpnCreateInput,
        client_uuid: str,
        sub_id: str,
        existing_client: dict[str, Any] | None = None,
        provision_update: bool = False,
    ) -> dict[str, Any]:
        if provision_update and existing_client is not None:
            vless_flow = self._resolve_vless_flow_for_provision_update(inbound, existing_client)
        else:
            vless_flow = self._resolve_vless_flow(inbound, existing_client)
        return build_client_payload(
            email=account_name,
            client_uuid=client_uuid,
            sub_id=sub_id,
            expiry_ms=datetime_to_ms(data.expire_at),
            total_gb=data.traffic_limit_gb,
            limit_ip=data.ip_limit,
            enable=True,
            flow=vless_flow,
        )

    async def _reuse_existing_client(
        self,
        *,
        account_name: str,
        data: VpnCreateInput,
    ) -> VpnAccountResult:
        logger.info("3x-ui existing client reused", extra={"email": account_name})
        inbound = await self._client.get_inbound_raw(self._client.inbound_id)
        if inbound is None:
            raise VpnPanelNotFoundError(
                f"3x-ui inbound {self._client.inbound_id} not found",
                panel="xui",
            )
        existing = find_client_in_inbound(inbound, account_name)
        if existing is None:
            raise VpnPanelNotFoundError(
                f"3x-ui client '{account_name}' not found in inbound",
                panel="xui",
            )

        client_uuid = str(existing.get("id") or "").strip() or str(uuid.uuid4())
        sub_id = str(existing.get("subId") or "").strip() or self._client.generate_sub_id()
        client_payload = self._build_client_payload_for_account(
            inbound=inbound,
            account_name=account_name,
            data=data,
            client_uuid=client_uuid,
            sub_id=sub_id,
            existing_client=existing,
            provision_update=True,
        )
        self._log_vless_flow(client_payload.get("flow"))
        await self._client.update_existing_client_via_inbound(
            self._client.inbound_id,
            client_payload,
        )
        logger.info(
            "3x-ui existing client updated",
            extra={"email": account_name, "uuid": client_uuid},
        )
        subscription_url = build_subscription_url(
            sub_id=sub_id,
            subscription_base_url=self._subscription_base,
            panel_base_url=self._settings.xui_base_url,
            email=account_name,
        )
        return map_account_result(
            client_payload,
            subscription_url=subscription_url,
            traffic_limit_gb=data.traffic_limit_gb,
            ip_limit=data.ip_limit,
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
            return await self._reuse_existing_client(account_name=account_name, data=data)

        client_uuid = str(uuid.uuid4())
        sub_id = self._client.generate_sub_id()
        client_payload = self._build_client_payload_for_account(
            inbound=inbound,
            account_name=account_name,
            data=data,
            client_uuid=client_uuid,
            sub_id=sub_id,
        )
        self._log_vless_flow(client_payload.get("flow"))
        try:
            await self._client.add_client_raw(self._client.inbound_id, client_payload)
        except VpnPanelConflictError:
            return await self._reuse_existing_client(account_name=account_name, data=data)
        logger.info("3x-ui client created", extra={"email": account_name, "uuid": client_uuid})
        subscription_url = build_subscription_url(
            sub_id=sub_id,
            subscription_base_url=self._subscription_base,
            panel_base_url=self._settings.xui_base_url,
            email=account_name,
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
        inbound, existing = await self._load_client(account_name)
        vless_flow = self._resolve_vless_flow(inbound, existing)
        updated = build_client_payload(
            email=account_name,
            client_uuid=str(existing.get("id") or ""),
            sub_id=str(existing.get("subId") or self._client.generate_sub_id()),
            expiry_ms=datetime_to_ms(expiry_time),
            total_gb=total_gb,
            limit_ip=limit_ip,
            enable=enable,
            flow=vless_flow,
        )
        self._log_vless_flow(vless_flow)
        criteria = ClientDeleteCriteria(
            email=account_name,
            client_uuid=str(existing.get("id") or "") or None,
            sub_id=str(existing.get("subId") or "") or None,
        )
        expected = ClientUpdateExpectation(
            enable=enable,
            limit_ip=limit_ip,
            total_gb_bytes=gb_to_panel_bytes(total_gb),
            expiry_time_ms=datetime_to_ms(expiry_time),
            flow=vless_flow or None,
            flow_required=bool(vless_flow),
        )
        await self._client.update_client_raw(
            self._client.inbound_id,
            criteria,
            updated,
            expected=expected,
        )
        logger.info(
            "3x-ui client updated",
            extra={
                "email": account_name,
                "enable": enable,
                "update_method": self._client.last_client_update_method or "unknown",
            },
        )
        info = await self.get_client(account_name)
        if info is None:
            raise VpnPanelNotFoundError("3x-ui client updated but cannot be loaded", panel="xui")
        if info.enable != enable:
            raise VpnPanelError(
                f"3x-ui update verification failed: expected enable={enable} got {info.enable}",
                panel="xui",
            )
        if info.limit_ip != limit_ip:
            raise VpnPanelError(
                f"3x-ui update verification failed: expected limitIp={limit_ip} got {info.limit_ip}",
                panel="xui",
            )
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

    async def _build_delete_criteria(
        self,
        *,
        email: str,
        client_uuid: str | None = None,
        sub_id: str | None = None,
    ) -> ClientDeleteCriteria:
        account_name = normalize_vpn_account_name(email)
        lookup = ClientDeleteCriteria(
            email=account_name,
            client_uuid=client_uuid,
            sub_id=sub_id,
        )

        panel_client: dict[str, Any] | None = None
        for summary in await self._client.list_inbounds_raw():
            inbound_id = inbound_id_value(summary)
            if inbound_id is None:
                continue
            inbound = await self._client.get_inbound_raw(inbound_id)
            if inbound is None:
                continue
            panel_client = find_client_in_inbound(inbound, account_name)
            if panel_client is None:
                panel_client = find_client_matching_delete_criteria(inbound, lookup)
            if panel_client is not None:
                break

        resolved_uuid = (client_uuid or "").strip()
        if not resolved_uuid and panel_client is not None:
            resolved_uuid = str(panel_client.get("id") or panel_client.get("uuid") or "").strip()

        resolved_sub_id = (sub_id or "").strip()
        if not resolved_sub_id and panel_client is not None:
            resolved_sub_id = str(panel_client.get("subId") or "").strip()

        return ClientDeleteCriteria(
            email=account_name,
            client_uuid=resolved_uuid or None,
            sub_id=resolved_sub_id or None,
        )

    async def delete_client(
        self,
        email: str,
        *,
        client_uuid: str | None = None,
        sub_id: str | None = None,
    ) -> None:
        account_name = normalize_vpn_account_name(email)
        criteria = await self._build_delete_criteria(
            email=account_name,
            client_uuid=client_uuid,
            sub_id=sub_id,
        )
        await self._client.delete_client_everywhere(criteria)
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
        account_name = normalize_vpn_account_name(email)
        try:
            _, client = await self._load_client(account_name)
        except VpnPanelNotFoundError:
            return None
        return self.normalize_subscription_url(
            None,
            sub_id=str(client.get("subId") or "") or None,
            email=account_name,
        )

    async def reset_client_ips(self, email: str) -> bool:
        account_name = normalize_vpn_account_name(email)
        cleared = await self._client.clear_client_ips_raw(account_name)
        logger.info("3x-ui client IPs cleared", extra={"email": account_name, "ok": cleared})
        return cleared
