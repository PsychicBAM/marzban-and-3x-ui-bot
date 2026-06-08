from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "vpn_account_id",
            "notification_type",
            "reminder_days_before",
            name="uq_notifications_account_type_days",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    vpn_account_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_accounts.id"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reminder_days_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="notifications")
    vpn_account: Mapped["VpnAccount"] = relationship(back_populates="notifications")
