from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.infrastructure.db.models.vpn_account import VpnAccount

PURCHASE_PAID_PREFIX = "purchase:paid:"
PURCHASE_FREE_PREFIX = "purchase:free:"
PURCHASE_CANCEL = "purchase:cancel"
PURCHASE_CHOICE_RENEW_PREFIX = "purchase:choice:renew:"
PURCHASE_CHOICE_SEPARATE_PREFIX = "purchase:choice:separate:"
PURCHASE_RENEW_ACCOUNT_PREFIX = "purchase:renew:acct:"
PURCHASE_SEPARATE_PAID_PREFIX = "purchase:separate:paid:"


def purchase_checkout_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"{PURCHASE_PAID_PREFIX}{plan_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PURCHASE_CANCEL)],
        ],
    )


def purchase_free_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Активировать бесплатно", callback_data=f"{PURCHASE_FREE_PREFIX}{plan_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PURCHASE_CANCEL)],
        ],
    )


def purchase_choice_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Продлить текущий VPN",
                    callback_data=f"{PURCHASE_CHOICE_RENEW_PREFIX}{plan_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Купить отдельную подписку",
                    callback_data=f"{PURCHASE_CHOICE_SEPARATE_PREFIX}{plan_id}",
                ),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PURCHASE_CANCEL)],
        ],
    )


def purchase_renew_account_keyboard(plan_id: int, accounts: list[VpnAccount]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for account in accounts:
        title = account.display_name or account.vpn_account_name
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔄 {title}",
                    callback_data=f"{PURCHASE_RENEW_ACCOUNT_PREFIX}{plan_id}:{account.id}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=PURCHASE_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def purchase_separate_checkout_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"{PURCHASE_SEPARATE_PAID_PREFIX}{plan_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PURCHASE_CANCEL)],
        ],
    )
