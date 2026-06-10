from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def customer_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Купить VPN")],
            [KeyboardButton(text="🔄 Продлить VPN"), KeyboardButton(text="📊 Мой VPN")],
            [KeyboardButton(text="ℹ️ Инструкция"), KeyboardButton(text="🆘 Поддержка")],
            [KeyboardButton(text="🎁 Пригласить друга"), KeyboardButton(text="🔔 Акции и новости")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
