from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AdminReportSettings(Base):
    __tablename__ = "admin_report_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    report_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9, server_default="9")
    report_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
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
