from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.application.dto.vpn import VpnAccountResult, VpnInboundInfo, VpnStatusInfo, VpnTrafficInfo
from app.application.ports.xui_port import XuiClientInfo


def ms_to_datetime(value: int | None) -> datetime | None:
    if not value or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def datetime_to_ms(value: datetime | None) -> int:
    if value is None:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp() * 1000)


def gb_to_panel_bytes(gb: int) -> int:
    if gb <= 0:
        return 0
    return gb * 1024 * 1024 * 1024


def panel_bytes_to_gb(value: int) -> int:
    if value <= 0:
        return 0
    return int(value / (1024 * 1024 * 1024))


def parse_inbound_settings(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def find_client_in_inbound(inbound: dict[str, Any], email: str) -> dict[str, Any] | None:
    settings = parse_inbound_settings(inbound.get("settings"))
    for client in settings.get("clients", []):
        if str(client.get("email", "")).lower() == email.lower():
            return client
    return None


def build_client_payload(
    *,
    email: str,
    client_uuid: str,
    sub_id: str,
    expiry_ms: int,
    total_gb: int,
    limit_ip: int,
    enable: bool,
) -> dict[str, Any]:
    return {
        "id": client_uuid,
        "email": email,
        "limitIp": limit_ip,
        "totalGB": gb_to_panel_bytes(total_gb),
        "expiryTime": expiry_ms,
        "enable": enable,
        "tgId": "",
        "subId": sub_id,
        "flow": "",
        "reset": 0,
    }


def map_client_info(
    client: dict[str, Any],
    *,
    subscription_url: str | None,
) -> XuiClientInfo:
    total_bytes = int(client.get("totalGB") or 0)
    return XuiClientInfo(
        client_uuid=str(client.get("id") or ""),
        email=str(client.get("email") or ""),
        enable=bool(client.get("enable", True)),
        expiry_time=ms_to_datetime(int(client.get("expiryTime") or 0)),
        total_gb=panel_bytes_to_gb(total_bytes),
        limit_ip=int(client.get("limitIp") or 0),
        used_traffic_bytes=0,
        subscription_url=subscription_url,
    )


def build_subscription_url(
    *,
    sub_id: str | None,
    subscription_base_url: str | None,
    panel_base_url: str,
) -> str | None:
    if not sub_id:
        return None
    if subscription_base_url:
        return f"{subscription_base_url.rstrip('/')}/{sub_id}"
    return f"{panel_base_url.rstrip('/')}/sub/{sub_id}"


def map_account_result(
    client: dict[str, Any],
    *,
    subscription_url: str | None,
    traffic_limit_gb: int,
    ip_limit: int,
) -> VpnAccountResult:
    info = map_client_info(client, subscription_url=subscription_url)
    return VpnAccountResult(
        panel="xui",
        account_name=info.email,
        external_id=info.client_uuid,
        subscription_url=info.subscription_url,
        expire_at=info.expiry_time,
        traffic_limit_gb=traffic_limit_gb,
        ip_limit=ip_limit,
        enabled=info.enable,
        raw=client,
    )


def map_status_info(
    client: dict[str, Any],
    *,
    subscription_url: str | None,
) -> VpnStatusInfo:
    info = map_client_info(client, subscription_url=subscription_url)
    status = "active" if info.enable else "disabled"
    return VpnStatusInfo(
        panel="xui",
        account_name=info.email,
        status=status,
        enabled=info.enable,
        expire_at=info.expiry_time,
        used_traffic_bytes=info.used_traffic_bytes,
        traffic_limit_gb=info.total_gb,
        ip_limit=info.limit_ip,
        subscription_url=info.subscription_url,
    )


def map_traffic_info(email: str, payload: dict[str, Any], *, online: bool | None) -> VpnTrafficInfo:
    up = int(payload.get("up") or payload.get("upload") or 0)
    down = int(payload.get("down") or payload.get("download") or 0)
    total_limit = int(payload.get("total") or 0)
    return VpnTrafficInfo(
        panel="xui",
        account_name=email,
        used_traffic_bytes=up + down,
        total_traffic_bytes=total_limit or None,
        online=online,
    )


def map_inbound_info(inbound: dict[str, Any]) -> VpnInboundInfo:
    settings = parse_inbound_settings(inbound.get("settings"))
    clients = settings.get("clients", [])
    return VpnInboundInfo(
        panel="xui",
        inbound_id=int(inbound.get("id") or 0),
        tag=str(inbound.get("remark") or inbound.get("tag") or ""),
        protocol=str(inbound.get("protocol") or ""),
        port=int(inbound.get("port") or 0),
        enabled=bool(inbound.get("enable", True)),
        client_count=len(clients) if isinstance(clients, list) else 0,
    )
