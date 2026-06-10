from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import VpnAccountStatus
from app.infrastructure.db.base import Base


class VpnAccount(Base):
    __tablename__ = "vpn_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    vpn_account_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=VpnAccountStatus.ACTIVE.value,
        index=True,
    )
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    traffic_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    traffic_limit_gb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ip_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    marzban_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    marzban_subscription_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    marzban_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    xui_client_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    xui_email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    xui_subscription_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    xui_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    user: Mapped["User"] = relationship(back_populates="vpn_accounts")
    plan: Mapped["Plan | None"] = relationship(back_populates="vpn_accounts")
    payment_requests: Mapped[list["PaymentRequest"]] = relationship(back_populates="vpn_account")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="vpn_account")
