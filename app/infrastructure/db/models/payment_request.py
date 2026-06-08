from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import PaymentRequestStatus, PaymentRequestType
from app.infrastructure.db.base import Base


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), nullable=False)
    vpn_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("vpn_accounts.id"),
        nullable=True,
        index=True,
    )
    request_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PaymentRequestType.PURCHASE.value,
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=PaymentRequestStatus.PENDING.value,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    receipt_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_file_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    receipt_message_id: Mapped[int | None] = mapped_column(nullable=True)
    user_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provisioning_error: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    user: Mapped["User"] = relationship(back_populates="payment_requests")
    plan: Mapped["Plan"] = relationship(back_populates="payment_requests")
    vpn_account: Mapped["VpnAccount | None"] = relationship(back_populates="payment_requests")
