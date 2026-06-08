from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Заявки"), KeyboardButton(text="👥 Клиенты")],
            [KeyboardButton(text="➕ Создать ключ"), KeyboardButton(text="💰 Тарифы")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Админ-панель",
    )
