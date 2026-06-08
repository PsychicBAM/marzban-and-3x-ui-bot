from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

STAT_REFRESH = "stat:refresh"
STAT_TODAY = "stat:today"
STAT_MONTH = "stat:month"
STAT_BACK = "stat:back"


def statistics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=STAT_REFRESH)],
            [
                InlineKeyboardButton(text="📅 Сегодня", callback_data=STAT_TODAY),
                InlineKeyboardButton(text="📆 Этот месяц", callback_data=STAT_MONTH),
            ],
            [InlineKeyboardButton(text="🏠 Назад", callback_data=STAT_BACK)],
        ],
    )
