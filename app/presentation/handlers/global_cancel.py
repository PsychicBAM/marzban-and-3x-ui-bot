from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config.settings import Settings
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_settings import settings_home_keyboard
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.i18n import t

logger = logging.getLogger(__name__)

router = Router(name="global_cancel")

_SETTINGS_STATE_PREFIXES = (
    "AdminNotificationSettingsStates:",
    "PaymentSettingsStates:",
    "SupportSettingsStates:",
    "InstructionSettingsStates:",
    "CustomerSupportStates:",
    "AdminSupportStates:",
    "AdminDailyReportStates:",
)

_CANCEL_FILTER = or_f(Command("cancel"), F.text.casefold() == "/cancel")


def _is_settings_fsm_state(state: str | None) -> bool:
    if state is None:
        return False
    return state.startswith(_SETTINGS_STATE_PREFIXES)


@router.message(_CANCEL_FILTER, StateFilter("*"))
async def handle_global_cancel(
    message: Message,
    state: FSMContext,
    settings: Settings,
    lang: str,
) -> None:
    current_state = await state.get_state()
    user_id = message.from_user.id if message.from_user else None

    await state.clear()

    logger.info(
        "Global cancel handled",
        extra={"user_id": user_id, "previous_state": current_state},
    )

    if message.from_user is None:
        return

    if settings.is_admin(message.from_user.id):
        await message.answer("✅ Действие отменено.", reply_markup=admin_main_keyboard())
        if _is_settings_fsm_state(current_state):
            await message.answer(
                "⚙️ <b>Настройки бота</b>\n\nВыберите раздел:",
                reply_markup=settings_home_keyboard(),
            )
        return

    await message.answer(t(lang, "common.cancel_done"), reply_markup=customer_main_keyboard(lang))
