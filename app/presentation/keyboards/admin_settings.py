from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.instruction_settings import InstructionSettings
from app.application.dto.notification_settings import NotificationSettings
from app.application.services.settings_service import (
    CHECK_INTERVAL_DAILY,
    CHECK_INTERVAL_EVERY_1_MINUTE,
    CHECK_INTERVAL_EVERY_10_MINUTES,
    CHECK_INTERVAL_HOURLY,
    CHECK_INTERVAL_LABELS,
)

SET_HOME = "set:home"
SET_MENU = "set:menu"
SET_NOTIFICATIONS = "set:notifications"
SET_PAYMENT = "set:payment"
SET_SUPPORT = "set:support"
SET_INSTRUCTION = "set:instruction"

PAY_EDIT = "pay:edit"
PAY_CLEAR = "pay:clear"
PAY_BACK = "pay:back"

SUP_EDIT_USERNAME = "sup:edit:user"
SUP_EDIT_URL = "sup:edit:url"
SUP_EDIT_TEXT = "sup:edit:text"
SUP_CLEAR = "sup:clear"
SUP_BACK = "sup:back"

INS_EDIT_TEXT = "ins:edit:text"
INS_EDIT_URL = "ins:edit:url"
INS_TOGGLE = "ins:toggle"
INS_CLEAR = "ins:clear"
INS_BACK = "ins:back"

NTF_TOGGLE = "ntf:toggle"
NTF_DAYS = "ntf:days"
NTF_INTERVAL = "ntf:interval"
NTF_TEST_TOGGLE = "ntf:test_toggle"
NTF_EXPIRED_TOGGLE = "ntf:expired_toggle"
NTF_SEND_TEST = "ntf:send_test"
NTF_INTERVAL_PREFIX = "ntf:ival:"


def settings_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Уведомления", callback_data=SET_NOTIFICATIONS)],
            [InlineKeyboardButton(text="💳 Реквизиты оплаты", callback_data=SET_PAYMENT)],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data=SET_SUPPORT)],
            [InlineKeyboardButton(text="ℹ️ Инструкция", callback_data=SET_INSTRUCTION)],
            [InlineKeyboardButton(text="🏠 Назад в админ-панель", callback_data=SET_HOME)],
        ],
    )


def payment_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить реквизиты", callback_data=PAY_EDIT)],
            [InlineKeyboardButton(text="🧹 Очистить реквизиты", callback_data=PAY_CLEAR)],
            [InlineKeyboardButton(text="🏠 Назад", callback_data=SET_MENU)],
        ],
    )


def support_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить username", callback_data=SUP_EDIT_USERNAME)],
            [InlineKeyboardButton(text="✏️ Изменить ссылку", callback_data=SUP_EDIT_URL)],
            [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=SUP_EDIT_TEXT)],
            [InlineKeyboardButton(text="🧹 Очистить", callback_data=SUP_CLEAR)],
            [InlineKeyboardButton(text="🏠 Назад", callback_data=SET_MENU)],
        ],
    )


def instruction_settings_keyboard(config: InstructionSettings) -> InlineKeyboardMarkup:
    toggle_text = "🚫 Выключить" if config.enabled else "✅ Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить текст инструкции", callback_data=INS_EDIT_TEXT)],
            [InlineKeyboardButton(text="✏️ Изменить ссылку", callback_data=INS_EDIT_URL)],
            [InlineKeyboardButton(text=toggle_text, callback_data=INS_TOGGLE)],
            [InlineKeyboardButton(text="🧹 Очистить", callback_data=INS_CLEAR)],
            [InlineKeyboardButton(text="🏠 Назад", callback_data=SET_MENU)],
        ],
    )


def notification_settings_keyboard(config: NotificationSettings) -> InlineKeyboardMarkup:
    toggle_text = "🚫 Выключить уведомления" if config.enabled else "✅ Включить уведомления"
    test_text = "🧪 Выключить тестовый режим" if config.test_mode else "🧪 Включить тестовый режим"
    expired_text = (
        "🚫 Выключить уведомление «истёк»"
        if config.notify_expired_enabled
        else "⛔ Включить уведомление «истёк»"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=NTF_TOGGLE)],
            [InlineKeyboardButton(text="📅 Изменить дни", callback_data=NTF_DAYS)],
            [InlineKeyboardButton(text="⏱ Изменить частоту", callback_data=NTF_INTERVAL)],
            [InlineKeyboardButton(text=test_text, callback_data=NTF_TEST_TOGGLE)],
            [InlineKeyboardButton(text=expired_text, callback_data=NTF_EXPIRED_TOGGLE)],
            [InlineKeyboardButton(text="📩 Отправить тест админу", callback_data=NTF_SEND_TEST)],
            [InlineKeyboardButton(text="🏠 Назад", callback_data=SET_MENU)],
        ],
    )


def notification_interval_keyboard() -> InlineKeyboardMarkup:
    options = [
        CHECK_INTERVAL_DAILY,
        CHECK_INTERVAL_HOURLY,
        CHECK_INTERVAL_EVERY_10_MINUTES,
        CHECK_INTERVAL_EVERY_1_MINUTE,
    ]
    buttons = [
        [
            InlineKeyboardButton(
                text=CHECK_INTERVAL_LABELS[code],
                callback_data=f"{NTF_INTERVAL_PREFIX}{code}",
            )
        ]
        for code in options
    ]
    buttons.append([InlineKeyboardButton(text="🏠 Назад", callback_data=SET_NOTIFICATIONS)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
