"""
List or delete 3x-ui Clients entries with no attached inbounds.

Dry-run by default. Pass --delete to actually remove orphan global client records.

Usage:
    python scripts/cleanup_xui_orphan_clients.py
    python scripts/cleanup_xui_orphan_clients.py --delete
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.exceptions import VpnPanelError
from app.config.settings import get_settings
from app.infrastructure.integrations.factory import create_xui_service
from app.infrastructure.integrations.xui.inbound_mutations import ClientDeleteCriteria


async def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup orphan 3x-ui global client records")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete orphan global client records (default is dry-run)",
    )
    args = parser.parse_args()

    settings = get_settings()
    service = create_xui_service(settings)
    if service is None:
        print("3x-ui is disabled. Set XUI_ENABLED=true in .env")
        raise SystemExit(1)

    client = service._client  # noqa: SLF001
    if not await client._global_clients_api_available():  # noqa: SLF001
        print("Global Clients API is not available on this panel.")
        raise SystemExit(1)

    orphans = await client.list_orphan_global_clients_raw()
    if not orphans:
        print("No orphan global client records found.")
        return

    print(f"Found {len(orphans)} orphan global client record(s):")
    for record in orphans:
        email = str(record.get("email") or "")
        sub_id = str(record.get("subId") or "")
        uuid = str(record.get("uuid") or "")
        print(f"  - email={email} subId={sub_id or '-'} uuid={uuid or '-'}")

    if not args.delete:
        print("\nDry-run only. Re-run with --delete to remove these records.")
        return

    deleted = 0
    failed = 0
    for record in orphans:
        email = str(record.get("email") or "").strip()
        if not email:
            continue
        criteria = ClientDeleteCriteria(
            email=email,
            client_uuid=str(record.get("uuid") or "") or None,
            sub_id=str(record.get("subId") or "") or None,
        )
        try:
            await client.delete_client_everywhere(criteria)
            deleted += 1
            print(f"Deleted orphan: {email}")
        except VpnPanelError as exc:
            failed += 1
            print(f"Failed to delete {email}: {exc.message}")

    print(f"\nDone. deleted={deleted} failed={failed}")


if __name__ == "__main__":
    asyncio.run(main())
