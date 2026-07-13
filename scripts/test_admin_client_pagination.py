"""
Unit checks for admin client list pagination helpers.

Usage:
    python scripts/test_admin_client_pagination.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.utils.admin_client_format import normalize_page, total_pages
from app.infrastructure.db.repositories.admin_customer_repo import PAGE_SIZE, STATUS_ACTIVE
from app.presentation.handlers.admin.clients import (
    ACL_FILTER_PREFIX,
    ACL_PAGE_PREFIX,
    _parse_list_callback,
)
from app.presentation.keyboards.admin_clients import _pagination_row


def _paginate(items: list[int], page: int) -> tuple[list[int], int, int]:
    total = len(items)
    page = normalize_page(page, total, PAGE_SIZE)
    start = page * PAGE_SIZE
    return items[start : start + PAGE_SIZE], total, page


def test_active_list_eight_items() -> None:
    items = list(range(8))
    page1_items, total, page1 = _paginate(items, 0)
    assert total == 8
    assert page1 == 0
    assert len(page1_items) == 5
    assert total_pages(total, PAGE_SIZE) == 2

    page2_items, total2, page2 = _paginate(items, 1)
    assert total2 == 8
    assert page2 == 1
    assert len(page2_items) == 3
    assert total_pages(total2, PAGE_SIZE) == 2


def test_page_three_clamps_to_last() -> None:
    items = list(range(8))
    page_items, total, page = _paginate(items, 2)
    assert page == 1
    assert len(page_items) == 3
    assert total_pages(total, PAGE_SIZE) == 2


def test_callback_parsing_preserves_active_filter() -> None:
    filter_data = f"{ACL_FILTER_PREFIX}{STATUS_ACTIVE}:0"
    page_data = f"{ACL_PAGE_PREFIX}{STATUS_ACTIVE}:1"

    filter_parsed = _parse_list_callback(filter_data, ACL_FILTER_PREFIX)
    page_parsed = _parse_list_callback(page_data, ACL_PAGE_PREFIX)

    assert filter_parsed == (STATUS_ACTIVE, 0)
    assert page_parsed == (STATUS_ACTIVE, 1)

    wrong = _parse_list_callback(page_data, ACL_FILTER_PREFIX)
    assert wrong is None


def test_pagination_row_never_shows_page_two_of_one() -> None:
    row = _pagination_row(STATUS_ACTIVE, page=1, total=8, page_prefix=ACL_PAGE_PREFIX)
    labels = [button.text for button in row]
    assert "Стр. 2/2" in labels
    assert "Стр. 2/1" not in labels
    next_buttons = [button for button in row if button.text == "Далее ➡️"]
    assert not next_buttons


def test_pagination_row_next_includes_filter() -> None:
    row = _pagination_row(STATUS_ACTIVE, page=0, total=8, page_prefix=ACL_PAGE_PREFIX)
    next_button = next(button for button in row if button.text == "Далее ➡️")
    assert next_button.callback_data == f"{ACL_PAGE_PREFIX}{STATUS_ACTIVE}:1"


def main() -> None:
    test_active_list_eight_items()
    test_page_three_clamps_to_last()
    test_callback_parsing_preserves_active_filter()
    test_pagination_row_never_shows_page_two_of_one()
    test_pagination_row_next_includes_filter()
    print("Admin client pagination tests passed.")


if __name__ == "__main__":
    main()
