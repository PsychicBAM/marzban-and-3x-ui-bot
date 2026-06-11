from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.presentation.i18n import t

HIST_PAGE_PREFIX = "hist:page:"
HIST_BACK_MENU = "hist:menu"


def history_keyboard(lang: str, *, page: int, pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{HIST_PAGE_PREFIX}{page - 1}"))
    if pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="hist:noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{HIST_PAGE_PREFIX}{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=t(lang, "common.main_menu_short"), callback_data=HIST_BACK_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
