"""
Unit checks for VPN account naming without Telegram @username.

Usage:
    python scripts/test_vpn_account_name_no_username.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.exceptions import VpnPanelValidationError
from app.application.utils.admin_client_format import format_admin_customer_handle
from app.application.utils.vpn_username import (
    build_primary_vpn_account_name,
    clean_vpn_base_name,
    resolve_primary_vpn_account_name,
)


def test_with_username() -> None:
    name = resolve_primary_vpn_account_name(
        vpn_account_name=None,
        username="Abdallah",
        telegram_id=123456789,
    )
    assert name == "abdallah_123456789"


def test_without_username_asks() -> None:
    name = resolve_primary_vpn_account_name(
        vpn_account_name=None,
        username=None,
        telegram_id=123456789,
    )
    assert name is None


def test_entered_name_with_spaces() -> None:
    cleaned = clean_vpn_base_name("Abdallah Bahi")
    assert cleaned == "abdallah_bahi"
    final = build_primary_vpn_account_name("Abdallah Bahi", 123456789)
    assert final == "abdallah_bahi_123456789"


def test_duplicate_human_names_different_telegram_ids() -> None:
    first = build_primary_vpn_account_name("mohamed", 111)
    second = build_primary_vpn_account_name("mohamed", 222)
    assert first == "mohamed_111"
    assert second == "mohamed_222"
    assert first != second


def test_invalid_name_rejected() -> None:
    for raw in ("", "   ", "абдалла", "محمد", "!!!", "name@mail"):
        try:
            clean_vpn_base_name(raw)
            raise AssertionError(f"expected invalid for {raw!r}")
        except VpnPanelValidationError:
            pass


def test_existing_vpn_account_name_not_renamed() -> None:
    existing = resolve_primary_vpn_account_name(
        vpn_account_name="oldname",
        username="new_username",
        telegram_id=999,
    )
    assert existing == "oldname"


def test_later_username_does_not_rename_existing() -> None:
    # Profile username can update later; primary VPN name stays.
    user = SimpleNamespace(vpn_account_name="abdallah_123", username="brand_new", telegram_id=123)
    resolved = resolve_primary_vpn_account_name(
        vpn_account_name=user.vpn_account_name,
        username=user.username,
        telegram_id=user.telegram_id,
    )
    assert resolved == "abdallah_123"


def test_admin_display_without_username() -> None:
    label = format_admin_customer_handle(
        full_name="Abdallah",
        username=None,
        telegram_id=123456789,
    )
    assert label == "Abdallah · ID 123456789"
    assert "—" not in label
    assert "@" not in label


def test_admin_display_with_username() -> None:
    label = format_admin_customer_handle(
        full_name="Abdallah",
        username="abdallah",
        telegram_id=123456789,
    )
    assert label == "Abdallah (@abdallah)"


def main() -> None:
    test_with_username()
    test_without_username_asks()
    test_entered_name_with_spaces()
    test_duplicate_human_names_different_telegram_ids()
    test_invalid_name_rejected()
    test_existing_vpn_account_name_not_renamed()
    test_later_username_does_not_rename_existing()
    test_admin_display_without_username()
    test_admin_display_with_username()
    print("VPN account name (no username) tests passed.")


if __name__ == "__main__":
    main()
