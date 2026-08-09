from __future__ import annotations

from app.application.dto.admin_customer import ClientListItem

def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return text[:max_len]
    return text[: max_len - 1] + "…"


def subscription_short_label(
    display_name: str | None,
    vpn_account_name: str,
    *,
    max_len: int = 14,
) -> str:
    if display_name:
        return _truncate(display_name.strip(), max_len)
    return _truncate(vpn_account_name, max_len)


def customer_short_name(name: str, *, max_len: int = 10) -> str:
    return _truncate(name.strip(), max_len)


def panel_badge_short(has_marzban: bool, has_xui: bool) -> str:
    if has_marzban and has_xui:
        return "M/XUI"
    if has_marzban:
        return "M"
    if has_xui:
        return "XUI"
    return "—"


def format_compact_list_row(index: int, item: ClientListItem) -> str:
    label = subscription_short_label(item.subscription_display_name, item.vpn_account_name)
    expiry = item.expiry_at.strftime("%d.%m") if item.expiry_at else "—"
    badge = panel_badge_short(item.has_marzban, item.has_xui)
    customer = format_admin_customer_handle(
        full_name=item.customer_name,
        username=item.username,
        telegram_id=item.telegram_id,
    )
    return (
        f"{index}) 👤 {customer} · 🔑 {label}\n"
        f"   до {expiry} · {badge}"
    )


def format_compact_button_label(index: int, item: ClientListItem) -> str:
    short_customer = customer_short_name(
        format_admin_customer_handle(
            full_name=item.customer_name,
            username=item.username,
            telegram_id=item.telegram_id,
            compact=True,
        ),
        max_len=18,
    )
    short_label = subscription_short_label(
        item.subscription_display_name,
        item.vpn_account_name,
        max_len=12,
    )
    return _truncate(f"{index}. {short_customer} · {short_label}", 64)


def format_admin_customer_handle(
    *,
    full_name: str | None,
    username: str | None,
    telegram_id: int,
    compact: bool = False,
) -> str:
    """Admin-facing customer label that never shows a blank @username."""
    name = (full_name or "").strip() or "Пользователь"
    if username:
        handle = f"@{username.lstrip('@')}"
        if compact:
            return handle
        return f"{name} ({handle})"
    if compact:
        first = name.split()[0] if name else "ID"
        return f"{first} · {telegram_id}"
    return f"{name} · ID {telegram_id}"



def total_pages(total: int, page_size: int) -> int:
    if total <= 0:
        return 1
    return (total + page_size - 1) // page_size


def normalize_page(page: int, total: int, page_size: int) -> int:
    """Clamp 0-based page index to valid range after total_pages is known."""
    if page < 0:
        return 0
    pages = total_pages(total, page_size)
    if page >= pages:
        return max(0, pages - 1)
    return page
