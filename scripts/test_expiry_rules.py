"""
Development-only script to verify expiry calculation rules.

Usage:
    python scripts/test_expiry_rules.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

from app.application.services.expiry_calculator import ExpiryCalculator
from app.domain.enums import ProvisionAction, VpnAccountStatus


class FakeAccount:
    def __init__(
        self,
        *,
        status: str,
        expiry_date: datetime | None,
        deleted_at: datetime | None = None,
    ) -> None:
        self.status = status
        self.expiry_date = expiry_date
        self.deleted_at = deleted_at


def _run_case(name: str, account: FakeAccount | None, duration: int, expected_days_from_now: int) -> None:
    now = datetime.now(UTC)
    expiry, action = ExpiryCalculator.calculate(now=now, duration_days=duration, account=account)
    delta_days = round((expiry - now).total_seconds() / 86400)
    print(f"{name}: action={action.value}, days_from_now={delta_days}, expected~={expected_days_from_now}")
    assert abs(delta_days - expected_days_from_now) <= 1, f"Failed: {name}"


def main() -> None:
    now = datetime.now(UTC)

    _run_case("new user", None, 30, 30)

    active = FakeAccount(
        status=VpnAccountStatus.ACTIVE.value,
        expiry_date=now + timedelta(days=7),
    )
    _run_case("active 7d left + 30d plan", active, 30, 37)

    expired = FakeAccount(
        status=VpnAccountStatus.EXPIRED.value,
        expiry_date=now - timedelta(days=3),
    )
    _run_case("expired account + 30d", expired, 30, 30)

    deleted = FakeAccount(
        status=VpnAccountStatus.DELETED.value,
        expiry_date=now + timedelta(days=10),
        deleted_at=now,
    )
    _run_case("deleted account + 30d", deleted, 30, 30)

    disabled = FakeAccount(
        status=VpnAccountStatus.DISABLED.value,
        expiry_date=now + timedelta(days=5),
    )
    expiry, action = ExpiryCalculator.calculate(now=now, duration_days=30, account=disabled)
    delta_days = round((expiry - now).total_seconds() / 86400)
    print(f"disabled renew: action={action.value}, days_from_now={delta_days}, expected~=35")
    assert action == ProvisionAction.RENEW_REENABLE_DISABLED
    assert abs(delta_days - 35) <= 1

    print("All expiry rule checks passed.")


if __name__ == "__main__":
    main()
