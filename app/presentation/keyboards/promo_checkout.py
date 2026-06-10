from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

PROMO_ENTER = "promo:enter"
PROMO_SKIP = "promo:skip"
PROMO_CANCEL = "promo:cancel"


def promo_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data=PROMO_ENTER)],
            [InlineKeyboardButton(text="➡️ Продолжить без промокода", callback_data=PROMO_SKIP)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PROMO_CANCEL)],
        ],
    )
