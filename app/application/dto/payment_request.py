from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class PaymentRequestInfo:
    id: int
    user_id: int
    plan_id: int
    request_type: str
    status: str
    amount: Decimal
    receipt_file_id: str | None
    receipt_file_type: str | None
    user_comment: str | None
    created_at: datetime
    approved_at: datetime | None
    rejected_at: datetime | None
    processed_by_telegram_id: int | None

    user_full_name: str
    username: str | None
    telegram_id: int

    plan_name: str
    plan_duration_days: int
    plan_traffic_limit_gb: int
    plan_ip_limit: int
    plan_issuing_mode: str
    vpn_account_id: int | None = None
    current_expiry_at: datetime | None = None
    expected_expiry_at: datetime | None = None
