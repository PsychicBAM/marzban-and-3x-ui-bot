from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NotificationSettings:
    enabled: bool
    reminder_days: list[int]
    check_interval: str
    test_mode: bool
    notify_expired_enabled: bool


@dataclass(slots=True)
class ExpiryNotificationJobResult:
    processed: int
    sent: int
    skipped: int
    failed: int
    test_mode: bool
