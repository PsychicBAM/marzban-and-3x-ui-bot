from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class VpnUserStats:
    total_users: int
    active_vpn: int
    expired_vpn: int
    disabled_vpn: int
    deleted_vpn: int


@dataclass(slots=True)
class ClientListItem:
    user_id: int
    telegram_id: int
    display_name: str
    username: str | None
    vpn_account_id: int | None
    vpn_status_label: str
    expiry_at: datetime | None
    has_marzban: bool
    has_xui: bool


@dataclass(slots=True)
class PanelStatusInfo:
    panel: str
    state: str


@dataclass(slots=True)
class ClientCardInfo:
    user_id: int
    telegram_id: int
    full_name: str
    username: str | None
    registered_at: datetime
    latest_payment_status: str | None
    vpn_account_id: int | None
    vpn_account_name: str | None
    plan_name: str | None
    status_label: str
    expiry_at: datetime | None
    days_left: int | None
    traffic_display: str
    traffic_limit_display: str
    ip_limit_display: str
    panel_statuses: list[PanelStatusInfo]
    traffic_refresh_failed: bool = False
    is_deleted: bool = False


@dataclass(slots=True)
class PanelActionResult:
    panel: str
    success: bool
    detail: str


@dataclass(slots=True)
class AdminCustomerActionOutcome:
    success: bool
    admin_message: str
    panel_results: list[PanelActionResult] = field(default_factory=list)
    customer_message: str | None = None
    customer_telegram_id: int | None = None
    qr_deliveries: list | None = None
