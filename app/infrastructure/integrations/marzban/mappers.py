from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.application.dto.vpn import VpnAccountResult, VpnStatusInfo, VpnTrafficInfo
from app.application.ports.marzban_port import MarzbanUserInfo

logger = logging.getLogger(__name__)

_SUB_TOKEN_RE = re.compile(r"/sub/([^?#]+)", re.IGNORECASE)


def _extract_sub_token(url: str) -> str | None:
    match = _SUB_TOKEN_RE.search(url)
    if not match:
        return None
    token = match.group(1).strip("/")
    return token or None


def normalize_marzban_subscription_url(
    url: str | None,
    *,
    subscription_base_url: str | None,
    username: str | None = None,
) -> str | None:
    """Rebuild subscription URL using MARZBAN_SUBSCRIPTION_BASE_URL and /sub/{token}."""
    base = (subscription_base_url or "").strip().rstrip("/")
    if not base:
        return url.strip() if url and url.strip() else None

    raw = url.strip() if url and url.strip() else None
    token = _extract_sub_token(raw) if raw else None
    if not token:
        return raw

    if base.endswith("/sub"):
        normalized = f"{base}/{token}"
    else:
        normalized = f"{base}/sub/{token}"

    if raw != normalized:
        logger.info(
            "Marzban subscription URL normalized",
            extra={"username": username or ""},
        )
    return normalized


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
    raw: str | None = None
    direct = payload.get("subscription_url")
    if isinstance(direct, str) and direct.strip():
        raw = direct.strip()
    else:
        links = payload.get("links") or []
        if links and isinstance(links[0], str) and links[0].strip():
            raw = links[0].strip()

    username = str(payload.get("username") or "") or None
    base = (subscription_base_url or "").strip()
    if base:
        normalized = normalize_marzban_subscription_url(
            raw,
            subscription_base_url=base,
            username=username,
        )
        if normalized:
            return normalized

    return raw


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
