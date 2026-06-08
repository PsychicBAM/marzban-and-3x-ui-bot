from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import PlanValidationError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.settings_service import SettingsService
from app.domain.enums import AdminActionType
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin_settings import (
    PAY_CLEAR,
    PAY_EDIT,
    SET_PAYMENT,
    payment_settings_keyboard,
)
from app.presentation.states.admin_payment_settings import PaymentSettingsStates

router = Router(name="admin_settings_payment")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.callback_query(F.data == SET_PAYMENT)
async def handle_payment_screen(
    callback: CallbackQuery,
    settings_service: SettingsService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    text = await settings_service.format_payment_details_admin()
    await callback.message.edit_text(text, reply_markup=payment_settings_keyboard())
    await callback.answer()


@router.callback_query(F.data == PAY_EDIT)
async def handle_payment_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PaymentSettingsStates.waiting_details)
    if callback.message is not None:
        await callback.message.answer(
            "💳 Введите реквизиты оплаты (можно несколько строк):\n<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.message(StateFilter(PaymentSettingsStates.waiting_details), F.text, ~F.text.startswith("/"))
async def handle_payment_edit_value(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    try:
        await settings_service.set_payment_details(message.text)
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return

    await state.clear()
    await admin_log_service.log(
        admin_telegram_id=message.from_user.id,
        action=AdminActionType.PAYMENT_SETTINGS_UPDATED,
        details={"field": "payment_details"},
    )
    text = await settings_service.format_payment_details_admin()
    await message.answer(f"✅ Реквизиты сохранены.\n\n{text}", reply_markup=payment_settings_keyboard())


@router.callback_query(F.data == PAY_CLEAR)
async def handle_payment_clear(
    callback: CallbackQuery,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    await settings_service.clear_payment_details()
    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.PAYMENT_SETTINGS_CLEARED,
        details={"field": "payment_details"},
    )
    text = await settings_service.format_payment_details_admin()
    await callback.message.edit_text(text, reply_markup=payment_settings_keyboard())
    await callback.answer("Очищено.")
