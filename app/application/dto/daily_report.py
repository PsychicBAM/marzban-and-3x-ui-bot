from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.application.dto.system_status import PanelStatusLine


@dataclass(frozen=True)
class DailyReportSnapshot:
    database_ok: bool
    database_error: str | None
    marzban: PanelStatusLine
    xui: PanelStatusLine
    total_users: int
    active_subscriptions: int
    expiring_in_3_days: int
    expired_subscriptions: int
    pending_payments: int
    open_support_tickets: int
    referrals_today: int
    promo_redemptions_today: int
    broadcasts_today: int
    revenue_today: Decimal
    revenue_7_days: Decimal
    last_backup: str | None
    generated_at_label: str
