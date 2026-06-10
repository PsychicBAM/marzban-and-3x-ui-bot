from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class ReferralSettingsInfo:
    is_enabled: bool
    reward_days_per_paid_referral: int
    milestone_paid_referrals: int
    milestone_reward_days: int
    min_purchase_amount: Decimal
    count_only_first_paid_purchase: bool
    allow_zero_amount_rewards: bool
    apply_reward_automatically: bool


@dataclass(slots=True)
class ReferralCustomerStats:
    referral_code: str
    referral_link: str
    invited_count: int
    paid_referrals_count: int
    earned_bonus_days: int
    pending_bonus_days: int
    milestone_target: int
    milestone_progress: int


@dataclass(slots=True)
class ReferralRewardInfo:
    id: int
    reward_type: str
    reward_days: int
    status: str
    referred_name: str | None
    created_at: datetime
    applied_at: datetime | None


@dataclass(slots=True)
class ReferralNotification:
    telegram_id: int
    message: str


@dataclass(slots=True)
class ReferralProcessOutcome:
    notifications: list[ReferralNotification]
