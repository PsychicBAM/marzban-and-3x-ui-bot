"""
Development-only script to test Marzban user lifecycle operations.

Usage:
    python scripts/test_marzban_create_user.py --username testuser --create
    python scripts/test_marzban_create_user.py --username testuser --lifecycle
    python scripts/test_marzban_create_user.py --username testuser --disable
    python scripts/test_marzban_create_user.py --username testuser --enable
    python scripts/test_marzban_create_user.py --username testuser --change-ip-limit 1
    python scripts/test_marzban_create_user.py --username testuser --delete

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
from app.infrastructure.integrations.marzban.verification import (
    is_marzban_user_active,
    read_marzban_ip_limit,
)


async def _load_user_raw(service, username: str) -> dict:
    payload = await service._client.get_user_raw(username)  # noqa: SLF001 — dev script
    if payload is None:
        raise SystemExit(f"FAIL: Marzban user '{username}' not found")
    return payload


async def _verify_status(service, username: str, *, expected_active: bool) -> None:
    payload = await _load_user_raw(service, username)
    active = is_marzban_user_active(payload)
    if active is not expected_active:
        status = payload.get("status")
        raise SystemExit(
            f"FAIL: expected status active={expected_active}, panel status={status!r}",
        )
    print(f"Panel status OK: active={active} status={payload.get('status')}")


async def _verify_ip_limit(service, username: str, expected: int) -> None:
    payload = await _load_user_raw(service, username)
    actual = read_marzban_ip_limit(payload)
    if actual is None:
        print("WARN: Marzban panel does not expose limit_ip — IP limit cannot be verified")
        return
    if actual != expected:
        raise SystemExit(f"FAIL: expected limit_ip={expected}, panel has limit_ip={actual}")
    print(f"Panel IP limit OK: limit_ip={actual}")


async def _run_create(service, *, username: str, days: int, traffic_gb: int, ip_limit: int):
    expire_at = datetime.now(UTC) + timedelta(days=days)
    result = await service.create_account(
        VpnCreateInput(
            account_name=username,
            expire_at=expire_at,
            traffic_limit_gb=traffic_gb,
            ip_limit=ip_limit,
        ),
    )
    print("Created:", result.account_name)
    print("Subscription:", result.subscription_url or "<none>")
    await _verify_status(service, username, expected_active=True)
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test Marzban user lifecycle")
    parser.add_argument("--username", required=True, help="VPN account name")
    parser.add_argument("--days", type=int, default=30, help="Expiry in days")
    parser.add_argument("--traffic-gb", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--ip-limit", type=int, default=3, help="0 = unlimited")
    parser.add_argument("--create", action="store_true", help="Create user")
    parser.add_argument("--disable", action="store_true", help="Disable user")
    parser.add_argument("--enable", action="store_true", help="Enable user")
    parser.add_argument("--change-ip-limit", type=int, metavar="N", help="Change IP limit")
    parser.add_argument("--delete", action="store_true", help="Delete user")
    parser.add_argument(
        "--lifecycle",
        action="store_true",
        help="create -> change ip limit -> disable -> enable -> delete",
    )
    args = parser.parse_args()

    settings = get_settings()
    service = create_marzban_service(settings)
    if service is None:
        print("Marzban is disabled. Set MARZBAN_ENABLED=true in .env")
        raise SystemExit(1)

    vless_flow = (settings.marzban_vless_flow or "").strip()
    if vless_flow:
        print(f"VLESS flow configured: {vless_flow}")

    action_flags = (
        args.create,
        args.disable,
        args.enable,
        args.change_ip_limit is not None,
        args.delete,
        args.lifecycle,
    )
    if not any(action_flags):
        args.lifecycle = True

    try:
        if args.lifecycle:
            await _run_create(
                service,
                username=args.username,
                days=args.days,
                traffic_gb=args.traffic_gb,
                ip_limit=args.ip_limit,
            )
            print("")
            try:
                await service.update_user(
                    username=args.username,
                    expire_at=datetime.now(UTC) + timedelta(days=args.days),
                    data_limit_gb=args.traffic_gb,
                    ip_limit=1,
                    enable=True,
                    verify_ip_limit=True,
                )
                print("Changed IP limit to 1")
                await _verify_ip_limit(service, args.username, 1)
            except VpnPanelError as exc:
                print(f"IP limit change: {exc.message}")
            print("")
            await service.disable_user(args.username)
            print("Disabled user")
            await _verify_status(service, args.username, expected_active=False)
            print("")
            await service.enable_user(args.username)
            print("Enabled user")
            await _verify_status(service, args.username, expected_active=True)
            print("")
            await service.delete_user(args.username)
            print("Deleted test user.")
        else:
            if args.create:
                await _run_create(
                    service,
                    username=args.username,
                    days=args.days,
                    traffic_gb=args.traffic_gb,
                    ip_limit=args.ip_limit,
                )
            if args.change_ip_limit is not None:
                info = await service.get_user(args.username)
                if info is None:
                    raise SystemExit(f"FAIL: user '{args.username}' not found")
                await service.update_user(
                    username=args.username,
                    expire_at=info.expire_at or datetime.now(UTC) + timedelta(days=args.days),
                    data_limit_gb=0,
                    ip_limit=args.change_ip_limit,
                    enable=info.status == "active",
                    verify_ip_limit=True,
                )
                print(f"Changed IP limit to {args.change_ip_limit}")
                await _verify_ip_limit(service, args.username, args.change_ip_limit)
            if args.disable:
                await service.disable_user(args.username)
                print("Disabled user")
                await _verify_status(service, args.username, expected_active=False)
            if args.enable:
                await service.enable_user(args.username)
                print("Enabled user")
                await _verify_status(service, args.username, expected_active=True)
            if args.delete:
                await service.delete_user(args.username)
                print("Deleted test user.")
    except VpnPanelError as exc:
        print(f"Error: {exc.message}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    asyncio.run(main())
