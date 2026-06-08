from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.admin_customer import ClientListItem
from app.infrastructure.db.repositories.admin_customer_repo import (
    PAGE_SIZE,
    STATUS_ACTIVE,
    STATUS_DELETED,
    STATUS_DISABLED,
    STATUS_EXPIRED,
)

ACL_DASH = "acl:dash"
ACL_ADMIN = "acl:adm"
ACL_SEARCH = "acl:search"
ACL_FILTER_PREFIX = "acl:f:"
ACL_OPEN_PREFIX = "acl:o:"
ACL_PAGE_PREFIX = "acl:p:"
ACL_SEARCH_RESULT_PREFIX = "acl:sr:"

ACL_ACT_LINK = "acl:a:lnk:"
ACL_ACT_QR = "acl:a:qr:"
ACL_ACT_EXTEND = "acl:a:ext:"
ACL_ACT_DISABLE = "acl:a:dis:"
ACL_ACT_ENABLE = "acl:a:en:"
ACL_ACT_IP = "acl:a:ipl:"
ACL_ACT_CLEAR = "acl:a:clr:"
ACL_ACT_DELETE = "acl:a:del:"

ACL_CONFIRM_DISABLE = "acl:cfm:dis:"
ACL_CONFIRM_DELETE = "acl:cfm:del:"
ACL_CANCEL_CONFIRM = "acl:cfm:cancel:"


def clients_dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Активные", callback_data=f"{ACL_FILTER_PREFIX}{STATUS_ACTIVE}:0")],
            [InlineKeyboardButton(text="⛔ Истёкшие", callback_data=f"{ACL_FILTER_PREFIX}{STATUS_EXPIRED}:0")],
            [InlineKeyboardButton(text="🚫 Отключённые", callback_data=f"{ACL_FILTER_PREFIX}{STATUS_DISABLED}:0")],
            [InlineKeyboardButton(text="🗑 Удалённые", callback_data=f"{ACL_FILTER_PREFIX}{STATUS_DELETED}:0")],
            [InlineKeyboardButton(text="🔎 Найти клиента", callback_data=ACL_SEARCH)],
            [InlineKeyboardButton(text="🏠 Назад в админ-панель", callback_data=ACL_ADMIN)],
        ],
    )


def client_list_keyboard(
    status_filter: str,
    items: list[ClientListItem],
    *,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=_row_label(item),
                callback_data=f"{ACL_OPEN_PREFIX}{item.user_id}",
            )
        ]
        for item in items
    ]

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"{ACL_PAGE_PREFIX}{status_filter}:{page - 1}",
            )
        )
    if (page + 1) * PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(
                text="▶️ Далее",
                callback_data=f"{ACL_PAGE_PREFIX}{status_filter}:{page + 1}",
            )
        )
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🏠 К клиентам", callback_data=ACL_DASH)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _row_label(item: ClientListItem) -> str:
    expiry = item.expiry_at.strftime("%d.%m.%Y") if item.expiry_at else "—"
    panels = []
    if item.has_marzban:
        panels.append("M")
    if item.has_xui:
        panels.append("X")
    panel_text = "/".join(panels) if panels else "—"
    name = item.display_name[:20]
    return f"{name} · {item.vpn_status_label} · {expiry} · {panel_text}"


def search_results_keyboard(items: list[ClientListItem]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=_row_label(item), callback_data=f"{ACL_SEARCH_RESULT_PREFIX}{item.user_id}")]
        for item in items
    ]
    buttons.append([InlineKeyboardButton(text="🏠 К клиентам", callback_data=ACL_DASH)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def client_card_keyboard(user_id: int, *, is_deleted: bool, has_vpn: bool = True) -> InlineKeyboardMarkup:
    if is_deleted or not has_vpn:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Назад", callback_data=ACL_DASH)],
            ],
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Отправить ссылку клиенту", callback_data=f"{ACL_ACT_LINK}{user_id}")],
            [InlineKeyboardButton(text="📷 Отправить QR клиенту", callback_data=f"{ACL_ACT_QR}{user_id}")],
            [InlineKeyboardButton(text="🔄 Продлить вручную", callback_data=f"{ACL_ACT_EXTEND}{user_id}")],
            [
                InlineKeyboardButton(text="🚫 Отключить", callback_data=f"{ACL_ACT_DISABLE}{user_id}"),
                InlineKeyboardButton(text="✅ Активировать", callback_data=f"{ACL_ACT_ENABLE}{user_id}"),
            ],
            [
                InlineKeyboardButton(text="✏️ Изменить IP limit", callback_data=f"{ACL_ACT_IP}{user_id}"),
                InlineKeyboardButton(text="🧹 Очистить IP", callback_data=f"{ACL_ACT_CLEAR}{user_id}"),
            ],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"{ACL_ACT_DELETE}{user_id}")],
            [InlineKeyboardButton(text="🏠 Назад", callback_data=ACL_DASH)],
        ],
    )


def confirm_disable_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, отключить", callback_data=f"{ACL_CONFIRM_DISABLE}{user_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"{ACL_CANCEL_CONFIRM}{user_id}"),
            ],
        ],
    )


def confirm_delete_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"{ACL_CONFIRM_DELETE}{user_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"{ACL_CANCEL_CONFIRM}{user_id}"),
            ],
        ],
    )
