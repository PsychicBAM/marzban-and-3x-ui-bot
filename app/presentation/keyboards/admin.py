from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Main admin menu
ADMIN_REQUESTS = "📥 Заявки"
ADMIN_CLIENTS = "👥 Клиенты"
ADMIN_SUPPORT = "🆘 Обращения"
ADMIN_MANAGEMENT = "🛠 Управление"
ADMIN_MARKETING = "📣 Маркетинг"
ADMIN_SYSTEM = "🩺 Система"
ADMIN_HOME = "🏠 Главное меню"
ADMIN_BACK = "🔙 Назад"

# Management submenu (legacy labels kept for cached keyboards)
ADMIN_MANUAL_KEY = "➕ Создать ключ"
ADMIN_TARIFFS = "💰 Тарифы"
ADMIN_SETTINGS = "⚙️ Настройки"

# Marketing submenu
ADMIN_BROADCASTS = "📣 Рассылки"
ADMIN_PROMO_CODES = "🎁 Промокоды"
ADMIN_REFERRALS = "🎁 Рефералы"

# System submenu
ADMIN_STATISTICS = "📊 Статистика"
ADMIN_SYSTEM_STATUS = "🩺 Статус системы"

ADMIN_PLACEHOLDER = "Админ-панель"


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_REQUESTS), KeyboardButton(text=ADMIN_CLIENTS)],
            [KeyboardButton(text=ADMIN_SUPPORT), KeyboardButton(text=ADMIN_MANAGEMENT)],
            [KeyboardButton(text=ADMIN_MARKETING), KeyboardButton(text=ADMIN_SYSTEM)],
            [KeyboardButton(text=ADMIN_HOME)],
        ],
        resize_keyboard=True,
        input_field_placeholder=ADMIN_PLACEHOLDER,
    )


def admin_management_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_MANUAL_KEY)],
            [KeyboardButton(text=ADMIN_TARIFFS)],
            [KeyboardButton(text=ADMIN_SETTINGS)],
            [KeyboardButton(text=ADMIN_BACK)],
        ],
        resize_keyboard=True,
        input_field_placeholder=ADMIN_PLACEHOLDER,
    )


def admin_marketing_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_BROADCASTS)],
            [KeyboardButton(text=ADMIN_PROMO_CODES)],
            [KeyboardButton(text=ADMIN_REFERRALS)],
            [KeyboardButton(text=ADMIN_BACK)],
        ],
        resize_keyboard=True,
        input_field_placeholder=ADMIN_PLACEHOLDER,
    )


def admin_system_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_STATISTICS)],
            [KeyboardButton(text=ADMIN_SYSTEM_STATUS)],
            [KeyboardButton(text=ADMIN_BACK)],
        ],
        resize_keyboard=True,
        input_field_placeholder=ADMIN_PLACEHOLDER,
    )
