from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.plan import PlanInfo
from app.application.services.plan_service import FIELD_LABELS

CB_LIST = "tariff:list"
CB_ADD = "tariff:add"
CB_EDIT = "tariff:edit"
CB_DISABLE = "tariff:disable"
CB_ENABLE = "tariff:enable"
CB_BACK_ADMIN = "tariff:back_admin"
CB_CREATE_CONFIRM = "tariff:cc"
CB_CREATE_CANCEL = "tariff:cx"
CB_EDIT_SELECT_PREFIX = "tariff:es:"
CB_EDIT_FIELD_PREFIX = "tariff:ef:"
CB_DISABLE_PREFIX = "tariff:dis:"
CB_ENABLE_PREFIX = "tariff:en:"
CB_ISSUING_CREATE_PREFIX = "tariff:im:"
CB_ISSUING_EDIT_PREFIX = "tariff:eu:"
CB_EDIT_BACK_PREFIX = "tariff:eb:"


def admin_tariffs_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить тариф", callback_data=CB_ADD)],
            [InlineKeyboardButton(text="✏️ Редактировать тариф", callback_data=CB_EDIT)],
            [InlineKeyboardButton(text="🚫 Выключить тариф", callback_data=CB_DISABLE)],
            [InlineKeyboardButton(text="✅ Включить тариф", callback_data=CB_ENABLE)],
            [InlineKeyboardButton(text="🏠 Назад в админ-панель", callback_data=CB_BACK_ADMIN)],
        ],
    )


def plan_list_keyboard(
    plans: list[PlanInfo],
    *,
    callback_prefix: str,
    back_callback: str = CB_LIST,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"#{plan.id} {plan.name}", callback_data=f"{callback_prefix}{plan.id}")]
        for plan in plans
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def create_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data=CB_CREATE_CONFIRM),
                InlineKeyboardButton(text="❌ Отмена", callback_data=CB_CREATE_CANCEL),
            ],
        ],
    )


def issuing_mode_keyboard(*, callback_prefix: str, back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Marzban", callback_data=f"{callback_prefix}marzban")],
            [InlineKeyboardButton(text="3x-ui", callback_data=f"{callback_prefix}xui")],
            [InlineKeyboardButton(text="Marzban + 3x-ui", callback_data=f"{callback_prefix}both")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)],
        ],
    )


def edit_fields_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{CB_EDIT_FIELD_PREFIX}{plan_id}:{field}")]
        for field, label in FIELD_LABELS.items()
    ]
    rows.append([InlineKeyboardButton(text="◀️ К списку тарифов", callback_data=CB_LIST)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
