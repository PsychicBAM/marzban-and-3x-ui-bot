from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.application.dto.provisioning import PanelProvisionResult
from app.domain.enums import ProvisionAction


@dataclass(slots=True)
class ProvisionProfile:
    """VPN limits and issuing mode for manual or tariff-based creation."""

    name: str
    duration_days: int
    traffic_limit_gb: int
    ip_limit: int
    issuing_mode: str
    plan_id: int | None = None


@dataclass(slots=True)
class ManualProvisionRequest:
    mode: str
    user_id: int
    account_name: str
    profile: ProvisionProfile
    extend_existing: bool
    admin_comment: str | None = None
    target_telegram_id: int | None = None
    target_display_name: str | None = None


@dataclass(slots=True)
class ManualProvisionResult:
    success: bool
    partial: bool
    vpn_account_id: int | None
    vpn_account_name: str
    expiry_at: datetime
    action: ProvisionAction
    panel_results: list[PanelProvisionResult] = field(default_factory=list)
    subscription_links: dict[str, str] = field(default_factory=dict)
    profile: ProvisionProfile | None = None
    target_telegram_id: int | None = None
