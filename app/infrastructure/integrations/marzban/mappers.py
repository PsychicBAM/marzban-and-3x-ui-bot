from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.application.dto.vpn import VpnAccountResult, VpnStatusInfo, VpnTrafficInfo
from app.application.ports.marzban_port import MarzbanUserInfo


def gb_to_bytes(gb: int) -> int:
    if gb <= 0:
        return 0
    return gb * 1024 * 1024 * 1024


def bytes_to_gb(value: int) -> int:
    if value <= 0:
        return 0
    return int(value / (1024 * 1024 * 1024))


def unix_to_datetime(value: int | None) -> datetime | None:
    if not value or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def datetime_to_unix(value: datetime | None) -> int:
    if value is None:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp())


def extract_subscription_url(
    payload: dict[str, Any],
    *,
    subscription_base_url: str | None,
) -> str | None:
    direct = payload.get("subscription_url")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    links = payload.get("links") or []
    if links and isinstance(links[0], str):
        return links[0]

    if subscription_base_url:
        username = payload.get("username")
        if username:
            return f"{subscription_base_url.rstrip('/')}/{username}"

    return None


def map_user_info(
    payload: dict[str, Any],
    *,
    subscription_base_url: str | None,
) -> MarzbanUserInfo:
    expire = payload.get("expire")
    expire_at = unix_to_datetime(int(expire)) if expire is not None else None
    return MarzbanUserInfo(
        username=str(payload.get("username") or ""),
        status=str(payload.get("status") or "unknown"),
        expire_at=expire_at,
        subscription_url=extract_subscription_url(payload, subscription_base_url=subscription_base_url),
        used_traffic_bytes=int(payload.get("used_traffic") or 0),
        data_limit_bytes=int(payload.get("data_limit") or 0),
    )


def map_account_result(
    payload: dict[str, Any],
    *,
    subscription_base_url: str | None,
    traffic_limit_gb: int,
    ip_limit: int,
) -> VpnAccountResult:
    info = map_user_info(payload, subscription_base_url=subscription_base_url)
    return VpnAccountResult(
        panel="marzban",
        account_name=info.username,
        external_id=info.username,
        subscription_url=info.subscription_url,
        expire_at=info.expire_at,
        traffic_limit_gb=traffic_limit_gb,
        ip_limit=ip_limit,
        enabled=info.status == "active",
        raw=payload,
    )


def map_status_info(
    payload: dict[str, Any],
    *,
    subscription_base_url: str | None,
    ip_limit: int,
) -> VpnStatusInfo:
    info = map_user_info(payload, subscription_base_url=subscription_base_url)
    return VpnStatusInfo(
        panel="marzban",
        account_name=info.username,
        status=info.status,
        enabled=info.status == "active",
        expire_at=info.expire_at,
        used_traffic_bytes=info.used_traffic_bytes,
        traffic_limit_gb=bytes_to_gb(info.data_limit_bytes),
        ip_limit=ip_limit,
        subscription_url=info.subscription_url,
    )


def map_traffic_info(payload: dict[str, Any]) -> VpnTrafficInfo:
    used = int(payload.get("used_traffic") or 0)
    total = int(payload.get("data_limit") or 0)
    return VpnTrafficInfo(
        panel="marzban",
        account_name=str(payload.get("username") or ""),
        used_traffic_bytes=used,
        total_traffic_bytes=total or None,
        online=None,
    )
