from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.enums import SupportTicketStatus

AST_MENU = "ast:menu"
AST_OPEN = "ast:open"
AST_ANSWERED = "ast:answered"
AST_CLOSED = "ast:closed"
AST_SEARCH = "ast:search"
AST_BACK = "ast:back"
AST_LIST_PREFIX = "ast:list:"
AST_TICKET_PREFIX = "ast:ticket:"
AST_REPLY_PREFIX = "ast:reply:"
AST_CLOSE_PREFIX = "ast:close:"
AST_REOPEN_PREFIX = "ast:reopen:"
AST_CLIENT_PREFIX = "ast:client:"
AST_PAGE_INFO = "ast:page_info"


def admin_support_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆕 Открытые", callback_data=f"{AST_LIST_PREFIX}{SupportTicketStatus.OPEN.value}:0")],
            [InlineKeyboardButton(text="💬 Ожидают ответа", callback_data=f"{AST_LIST_PREFIX}{SupportTicketStatus.ANSWERED.value}:0")],
            [InlineKeyboardButton(text="✅ Закрытые", callback_data=f"{AST_LIST_PREFIX}{SupportTicketStatus.CLOSED.value}:0")],
            [InlineKeyboardButton(text="🔎 Найти обращение", callback_data=AST_SEARCH)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=AST_BACK)],
        ]
    )


def admin_support_list_keyboard(status: str, tickets: list, *, page: int, pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ticket in tickets:
        user = ticket.user
        label = f"#{ticket.id}"
        if user and user.username:
            label += f" @{user.username[:12]}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{AST_TICKET_PREFIX}{ticket.id}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{AST_LIST_PREFIX}{status}:{page - 1}"))
    if pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=AST_PAGE_INFO))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{AST_LIST_PREFIX}{status}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=AST_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_support_ticket_keyboard(ticket_id: int, *, user_telegram_id: int | None, status: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"{AST_REPLY_PREFIX}{ticket_id}")],
    ]
    if status == SupportTicketStatus.CLOSED.value:
        rows.append([InlineKeyboardButton(text="🔓 Открыть снова", callback_data=f"{AST_REOPEN_PREFIX}{ticket_id}")])
    else:
        rows.append([InlineKeyboardButton(text="✅ Закрыть", callback_data=f"{AST_CLOSE_PREFIX}{ticket_id}")])
    if user_telegram_id:
        rows.append([InlineKeyboardButton(text="👤 Открыть клиента", callback_data=f"{AST_CLIENT_PREFIX}{user_telegram_id}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=AST_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
