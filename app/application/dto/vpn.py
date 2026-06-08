from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class VpnCreateInput:
    account_name: str
    expire_at: datetime
    traffic_limit_gb: int
    ip_limit: int


@dataclass(slots=True)
class VpnAccountResult:
    panel: str
    account_name: str
    external_id: str
    subscription_url: str | None
    expire_at: datetime | None
    traffic_limit_gb: int
    ip_limit: int
    enabled: bool
    raw: dict | None = None


@dataclass(slots=True)
class VpnTrafficInfo:
    panel: str
    account_name: str
    used_traffic_bytes: int
    total_traffic_bytes: int | None
    online: bool | None = None


@dataclass(slots=True)
class VpnStatusInfo:
    panel: str
    account_name: str
    status: str
    enabled: bool
    expire_at: datetime | None
    used_traffic_bytes: int
    traffic_limit_gb: int
    ip_limit: int
    subscription_url: str | None


@dataclass(slots=True)
class VpnInboundInfo:
    panel: str
    inbound_id: int
    tag: str
    protocol: str
    port: int
    enabled: bool
    client_count: int
