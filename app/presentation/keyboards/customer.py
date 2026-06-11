from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.presentation.i18n import normalize_lang, t


def customer_main_keyboard(lang: str | None = None) -> ReplyKeyboardMarkup:
    code = normalize_lang(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(code, "menu.buy_vpn"))],
            [
                KeyboardButton(text=t(code, "menu.renew_vpn")),
                KeyboardButton(text=t(code, "menu.my_vpn")),
            ],
            [
                KeyboardButton(text=t(code, "menu.guide")),
                KeyboardButton(text=t(code, "menu.faq")),
            ],
            [KeyboardButton(text=t(code, "menu.support"))],
            [
                KeyboardButton(text=t(code, "menu.invite_friend")),
                KeyboardButton(text=t(code, "menu.promo_news")),
            ],
            [
                KeyboardButton(text=t(code, "menu.history")),
                KeyboardButton(text=t(code, "menu.language")),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder=t(code, "menu.placeholder"),
    )
