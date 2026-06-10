from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class PromoApplyResult:
    promo_code_id: int
    code: str
    discount_type: str
    original_amount: Decimal
    discount_amount: Decimal
    final_amount: Decimal
    extra_days: int


@dataclass(slots=True)
class PromoCodeInfo:
    id: int
    code: str
    discount_type: str
    value: Decimal
    is_active: bool
    starts_at: datetime | None
    expires_at: datetime | None
    max_uses: int | None
    max_uses_per_user: int
    used_count: int
    min_amount: Decimal | None
    applies_to_plan_id: int | None
    applies_to_request_type: str | None
    new_users_only: bool
    created_at: datetime
