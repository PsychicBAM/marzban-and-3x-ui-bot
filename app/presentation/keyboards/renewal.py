from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.plan import PlanInfo

RENEW_SELECT_PREFIX = "renew:select:"
RENEW_PAID_PREFIX = "renew:paid:"
RENEW_CANCEL = "renew:cancel"


def renewal_plan_keyboard(plans: list[PlanInfo], *, vpn_account_id: int | None) -> InlineKeyboardMarkup:
    account_token = vpn_account_id if vpn_account_id is not None else 0
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{plan.name} — {plan.price:.0f} ₽",
                callback_data=f"{RENEW_SELECT_PREFIX}{plan.id}:{account_token}",
            )
        ]
        for plan in plans
    ]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=RENEW_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def renewal_checkout_keyboard(plan_id: int, *, vpn_account_id: int | None) -> InlineKeyboardMarkup:
    account_token = vpn_account_id if vpn_account_id is not None else 0
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Я оплатил продление",
                    callback_data=f"{RENEW_PAID_PREFIX}{plan_id}:{account_token}",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=RENEW_CANCEL)],
        ],
    )
