from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.enums import SupportTicketTopic
from app.presentation.i18n import t

SUP_MENU = "sup:menu"
SUP_CREATE = "sup:create"
SUP_LIST = "sup:list"
SUP_LIST_PAGE_PREFIX = "sup:list:"
SUP_BACK_MENU = "sup:back_menu"
SUP_TOPIC_PREFIX = "sup:topic:"
SUP_TICKET_PREFIX = "sup:ticket:"
SUP_TICKET_REPLY_PREFIX = "sup:reply:"
SUP_TICKET_CLOSE_PREFIX = "sup:close:"
SUP_TICKET_BACK_LIST = "sup:ticket_back_list"
SUP_LIST_PAGE_INFO = "sup:list_info"


def support_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "support.create_ticket"), callback_data=SUP_CREATE)],
            [InlineKeyboardButton(text=t(lang, "support.my_tickets"), callback_data=f"{SUP_LIST_PAGE_PREFIX}0")],
            [InlineKeyboardButton(text=t(lang, "lang.back"), callback_data=SUP_BACK_MENU)],
        ]
    )


def support_topic_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "support.topic_payment"), callback_data=f"{SUP_TOPIC_PREFIX}{SupportTicketTopic.PAYMENT.value}")],
            [InlineKeyboardButton(text=t(lang, "support.topic_connection"), callback_data=f"{SUP_TOPIC_PREFIX}{SupportTicketTopic.CONNECTION.value}")],
            [InlineKeyboardButton(text=t(lang, "support.topic_renewal"), callback_data=f"{SUP_TOPIC_PREFIX}{SupportTicketTopic.RENEWAL.value}")],
            [InlineKeyboardButton(text=t(lang, "support.topic_other"), callback_data=f"{SUP_TOPIC_PREFIX}{SupportTicketTopic.OTHER.value}")],
            [InlineKeyboardButton(text=t(lang, "lang.back"), callback_data=SUP_MENU)],
        ]
    )


def support_ticket_list_keyboard(
    lang: str,
    tickets: list,
    *,
    page: int,
    pages: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ticket in tickets:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"#{ticket.id} · {ticket.topic[:8]}",
                    callback_data=f"{SUP_TICKET_PREFIX}{ticket.id}",
                )
            ]
        )
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{SUP_LIST_PAGE_PREFIX}{page - 1}"))
    if pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=SUP_LIST_PAGE_INFO))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{SUP_LIST_PAGE_PREFIX}{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=t(lang, "lang.back"), callback_data=SUP_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_ticket_detail_keyboard(lang: str, ticket_id: int, *, can_reply: bool, can_close: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_reply:
        rows.append([InlineKeyboardButton(text=t(lang, "support.reply"), callback_data=f"{SUP_TICKET_REPLY_PREFIX}{ticket_id}")])
    if can_close:
        rows.append([InlineKeyboardButton(text=t(lang, "support.close_ticket"), callback_data=f"{SUP_TICKET_CLOSE_PREFIX}{ticket_id}")])
    rows.append([InlineKeyboardButton(text=t(lang, "lang.back"), callback_data=SUP_TICKET_BACK_LIST)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
