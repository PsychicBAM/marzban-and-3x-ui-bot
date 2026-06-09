"""
Development-only script to test 3x-ui client creation.

Usage:
    python scripts/test_xui_create_client.py --list-inbounds
    python scripts/test_xui_create_client.py --email testuser --days 30
    python scripts/test_xui_create_client.py --email testuser --reuse-existing

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
from app.infrastructure.integrations.xui.client import ADD_CLIENT_PATH, XuiApiClient
from app.infrastructure.integrations.xui.inbound_mutations import (
    ClientDeleteCriteria,
    find_client_matching_delete_criteria,
    inbound_display_name,
    inbound_id_value,
)


async def _probe_add_client_endpoint(client: XuiApiClient) -> str:
    """Return addClient HTTP status without creating a client."""
    response = await client._request(  # noqa: SLF001 — dev script
        "POST",
        ADD_CLIENT_PATH,
        json_body={"id": client.inbound_id, "settings": "{}"},
    )
    return str(response.status_code)


async def _verify_client_absent(service, email: str) -> None:
    criteria = ClientDeleteCriteria(email=email)
    client = service._client  # noqa: SLF001
    for summary in await client.list_inbounds_raw():
        inbound_id = inbound_id_value(summary)
        if inbound_id is None:
            continue
        inbound = await client.get_inbound_raw(inbound_id)
        if inbound is None:
            continue
        if find_client_matching_delete_criteria(inbound, criteria) is not None:
            remark = inbound_display_name(inbound)
            raise SystemExit(
                f"FAIL: client '{email}' still exists in inbound #{inbound_id} {remark}",
            )


async def _print_create_result(
    service,
    client: XuiApiClient,
    result,
    *,
    label: str,
) -> None:
    add_method = client.last_client_add_method or "unknown"
    print(f"{label}: {result.account_name} uuid: {result.external_id}")
    print("Add method:", add_method)
    if result.raw:
        inbound = await service.get_inbound()
        protocol = inbound.protocol if inbound else "unknown"
        print("Inbound protocol:", protocol)
        if protocol.lower() == "vless":
            print("Client flow:", result.raw.get("flow") or "<not set>")
    if add_method == "inbound_update":
        print("Inbound update strategy was used.")
    print("Subscription:", result.subscription_url or "<none>")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test 3x-ui create client")
    parser.add_argument("--email", help="Client email / account name (required for create/delete)")
    parser.add_argument("--days", type=int, default=30, help="Expiry in days")
    parser.add_argument("--traffic-gb", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--ip-limit", type=int, default=3, help="0 = unlimited")
    parser.add_argument("--list-inbounds", action="store_true", help="List inbounds only")
    parser.add_argument("--delete", action="store_true", help="Delete client after test")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Create twice with same email; second call should update, not fail",
    )
    args = parser.parse_args()

    if not args.list_inbounds and not args.email:
        parser.error("--email is required unless --list-inbounds is used")

    settings = get_settings()
    service = create_xui_service(settings)
    if service is None:
        print("3x-ui is disabled. Set XUI_ENABLED=true in .env")
        raise SystemExit(1)

    vless_flow = (settings.xui_vless_flow or "").strip()
    if vless_flow:
        print(f"VLESS flow configured: {vless_flow}")

    if args.list_inbounds:
        inbounds = await service.list_inbounds()
        for inbound in inbounds:
            print(
                f"#{inbound.inbound_id} {inbound.tag} "
                f"{inbound.protocol}:{inbound.port} clients={inbound.client_count}"
            )
        return

    assert args.email is not None
    client = service._client  # noqa: SLF001 — dev script
    assert isinstance(client, XuiApiClient)

    try:
        add_client_status = await _probe_add_client_endpoint(client)
        print(f"addClient probe: HTTP {add_client_status}")
        if add_client_status == "404":
            print("Expected: create may use inbound update fallback")
    except VpnPanelError as exc:
        print(f"addClient probe error: {exc.message}")

    expire_at = datetime.now(UTC) + timedelta(days=args.days)
    create_input = VpnCreateInput(
        account_name=args.email,
        expire_at=expire_at,
        traffic_limit_gb=args.traffic_gb,
        ip_limit=args.ip_limit,
    )

    try:
        if args.reuse_existing:
            print("First create (new or reuse):")
            first = await service.create_account(create_input)
            await _print_create_result(service, client, first, label="First")

            second_expire = datetime.now(UTC) + timedelta(days=args.days + 7)
            second_input = VpnCreateInput(
                account_name=args.email,
                expire_at=second_expire,
                traffic_limit_gb=args.traffic_gb,
                ip_limit=args.ip_limit,
            )
            print("")
            print("Second create with same email (should update existing):")
            second = await service.create_account(second_input)
            await _print_create_result(service, client, second, label="Second")
            result = second
        else:
            result = await service.create_account(create_input)
            await _print_create_result(service, client, result, label="Created")

        traffic = await service.get_traffic(result.account_name)
        if traffic:
            print("Traffic used bytes:", traffic.used_traffic_bytes, "online:", traffic.online)
        if args.delete:
            await service.delete_client(
                result.account_name,
                client_uuid=result.external_id,
                sub_id=str(result.raw.get("subId") or "") if result.raw else None,
            )
            delete_method = client.last_client_delete_method or "unknown"
            print("Deleted test client. Delete method:", delete_method)
            await _verify_client_absent(service, result.account_name)
            print("Delete verification: client absent from inbound")
    except VpnPanelError as exc:
        print(f"Error: {exc.message}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    asyncio.run(main())
