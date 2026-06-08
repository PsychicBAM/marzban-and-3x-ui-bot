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
    INS_CLEAR,
    INS_EDIT_TEXT,
    INS_EDIT_URL,
    INS_TOGGLE,
    SET_INSTRUCTION,
    instruction_settings_keyboard,
)
from app.presentation.states.admin_instruction_settings import InstructionSettingsStates

router = Router(name="admin_settings_instruction")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.callback_query(F.data == SET_INSTRUCTION)
async def handle_instruction_screen(
    callback: CallbackQuery,
    settings_service: SettingsService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    config = await settings_service.get_instruction_settings()
    text = settings_service.format_instruction_settings_admin(config)
    await callback.message.edit_text(text, reply_markup=instruction_settings_keyboard(config))
    await callback.answer()


@router.callback_query(F.data == INS_EDIT_TEXT)
async def handle_instruction_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(InstructionSettingsStates.waiting_text)
    if callback.message is not None:
        await callback.message.answer(
            "Введите текст инструкции (можно несколько строк):\n"
            "Отправьте <code>-</code> чтобы очистить текст.\n"
            "<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.callback_query(F.data == INS_EDIT_URL)
async def handle_instruction_url_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(InstructionSettingsStates.waiting_url)
    if callback.message is not None:
        await callback.message.answer(
            "Введите ссылку на инструкцию (http:// или https://).\n"
            "Отправьте <code>-</code> чтобы очистить ссылку.\n"
            "<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.callback_query(F.data == INS_TOGGLE)
async def handle_instruction_toggle(
    callback: CallbackQuery,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    config = await settings_service.get_instruction_settings()
    await settings_service.update_instruction_settings(enabled=not config.enabled)
    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.INSTRUCTION_SETTINGS_UPDATED,
        details={"field": "instruction_enabled", "value": not config.enabled},
    )
    refreshed = await settings_service.get_instruction_settings()
    await callback.message.edit_text(
        settings_service.format_instruction_settings_admin(refreshed),
        reply_markup=instruction_settings_keyboard(refreshed),
    )
    await callback.answer("Сохранено.")


@router.message(StateFilter(InstructionSettingsStates.waiting_text), F.text)
async def handle_instruction_text_value(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None or message.text is None or message.text.startswith("/"):
        return
    raw = message.text.strip()
    text = "" if raw == "-" else raw
    await settings_service.update_instruction_settings(text=text)
    await _finish_instruction_edit(
        message,
        state,
        settings_service,
        admin_log_service,
        field="instruction_text",
    )


@router.message(StateFilter(InstructionSettingsStates.waiting_url), F.text)
async def handle_instruction_url_value(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None or message.text is None or message.text.startswith("/"):
        return
    raw = message.text.strip()
    try:
        url = "" if raw == "-" else settings_service.validate_support_url(raw)
        await settings_service.update_instruction_settings(url=url)
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return

    await _finish_instruction_edit(
        message,
        state,
        settings_service,
        admin_log_service,
        field="instruction_url",
    )


@router.callback_query(F.data == INS_CLEAR)
async def handle_instruction_clear(
    callback: CallbackQuery,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    await settings_service.clear_instruction_settings()
    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.INSTRUCTION_SETTINGS_CLEARED,
        details={},
    )
    config = await settings_service.get_instruction_settings()
    await callback.message.edit_text(
        settings_service.format_instruction_settings_admin(config),
        reply_markup=instruction_settings_keyboard(config),
    )
    await callback.answer("Очищено.")


async def _finish_instruction_edit(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
    *,
    field: str,
) -> None:
    if message.from_user is None:
        return
    await state.clear()
    await admin_log_service.log(
        admin_telegram_id=message.from_user.id,
        action=AdminActionType.INSTRUCTION_SETTINGS_UPDATED,
        details={"field": field},
    )
    config = await settings_service.get_instruction_settings()
    text = settings_service.format_instruction_settings_admin(config)
    await message.answer(f"✅ Сохранено.\n\n{text}", reply_markup=instruction_settings_keyboard(config))
