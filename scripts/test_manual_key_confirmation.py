"""
Manual key flow confirmation with dict profile from FSM.

Usage:
    python scripts/test_manual_key_confirmation.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

from app.application.services.manual_key_flow_service import ManualKeyFlowService
from app.domain.enums import IssuingMode


class _FakeUow:
    pass


class _FakePlanService:
    pass


def main() -> None:
    service = ManualKeyFlowService(_FakeUow(), _FakePlanService())
    profile_dict = {
        "name": "Ручные параметры",
        "duration_days": 2,
        "traffic_limit_gb": 0,
        "ip_limit": 0,
        "issuing_mode": IssuingMode.BOTH.value,
        "plan_id": None,
    }
    preview = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    text = service.format_confirmation(
        {
            "mode": "standalone",
            "account_name": "testfortest",
            "profile": profile_dict,
            "preview_expiry": preview,
        },
    )
    assert "testfortest" in text
    assert "Безлимит" in text
    assert "Marzban + 3x-ui" in text
    request = service.build_request(
        {
            "mode": "standalone",
            "user_id": 1,
            "account_name": "testfortest",
            "profile": profile_dict,
            "extend_existing": False,
        },
    )
    assert request.profile.issuing_mode == IssuingMode.BOTH.value

    manual_only = {
        "mode": "standalone",
        "user_id": 1,
        "account_name": "testfortest",
        "custom_duration_days": 2,
        "custom_traffic_gb": 0,
        "custom_ip_limit": 0,
        "issuing_mode": IssuingMode.BOTH.value,
    }
    built = service.profile_dict_from_fsm_data(manual_only)
    assert built is not None
    assert built["duration_days"] == 2
    text2 = service.format_confirmation(
        {**manual_only, "profile": built, "preview_expiry": preview},
    )
    assert "testfortest" in text2
    request2 = service.build_request({**manual_only, "profile": built, "extend_existing": False})
    assert request2.profile.traffic_limit_gb == 0
    print("Manual key confirmation dict-profile test passed.")


if __name__ == "__main__":
    main()
