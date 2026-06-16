"""
Development-only script to test 3x-ui client lifecycle operations.

Usage:
    python scripts/test_xui_create_client.py --list-inbounds
    python scripts/test_xui_create_client.py --email testuser --create
    python scripts/test_xui_create_client.py --email testuser --lifecycle
    python scripts/test_xui_create_client.py --email testuser --disable
    python scripts/test_xui_create_client.py --email testuser --enable
    python scripts/test_xui_create_client.py --email testuser --change-ip-limit 5
    python scripts/test_xui_create_client.py --email testuser --delete

Requires .env with XUI_* variables. Never commit real credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.dto.vpn import VpnCreateInput
from app.application.exceptions import VpnPanelError
from app.config.settings import get_settings
from app.infrastructure.integrations.factory import create_xui_service
from app.infrastructure.integrations.xui.client import ADD_CLIENT_PATH, XuiApiClient
from app.infrastructure.integrations.xui.inbound_mutations import (
    ClientDeleteCriteria,
    count_clients_in_inbound,
    find_client_matching_delete_criteria,
    inbound_display_name,
    inbound_id_value,
    parse_settings_field,
    read_panel_bool,
    read_panel_int,
)

UPDATE_CLIENT_PROBE_UUID = "00000000-0000-0000-0000-000000000000"


async def _probe_endpoint(client: XuiApiClient, method: str, path: str, **kwargs) -> str:
    response = await client._request(method, path, **kwargs)  # noqa: SLF001 — dev script
    return str(response.status_code)


async def _probe_mutation_endpoints(client: XuiApiClient) -> None:
    add_status = await _probe_endpoint(
        client,
        "POST",
        ADD_CLIENT_PATH,
        json_body={"id": client.inbound_id, "settings": "{}"},
    )
    print(f"addClient probe: HTTP {add_status}")
    if add_status == "404":
        print("Expected: create may use inbound update fallback")

    update_path = f"/panel/api/inbounds/updateClient/{UPDATE_CLIENT_PROBE_UUID}"
    update_status = await _probe_endpoint(
        client,
        "POST",
        update_path,
        form_body={"id": str(client.inbound_id), "settings": "{}"},
    )
    print(f"updateClient probe: HTTP {update_status}")
    if update_status == "404":
        print("Expected: update may use inbound update fallback")


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


async def _load_client_state(service, email: str):
    info = await service.get_client(email)
    if info is None:
        await _print_inbound_diagnostics(service, email)
        raise SystemExit(f"FAIL: client '{email}' not found on panel")
    return info


async def _print_inbound_diagnostics(service, email: str) -> None:
    api_client = service._client  # noqa: SLF001
    inbound_id = api_client.inbound_id
    inbound = await api_client.get_inbound_raw(inbound_id)
    if inbound is None:
        print(f"Diagnostics: inbound #{inbound_id} not found via GET")
        return
    clients_count, settings_parsed = count_clients_in_inbound(inbound)
    protocol = str(inbound.get("protocol") or "unknown")
    print("Diagnostics:")
    print(f"  inbound_id={inbound_id}")
    print(f"  protocol={protocol}")
    print(f"  remark={inbound_display_name(inbound)}")
    print(f"  clients_in_settings={clients_count}")
    print(f"  settings_parsed_ok={settings_parsed}")
    print(f"  add_method={api_client.last_client_add_method or 'unknown'}")
    criteria = ClientDeleteCriteria(email=email)
    client = find_client_matching_delete_criteria(inbound, criteria)
    if client is None:
        print(f"  target_email={email} found_in_inbound=False")
        if settings_parsed:
            settings_obj = parse_settings_field(inbound.get("settings"))
            emails = [
                str(item.get("email") or "")
                for item in settings_obj.get("clients", [])
                if isinstance(item, dict)
            ]
            preview = ", ".join(emails[:8])
            if len(emails) > 8:
                preview += ", ..."
            print(f"  existing_client_emails=[{preview}]")
    else:
        print(f"  target_email={email} found_in_inbound=True")
        print(f"  client_enable={read_panel_bool(client.get('enable'))}")
        print(f"  client_limitIp={read_panel_int(client.get('limitIp'))}")
        if protocol.lower() == "vless":
            print(f"  client_flow={client.get('flow') or '<not set>'}")


async def _verify_raw_client_in_inbound(service, email: str, *, limit_ip: int | None = None) -> None:
    criteria = ClientDeleteCriteria(email=email)
    api_client = service._client  # noqa: SLF001
    inbound = await api_client.get_inbound_raw(api_client.inbound_id)
    if inbound is None:
        await _print_inbound_diagnostics(service, email)
        raise SystemExit("FAIL: configured inbound not found")
    client = find_client_matching_delete_criteria(inbound, criteria)
    if client is None:
        await _print_inbound_diagnostics(service, email)
        raise SystemExit(f"FAIL: client '{email}' not found in inbound settings.clients")
    if limit_ip is not None:
        actual = read_panel_int(client.get("limitIp"))
        if actual != limit_ip:
            raise SystemExit(f"FAIL: expected raw limitIp={limit_ip}, inbound has limitIp={actual}")
        print(f"Inbound raw client OK: limitIp={actual} enable={read_panel_bool(client.get('enable'))}")


async def _verify_client_state(
    service,
    email: str,
    *,
    enable: bool | None = None,
    limit_ip: int | None = None,
) -> None:
    info = await _load_client_state(service, email)
    if enable is not None and info.enable is not enable:
        raise SystemExit(
            f"FAIL: expected enable={enable}, panel has enable={info.enable}",
        )
    if limit_ip is not None and info.limit_ip != limit_ip:
        raise SystemExit(
            f"FAIL: expected limit_ip={limit_ip}, panel has limit_ip={info.limit_ip}",
        )
    print(
        f"Panel state OK: enable={info.enable} limit_ip={info.limit_ip} "
        f"total_gb={info.total_gb} uuid={info.client_uuid}",
    )
    if limit_ip is not None:
        await _verify_raw_client_in_inbound(service, email, limit_ip=limit_ip)


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
        print("Inbound update strategy was used for create.")
    print("Subscription:", result.subscription_url or "<none>")


async def _run_create(
    service,
    client: XuiApiClient,
    *,
    email: str,
    days: int,
    traffic_gb: int,
    ip_limit: int,
) -> object:
    expire_at = datetime.now(UTC) + timedelta(days=days)
    create_input = VpnCreateInput(
        account_name=email,
        expire_at=expire_at,
        traffic_limit_gb=traffic_gb,
        ip_limit=ip_limit,
    )
    result = await service.create_account(create_input)
    await _print_create_result(service, client, result, label="Created")
    await _verify_client_state(service, email, enable=True, limit_ip=ip_limit)
    return result


async def _run_disable(service, client: XuiApiClient, email: str) -> None:
    await service.disable_client(email)
    method = client.last_client_update_method or "unknown"
    print(f"Disabled client. Update method: {method}")
    await _verify_client_state(service, email, enable=False)


async def _run_enable(service, client: XuiApiClient, email: str) -> None:
    await service.enable_client(email)
    method = client.last_client_update_method or "unknown"
    print(f"Enabled client. Update method: {method}")
    await _verify_client_state(service, email, enable=True)


async def _run_change_ip_limit(
    service,
    client: XuiApiClient,
    email: str,
    new_limit: int,
) -> None:
    info = await _load_client_state(service, email)
    await service.update_client(
        email=email,
        expiry_time=info.expiry_time or datetime.now(UTC),
        total_gb=info.total_gb,
        limit_ip=new_limit,
        enable=info.enable,
    )
    method = client.last_client_update_method or "unknown"
    print(f"Changed IP limit to {new_limit}. Update method: {method}")
    await _verify_client_state(service, email, limit_ip=new_limit)


async def _run_delete(service, client: XuiApiClient, email: str, result) -> None:
    await service.delete_client(
        email,
        client_uuid=result.external_id,
        sub_id=str(result.raw.get("subId") or "") if result.raw else None,
    )
    delete_method = client.last_client_delete_method or "unknown"
    print("Deleted test client. Delete method:", delete_method)
    await _verify_client_absent(service, email)
    print("Delete verification: client absent from all inbounds")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test 3x-ui client lifecycle")
    parser.add_argument("--email", help="Client email / account name")
    parser.add_argument("--days", type=int, default=30, help="Expiry in days (create)")
    parser.add_argument("--traffic-gb", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--ip-limit", type=int, default=3, help="0 = unlimited")
    parser.add_argument("--list-inbounds", action="store_true", help="List inbounds only")
    parser.add_argument("--create", action="store_true", help="Create client and verify panel state")
    parser.add_argument("--disable", action="store_true", help="Disable client and verify panel state")
    parser.add_argument("--enable", action="store_true", help="Enable client and verify panel state")
    parser.add_argument(
        "--change-ip-limit",
        type=int,
        metavar="N",
        help="Change client IP limit and verify panel state",
    )
    parser.add_argument("--delete", action="store_true", help="Delete client and verify absence")
    parser.add_argument(
        "--lifecycle",
        action="store_true",
        help="Run create -> disable -> enable -> change ip limit -> delete",
    )
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

    action_flags = (
        args.create,
        args.disable,
        args.enable,
        args.change_ip_limit is not None,
        args.delete,
        args.lifecycle,
        args.reuse_existing,
    )
    if not any(action_flags):
        args.create = True
        if not args.delete:
            args.lifecycle = True

    try:
        await _probe_mutation_endpoints(client)

        result = None
        if args.reuse_existing:
            print("First create (new or reuse):")
            first = await _run_create(
                service,
                client,
                email=args.email,
                days=args.days,
                traffic_gb=args.traffic_gb,
                ip_limit=args.ip_limit,
            )
            print("")
            print("Second create with same email (should update existing):")
            second_expire = datetime.now(UTC) + timedelta(days=args.days + 7)
            second_input = VpnCreateInput(
                account_name=args.email,
                expire_at=second_expire,
                traffic_limit_gb=args.traffic_gb,
                ip_limit=args.ip_limit,
            )
            second = await service.create_account(second_input)
            await _print_create_result(service, client, second, label="Second")
            result = second
        elif args.lifecycle:
            result = await _run_create(
                service,
                client,
                email=args.email,
                days=args.days,
                traffic_gb=args.traffic_gb,
                ip_limit=args.ip_limit,
            )
            print("")
            await _run_disable(service, client, args.email)
            print("")
            await _run_enable(service, client, args.email)
            print("")
            await _run_change_ip_limit(service, client, args.email, 1)
            print("")
            await _run_delete(service, client, args.email, result)
        else:
            if args.create:
                result = await _run_create(
                    service,
                    client,
                    email=args.email,
                    days=args.days,
                    traffic_gb=args.traffic_gb,
                    ip_limit=args.ip_limit,
                )
            if args.disable:
                await _run_disable(service, client, args.email)
            if args.enable:
                await _run_enable(service, client, args.email)
            if args.change_ip_limit is not None:
                await _run_change_ip_limit(
                    service,
                    client,
                    args.email,
                    args.change_ip_limit,
                )
            if args.delete:
                if result is None:
                    info = await service.get_client(args.email)
                    if info is None:
                        print(
                            f"Client '{args.email}' not found. "
                            "Use --create to create it first, or --lifecycle for full flow.",
                        )
                        await _print_inbound_diagnostics(service, args.email)
                        raise SystemExit(1)
                    result = SimpleNamespace(
                        external_id=info.client_uuid,
                        raw={"subId": ""},
                    )
                await _run_delete(service, client, args.email, result)

        if result and not args.delete and not args.lifecycle:
            traffic = await service.get_traffic(result.account_name)
            if traffic:
                print("Traffic used bytes:", traffic.used_traffic_bytes, "online:", traffic.online)
    except VpnPanelError as exc:
        print(f"Error: {exc.message}")
        if args.email:
            try:
                await _print_inbound_diagnostics(service, args.email)
            except Exception:
                pass
        raise SystemExit(2) from exc


if __name__ == "__main__":
    asyncio.run(main())
