from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

REF_LINK = "ref:link"
REF_STATS = "ref:stats"
REF_BONUSES = "ref:bonuses"
REF_APPLY = "ref:apply"
REF_HOME = "ref:home"


def referral_inline_keyboard(*, has_pending: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data=REF_LINK)],
        [InlineKeyboardButton(text="📊 Статистика", callback_data=REF_STATS)],
        [InlineKeyboardButton(text="🎁 Мои бонусы", callback_data=REF_BONUSES)],
    ]
    if has_pending:
        rows.append([InlineKeyboardButton(text="⚡ Применить бонусы", callback_data=REF_APPLY)])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data=REF_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
