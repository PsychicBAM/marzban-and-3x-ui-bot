"""
Development-only script to test Marzban user creation.

Usage:
    python scripts/test_marzban_create_user.py --username testuser --days 30

Requires .env with MARZBAN_* variables. Never commit real credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.dto.vpn import VpnCreateInput
from app.application.exceptions import VpnPanelError
from app.config.settings import get_settings
from app.infrastructure.integrations.factory import create_marzban_service


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test Marzban create user")
    parser.add_argument("--username", required=True, help="VPN account name")
    parser.add_argument("--days", type=int, default=30, help="Expiry in days")
    parser.add_argument("--traffic-gb", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--ip-limit", type=int, default=3, help="0 = unlimited")
    parser.add_argument("--delete", action="store_true", help="Delete user after test")
    args = parser.parse_args()

    settings = get_settings()
    service = create_marzban_service(settings)
    if service is None:
        print("Marzban is disabled. Set MARZBAN_ENABLED=true in .env")
        raise SystemExit(1)

    expire_at = datetime.now(UTC) + timedelta(days=args.days)
    try:
        result = await service.create_account(
            VpnCreateInput(
                account_name=args.username,
                expire_at=expire_at,
                traffic_limit_gb=args.traffic_gb,
                ip_limit=args.ip_limit,
            ),
        )
        print("Created:", result.account_name)
        print("Subscription:", result.subscription_url or "<none>")
        status = await service.get_status(result.account_name)
        if status:
            print("Status:", status.status, "expire:", status.expire_at)
        if args.delete:
            await service.delete_user(result.account_name)
            print("Deleted test user.")
    except VpnPanelError as exc:
        print(f"Error: {exc.message}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    asyncio.run(main())
