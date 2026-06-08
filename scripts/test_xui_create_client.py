"""
Development-only script to test 3x-ui client creation.

Usage:
    python scripts/test_xui_create_client.py --email testuser --days 30

Requires .env with XUI_* variables. Never commit real credentials.
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
from app.infrastructure.integrations.factory import create_xui_service


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test 3x-ui create client")
    parser.add_argument("--email", required=True, help="Client email / account name")
    parser.add_argument("--days", type=int, default=30, help="Expiry in days")
    parser.add_argument("--traffic-gb", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--ip-limit", type=int, default=3, help="0 = unlimited")
    parser.add_argument("--list-inbounds", action="store_true", help="List inbounds only")
    parser.add_argument("--delete", action="store_true", help="Delete client after test")
    args = parser.parse_args()

    settings = get_settings()
    service = create_xui_service(settings)
    if service is None:
        print("3x-ui is disabled. Set XUI_ENABLED=true in .env")
        raise SystemExit(1)

    if args.list_inbounds:
        inbounds = await service.list_inbounds()
        for inbound in inbounds:
            print(f"#{inbound.inbound_id} {inbound.tag} {inbound.protocol}:{inbound.port} clients={inbound.client_count}")
        return

    expire_at = datetime.now(UTC) + timedelta(days=args.days)
    try:
        result = await service.create_account(
            VpnCreateInput(
                account_name=args.email,
                expire_at=expire_at,
                traffic_limit_gb=args.traffic_gb,
                ip_limit=args.ip_limit,
            ),
        )
        print("Created:", result.account_name, "uuid:", result.external_id)
        print("Subscription:", result.subscription_url or "<none>")
        traffic = await service.get_traffic(result.account_name)
        if traffic:
            print("Traffic used bytes:", traffic.used_traffic_bytes, "online:", traffic.online)
        if args.delete:
            await service.delete_client(result.account_name)
            print("Deleted test client.")
    except VpnPanelError as exc:
        print(f"Error: {exc.message}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    asyncio.run(main())
