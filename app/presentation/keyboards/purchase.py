from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

PURCHASE_PAID_PREFIX = "purchase:paid:"
PURCHASE_CANCEL = "purchase:cancel"


def purchase_checkout_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"{PURCHASE_PAID_PREFIX}{plan_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PURCHASE_CANCEL)],
        ],
    )
