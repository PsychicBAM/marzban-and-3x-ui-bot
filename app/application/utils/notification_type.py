from __future__ import annotations

from app.domain.enums import NotificationType


def expiry_reminder_type(days: int) -> str:
    return f"expiry_{days}d"


def is_expired_type(notification_type: str) -> bool:
    return notification_type == NotificationType.EXPIRED.value
