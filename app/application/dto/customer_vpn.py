from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class PanelOverview:
    name: str
    configured: bool
    status: str | None = None


@dataclass(slots=True)
class CustomerVpnOverview:
    account_id: int
    vpn_account_name: str
    status_label: str
    plan_name: str | None
    expiry_at: datetime | None
    days_left: int | None
    traffic_display: str
    traffic_limit_display: str
    ip_limit_display: str
    panels: list[PanelOverview]
    traffic_refresh_failed: bool = False
