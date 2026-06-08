from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(slots=True)
class UserVpnCounts:
    total_users: int
    active_vpn: int
    expired_vpn: int
    disabled_vpn: int
    deleted_vpn: int


@dataclass(slots=True)
class PaymentStatusCounts:
    pending: int
    approved: int
    rejected: int
    provisioning_failed: int
    provisioning_partial: int


@dataclass(slots=True)
class RevenueSummary:
    total: Decimal
    today: Decimal
    month: Decimal
    by_plan: list[tuple[str, Decimal]] = field(default_factory=list)


@dataclass(slots=True)
class VpnAccountCounts:
    total: int
    active: int
    expired: int
    disabled: int
    deleted: int
    marzban: int
    xui: int


@dataclass(slots=True)
class ExpiringSoonCounts:
    in_1_day: int
    in_3_days: int
    in_7_days: int


@dataclass(slots=True)
class StatisticsSnapshot:
    users: UserVpnCounts
    payments: PaymentStatusCounts
    revenue: RevenueSummary
    vpn_accounts: VpnAccountCounts
    expiring: ExpiringSoonCounts
    generated_at_label: str
