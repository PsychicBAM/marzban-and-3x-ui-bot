from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.admin_customer import ClientListItem
from app.application.utils.admin_client_format import (
    format_compact_button_label,
    total_pages,
)
from app.infrastructure.db.repositories.admin_customer_repo import (
    PAGE_SIZE,
    STATUS_ACTIVE,
    STATUS_DELETED,
    STATUS_DISABLED,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
)

ACL_DASH = "acl:dash"
ACL_ADMIN = "acl:adm"
ACL_SEARCH = "acl:search"
ACL_FILTER_PREFIX = "acl:f:"
ACL_OPEN_PREFIX = "acl:o:"
ACL_PAGE_PREFIX = "acl:p:"
ACL_PAGE_INFO_PREFIX = "acl:pg:i:"
ACL_SEARCH_RESULT_PREFIX = "acl:sr:"
ACL_SEARCH_PAGE_PREFIX = "acl:sq:"

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
            [
                InlineKeyboardButton(
                    text="⏳ Истекают скоро",
                    callback_data=f"{ACL_FILTER_PREFIX}{STATUS_EXPIRING_SOON}:0",
                )
            ],
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
    start_index = page * PAGE_SIZE
    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=format_compact_button_label(start_index + offset, item),
                callback_data=f"{ACL_OPEN_PREFIX}{item.vpn_account_id}:{status_filter}:{page}",
            )
        ]
        for offset, item in enumerate(items, start=1)
    ]
    buttons.append(_pagination_row(status_filter, page=page, total=total, page_prefix=ACL_PAGE_PREFIX))
    buttons.append([InlineKeyboardButton(text="🏠 К клиентам", callback_data=ACL_DASH)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def search_results_keyboard(
    items: list[ClientListItem],
    *,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    start_index = page * PAGE_SIZE
    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=format_compact_button_label(start_index + offset, item),
                callback_data=f"{ACL_SEARCH_RESULT_PREFIX}{item.vpn_account_id}:{page}",
            )
        ]
        for offset, item in enumerate(items, start=1)
    ]
    buttons.append(
        _pagination_row("search", page=page, total=total, page_prefix=ACL_SEARCH_PAGE_PREFIX),
    )
    buttons.append([InlineKeyboardButton(text="🏠 К клиентам", callback_data=ACL_DASH)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _pagination_row(
    scope: str,
    *,
    page: int,
    total: int,
    page_prefix: str,
) -> list[InlineKeyboardButton]:
    pages = total_pages(total, PAGE_SIZE)
    current = page + 1
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"{page_prefix}{scope}:{page - 1}",
            )
        )
    row.append(
        InlineKeyboardButton(
            text=f"Стр. {current}/{pages}",
            callback_data=f"{ACL_PAGE_INFO_PREFIX}{scope}:{page}",
        )
    )
    if current < pages:
        row.append(
            InlineKeyboardButton(
                text="Далее ➡️",
                callback_data=f"{page_prefix}{scope}:{page + 1}",
            )
        )
    return row


def client_card_keyboard(
    vpn_account_id: int,
    *,
    is_deleted: bool,
    list_filter: str | None = None,
    list_page: int | None = None,
    search_page: int | None = None,
) -> InlineKeyboardMarkup:
    if search_page is not None:
        back_callback = f"{ACL_SEARCH_PAGE_PREFIX}search:{search_page}"
    elif list_filter is not None and list_page is not None:
        back_callback = f"{ACL_PAGE_PREFIX}{list_filter}:{list_page}"
    else:
        back_callback = ACL_DASH

    if is_deleted:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Назад", callback_data=back_callback)],
            ],
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Отправить ссылку клиенту",
                    callback_data=f"{ACL_ACT_LINK}{vpn_account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📷 Отправить QR клиенту",
                    callback_data=f"{ACL_ACT_QR}{vpn_account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Продлить вручную",
                    callback_data=f"{ACL_ACT_EXTEND}{vpn_account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Отключить",
                    callback_data=f"{ACL_ACT_DISABLE}{vpn_account_id}",
                ),
                InlineKeyboardButton(
                    text="✅ Активировать",
                    callback_data=f"{ACL_ACT_ENABLE}{vpn_account_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить IP limit",
                    callback_data=f"{ACL_ACT_IP}{vpn_account_id}",
                ),
                InlineKeyboardButton(
                    text="🧹 Очистить IP",
                    callback_data=f"{ACL_ACT_CLEAR}{vpn_account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"{ACL_ACT_DELETE}{vpn_account_id}",
                )
            ],
            [InlineKeyboardButton(text="🏠 Назад", callback_data=back_callback)],
        ],
    )


def confirm_disable_keyboard(vpn_account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, отключить",
                    callback_data=f"{ACL_CONFIRM_DISABLE}{vpn_account_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"{ACL_CANCEL_CONFIRM}{vpn_account_id}",
                ),
            ],
        ],
    )


def confirm_delete_keyboard(vpn_account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"{ACL_CONFIRM_DELETE}{vpn_account_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"{ACL_CANCEL_CONFIRM}{vpn_account_id}",
                ),
            ],
        ],
    )
