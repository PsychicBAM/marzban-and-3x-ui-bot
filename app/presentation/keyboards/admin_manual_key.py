from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.plan import PlanInfo
from app.domain.enums import IssuingMode

MK_CANCEL = "mk:cancel"
MK_MODE_EXISTING = "mk:mode:existing"
MK_MODE_STANDALONE = "mk:mode:standalone"

MK_USER_PREFIX = "mk:user:"
MK_EXTEND_YES = "mk:extend:yes"
MK_EXTEND_NO = "mk:extend:no"
MK_NAME_OK = "mk:name:ok"
MK_NAME_EDIT = "mk:name:edit"

MK_PARAMS_TARIFF = "mk:params:tariff"
MK_PARAMS_CUSTOM = "mk:params:custom"

MK_PLAN_PREFIX = "mk:plan:"
MK_ISSUING_PREFIX = "mk:issuing:"

MK_CONFIRM_CREATE = "mk:confirm:create"
MK_CONFIRM_CANCEL = "mk:confirm:cancel"

MK_SEND_CUSTOMER = "mk:send:customer"
MK_DONE_ADMIN = "mk:done:admin"
MK_SKIP_COMMENT = "mk:comment:skip"


def mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Для существующего клиента", callback_data=MK_MODE_EXISTING)],
            [InlineKeyboardButton(text="🧾 Ручной ключ без клиента", callback_data=MK_MODE_STANDALONE)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CANCEL)],
        ],
    )


def user_search_results_keyboard(users: list) -> InlineKeyboardMarkup:
    from app.infrastructure.db.models.user import User

    buttons = []
    for user in users:
        if not isinstance(user, User):
            continue
        name = " ".join(part for part in [user.first_name, user.last_name] if part) or "Пользователь"
        username = f"@{user.username}" if user.username else "—"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{name} ({username})",
                    callback_data=f"{MK_USER_PREFIX}{user.id}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def extend_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Продлить существующий", callback_data=MK_EXTEND_YES)],
            [InlineKeyboardButton(text="🆕 Создать отдельный ключ", callback_data=MK_EXTEND_NO)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CANCEL)],
        ],
    )


def account_name_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Использовать это имя", callback_data=MK_NAME_OK)],
            [InlineKeyboardButton(text="✏️ Ввести другое имя", callback_data=MK_NAME_EDIT)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CANCEL)],
        ],
    )


def params_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Выбрать тариф", callback_data=MK_PARAMS_TARIFF)],
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=MK_PARAMS_CUSTOM)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CANCEL)],
        ],
    )


def tariff_keyboard(plans: list[PlanInfo]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{p.name} — {p.duration_days} дн.", callback_data=f"{MK_PLAN_PREFIX}{p.id}")]
        for p in plans
    ]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def issuing_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Marzban", callback_data=f"{MK_ISSUING_PREFIX}{IssuingMode.MARZBAN.value}")],
            [InlineKeyboardButton(text="3x-ui", callback_data=f"{MK_ISSUING_PREFIX}{IssuingMode.XUI.value}")],
            [InlineKeyboardButton(text="Обе панели", callback_data=f"{MK_ISSUING_PREFIX}{IssuingMode.BOTH.value}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CANCEL)],
        ],
    )


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Создать", callback_data=MK_CONFIRM_CREATE)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CONFIRM_CANCEL)],
        ],
    )


def skip_comment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=MK_SKIP_COMMENT)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=MK_CANCEL)],
        ],
    )


def after_create_keyboard(*, for_existing_user: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if for_existing_user:
        rows.append([InlineKeyboardButton(text="📩 Отправить клиенту", callback_data=MK_SEND_CUSTOMER)])
    rows.append([InlineKeyboardButton(text="🏠 В админ-панель", callback_data=MK_DONE_ADMIN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
