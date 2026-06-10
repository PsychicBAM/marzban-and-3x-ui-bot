from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.enums import BroadcastTargetType

BC_HOME = "bc:home"
BC_CREATE = "bc:new"
BC_HISTORY = "bc:hist"
BC_BACK_ADMIN = "bc:adm"
BC_SKIP_PHOTO = "bc:photo:skip"
BC_TARGET_PREFIX = "bc:tgt:"
BC_CONFIRM_SEND = "bc:send"
BC_EDIT_TEXT = "bc:edit:text"
BC_EDIT_PHOTO = "bc:edit:photo"
BC_CANCEL = "bc:cancel"


def broadcast_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать рассылку", callback_data=BC_CREATE)],
            [InlineKeyboardButton(text="📋 История рассылок", callback_data=BC_HISTORY)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=BC_BACK_ADMIN)],
        ],
    )


def broadcast_skip_photo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Без фото", callback_data=BC_SKIP_PHOTO)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=BC_CANCEL)],
        ],
    )


def broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    options = [
        (BroadcastTargetType.ALL, "👥 Все пользователи"),
        (BroadcastTargetType.ACTIVE_VPN, "✅ С активным VPN"),
        (BroadcastTargetType.EXPIRED_VPN, "⛔ С истёкшим VPN"),
        (BroadcastTargetType.NO_ACTIVE_VPN, "📭 Без активного VPN"),
        (BroadcastTargetType.EXPIRING_SOON, "⏳ Истекает ≤7 дн."),
        (BroadcastTargetType.PROMO_ENABLED, "🔔 Подписаны на акции"),
    ]
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"{BC_TARGET_PREFIX}{target.value}")]
        for target, label in options
    ]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=BC_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Отправить", callback_data=BC_CONFIRM_SEND)],
            [
                InlineKeyboardButton(text="✏️ Изменить текст", callback_data=BC_EDIT_TEXT),
                InlineKeyboardButton(text="🖼 Изменить фото", callback_data=BC_EDIT_PHOTO),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=BC_CANCEL)],
        ],
    )


def promo_settings_keyboard(*, enabled: bool) -> InlineKeyboardMarkup:
    if enabled:
        toggle = InlineKeyboardButton(text="🔕 Выключить", callback_data="promo:off")
    else:
        toggle = InlineKeyboardButton(text="🔔 Включить", callback_data="promo:on")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle],
        ],
    )
