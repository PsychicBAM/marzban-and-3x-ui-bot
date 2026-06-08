from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.plan import PlanInfo

PURCHASE_CALLBACK_PREFIX = "purchase:select:"


def plan_selection_keyboard(plans: list[PlanInfo]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{plan.name} — {plan.price:.0f} ₽",
                callback_data=f"{PURCHASE_CALLBACK_PREFIX}{plan.id}",
            )
        ]
        for plan in plans
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
