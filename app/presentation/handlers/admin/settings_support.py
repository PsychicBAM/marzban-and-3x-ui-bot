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
    SET_SUPPORT,
    SUP_CLEAR,
    SUP_EDIT_TEXT,
    SUP_EDIT_URL,
    SUP_EDIT_USERNAME,
    support_settings_keyboard,
)
from app.presentation.states.admin_support_settings import SupportSettingsStates

router = Router(name="admin_settings_support")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.callback_query(F.data == SET_SUPPORT)
async def handle_support_screen(
    callback: CallbackQuery,
    settings_service: SettingsService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    config = await settings_service.get_support_settings()
    text = settings_service.format_support_settings_admin(config)
    await callback.message.edit_text(text, reply_markup=support_settings_keyboard())
    await callback.answer()


@router.callback_query(F.data == SUP_EDIT_USERNAME)
async def handle_support_username_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportSettingsStates.waiting_username)
    if callback.message is not None:
        await callback.message.answer(
            "Введите username поддержки (с @ или без):\n<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.callback_query(F.data == SUP_EDIT_URL)
async def handle_support_url_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportSettingsStates.waiting_url)
    if callback.message is not None:
        await callback.message.answer(
            "Введите ссылку поддержки (http:// или https://).\n"
            "Отправьте <code>-</code> чтобы очистить ссылку.\n"
            "<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.callback_query(F.data == SUP_EDIT_TEXT)
async def handle_support_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportSettingsStates.waiting_text)
    if callback.message is not None:
        await callback.message.answer(
            "Введите текст сообщения поддержки (можно несколько строк):\n"
            "Отправьте <code>-</code> чтобы очистить текст.\n"
            "<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.message(StateFilter(SupportSettingsStates.waiting_username), F.text, ~F.text.startswith("/"))
async def handle_support_username_value(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    try:
        username = settings_service.normalize_support_username(message.text)
        await settings_service.update_support_settings(username=username)
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return

    await _finish_support_edit(message, state, settings_service, admin_log_service, field="support_username")


@router.message(StateFilter(SupportSettingsStates.waiting_url), F.text, ~F.text.startswith("/"))
async def handle_support_url_value(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    raw = message.text.strip()
    try:
        url = "" if raw == "-" else settings_service.validate_support_url(raw)
        await settings_service.update_support_settings(url=url)
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return

    await _finish_support_edit(message, state, settings_service, admin_log_service, field="support_url")


@router.message(StateFilter(SupportSettingsStates.waiting_text), F.text, ~F.text.startswith("/"))
async def handle_support_text_value(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    raw = message.text.strip()
    text = "" if raw == "-" else raw
    await settings_service.update_support_settings(text=text)
    await _finish_support_edit(message, state, settings_service, admin_log_service, field="support_text")


@router.callback_query(F.data == SUP_CLEAR)
async def handle_support_clear(
    callback: CallbackQuery,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    await settings_service.clear_support_settings()
    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.SUPPORT_SETTINGS_CLEARED,
        details={},
    )
    config = await settings_service.get_support_settings()
    await callback.message.edit_text(
        settings_service.format_support_settings_admin(config),
        reply_markup=support_settings_keyboard(),
    )
    await callback.answer("Очищено.")


async def _finish_support_edit(
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
        action=AdminActionType.SUPPORT_SETTINGS_UPDATED,
        details={"field": field},
    )
    config = await settings_service.get_support_settings()
    text = settings_service.format_support_settings_admin(config)
    await message.answer(f"✅ Сохранено.\n\n{text}", reply_markup=support_settings_keyboard())
