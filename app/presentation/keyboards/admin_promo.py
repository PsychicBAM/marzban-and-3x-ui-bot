from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.promo_code import PromoCodeInfo
from app.domain.enums import PromoDiscountType, PromoRequestScope

PC_HOME = "pc:home"
PC_CREATE = "pc:new"
PC_LIST = "pc:list"
PC_SEARCH = "pc:srch"
PC_STATS = "pc:stat"
PC_BACK_ADMIN = "pc:adm"
PC_CANCEL = "pc:cancel"
PC_CONFIRM = "pc:ok"
PC_SKIP_DATES = "pc:dates:skip"
PC_UNLIMITED_USES = "pc:uses:unlim"
PC_TYPE_PREFIX = "pc:dt:"
PC_SCOPE_PREFIX = "pc:scp:"
PC_PLAN_PREFIX = "pc:plan:"
PC_ITEM_PREFIX = "pc:item:"
PC_TOGGLE_PREFIX = "pc:tog:"
PC_REDEEM_PREFIX = "pc:red:"
PC_BACK_LIST = "pc:back:list"


def promo_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать промокод", callback_data=PC_CREATE)],
            [InlineKeyboardButton(text="📋 Список промокодов", callback_data=PC_LIST)],
            [InlineKeyboardButton(text="🔎 Найти промокод", callback_data=PC_SEARCH)],
            [InlineKeyboardButton(text="📊 Статистика", callback_data=PC_STATS)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=PC_BACK_ADMIN)],
        ],
    )


def promo_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=PC_CANCEL)]],
    )


def promo_discount_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Процент", callback_data=f"{PC_TYPE_PREFIX}{PromoDiscountType.PERCENT.value}")],
            [
                InlineKeyboardButton(
                    text="💵 Фикс. сумма",
                    callback_data=f"{PC_TYPE_PREFIX}{PromoDiscountType.FIXED_AMOUNT.value}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Доп. дни",
                    callback_data=f"{PC_TYPE_PREFIX}{PromoDiscountType.EXTRA_DAYS.value}",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PC_CANCEL)],
        ],
    )


def promo_dates_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Без ограничений по датам", callback_data=PC_SKIP_DATES)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PC_CANCEL)],
        ],
    )


def promo_max_uses_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="♾ Безлимит", callback_data=PC_UNLIMITED_USES)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PC_CANCEL)],
        ],
    )


def promo_scope_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Покупка и продление", callback_data=f"{PC_SCOPE_PREFIX}{PromoRequestScope.ANY.value}")],
            [InlineKeyboardButton(text="🛍 Только покупка", callback_data=f"{PC_SCOPE_PREFIX}{PromoRequestScope.PURCHASE.value}")],
            [InlineKeyboardButton(text="🔄 Только продление", callback_data=f"{PC_SCOPE_PREFIX}{PromoRequestScope.RENEWAL.value}")],
            [InlineKeyboardButton(text="📦 Конкретный тариф", callback_data=f"{PC_SCOPE_PREFIX}plan")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PC_CANCEL)],
        ],
    )


def promo_plan_keyboard(plans: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"{PC_PLAN_PREFIX}{plan_id}")]
        for plan_id, name in plans
    ]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=PC_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Создать", callback_data=PC_CONFIRM)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=PC_CANCEL)],
        ],
    )


def promo_list_keyboard(items: list[PromoCodeInfo]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items[:20]:
        status = "✅" if item.is_active else "🚫"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {item.code}",
                    callback_data=f"{PC_ITEM_PREFIX}{item.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=PC_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_item_keyboard(promo_id: int, *, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "🚫 Отключить" if is_active else "✅ Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"{PC_TOGGLE_PREFIX}{promo_id}")],
            [InlineKeyboardButton(text="📜 Использования", callback_data=f"{PC_REDEEM_PREFIX}{promo_id}")],
            [InlineKeyboardButton(text="🔙 К списку", callback_data=PC_LIST)],
        ],
    )


def promo_back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=PC_HOME)]],
    )
