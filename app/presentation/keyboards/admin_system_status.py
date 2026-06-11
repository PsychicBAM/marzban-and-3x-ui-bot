from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SS_TOGGLE_REPORT = "ss:report_toggle"
SS_SET_TIME = "ss:report_time"
SS_SEND_NOW = "ss:report_send"
SS_BACK = "ss:back"


def system_status_keyboard(*, report_enabled: bool) -> InlineKeyboardMarkup:
    toggle_label = "📅 Ежедневный отчёт: вкл" if report_enabled else "📅 Ежедневный отчёт: выкл"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_label, callback_data=SS_TOGGLE_REPORT)],
            [InlineKeyboardButton(text="🕘 Изменить время отчёта", callback_data=SS_SET_TIME)],
            [InlineKeyboardButton(text="📤 Отправить отчёт сейчас", callback_data=SS_SEND_NOW)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=SS_BACK)],
        ]
    )
