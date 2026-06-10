from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.user import User


class ReferralSettings(Base):
    __tablename__ = "referral_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reward_days_per_paid_referral: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    milestone_paid_referrals: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    milestone_reward_days: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    min_purchase_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    count_only_first_paid_purchase: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_zero_amount_rewards: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    apply_reward_automatically: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ReferralEvent(Base):
    __tablename__ = "referral_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(32), default="link", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="registered", nullable=False)
    payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    referrer: Mapped["User"] = relationship(foreign_keys=[referrer_user_id])
    referred: Mapped["User"] = relationship(foreign_keys=[referred_user_id])


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    referred_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    reward_type: Mapped[str] = mapped_column(String(16), nullable=False)
    reward_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    applied_vpn_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("vpn_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    referrer: Mapped["User"] = relationship(foreign_keys=[referrer_user_id])
