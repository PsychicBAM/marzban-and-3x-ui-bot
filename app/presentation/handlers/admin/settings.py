from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import PlanValidationError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.expiry_notification_service import ExpiryNotificationService
from app.application.services.settings_service import (
    CHECK_INTERVAL_EVERY_1_MINUTE,
    SettingsService,
)
from app.domain.enums import AdminActionType
from app.infrastructure.scheduler.expiry_scheduler import get_expiry_scheduler
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_settings import (
    NTF_DAYS,
    NTF_EXPIRED_TOGGLE,
    NTF_INTERVAL,
    NTF_INTERVAL_PREFIX,
    NTF_SEND_TEST,
    NTF_TEST_TOGGLE,
    NTF_TOGGLE,
    SET_HOME,
    SET_MENU,
    SET_NOTIFICATIONS,
    notification_interval_keyboard,
    notification_settings_keyboard,
    settings_home_keyboard,
)
from app.presentation.states.admin_instruction_settings import InstructionSettingsStates
from app.presentation.states.admin_notification_settings import AdminNotificationSettingsStates
from app.presentation.states.admin_payment_settings import PaymentSettingsStates
from app.presentation.states.admin_support_settings import SupportSettingsStates

router = Router(name="admin_settings")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())

SETTINGS_FSM_STATES = (
    AdminNotificationSettingsStates.waiting_days,
    PaymentSettingsStates.waiting_details,
    SupportSettingsStates.waiting_username,
    SupportSettingsStates.waiting_url,
    SupportSettingsStates.waiting_text,
    InstructionSettingsStates.waiting_text,
    InstructionSettingsStates.waiting_url,
)


@router.message(F.text == "⚙️ Настройки")
async def handle_settings_menu(message: Message) -> None:
    await message.answer(
        "⚙️ <b>Настройки бота</b>\n\nВыберите раздел:",
        reply_markup=settings_home_keyboard(),
    )


@router.callback_query(F.data == SET_HOME)
async def handle_settings_back_admin(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer("Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == SET_MENU)
async def handle_settings_menu_screen(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text(
        "⚙️ <b>Настройки бота</b>\n\nВыберите раздел:",
        reply_markup=settings_home_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == SET_NOTIFICATIONS)
async def handle_notification_settings_screen(
    callback: CallbackQuery,
    settings_service: SettingsService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    config = await settings_service.get_notification_settings()
    text = settings_service.format_notification_settings(config)
    await callback.message.edit_text(text, reply_markup=notification_settings_keyboard(config))
    await callback.answer()


@router.callback_query(F.data == NTF_TOGGLE)
async def handle_notifications_toggle(
    callback: CallbackQuery,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    config = await settings_service.get_notification_settings()
    await settings_service.set_notifications_enabled(not config.enabled)
    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.NOTIFICATION_SETTINGS_UPDATED,
        details={"field": "notifications_enabled", "value": not config.enabled},
    )
    refreshed = await settings_service.get_notification_settings()
    await callback.message.edit_text(
        settings_service.format_notification_settings(refreshed),
        reply_markup=notification_settings_keyboard(refreshed),
    )
    await callback.answer("Сохранено.")


@router.callback_query(F.data == NTF_TEST_TOGGLE)
async def handle_test_mode_toggle(
    callback: CallbackQuery,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    config = await settings_service.get_notification_settings()
    await settings_service.set_notification_test_mode(not config.test_mode)
    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.NOTIFICATION_SETTINGS_UPDATED,
        details={"field": "notification_test_mode", "value": not config.test_mode},
    )
    refreshed = await settings_service.get_notification_settings()
    await callback.message.edit_text(
        settings_service.format_notification_settings(refreshed),
        reply_markup=notification_settings_keyboard(refreshed),
    )
    await callback.answer("Сохранено.")


@router.callback_query(F.data == NTF_EXPIRED_TOGGLE)
async def handle_expired_toggle(
    callback: CallbackQuery,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    config = await settings_service.get_notification_settings()
    await settings_service.set_notify_expired_enabled(not config.notify_expired_enabled)
    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.NOTIFICATION_SETTINGS_UPDATED,
        details={"field": "notify_expired_enabled", "value": not config.notify_expired_enabled},
    )
    refreshed = await settings_service.get_notification_settings()
    await callback.message.edit_text(
        settings_service.format_notification_settings(refreshed),
        reply_markup=notification_settings_keyboard(refreshed),
    )
    await callback.answer("Сохранено.")


@router.callback_query(F.data == NTF_DAYS)
async def handle_change_days_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminNotificationSettingsStates.waiting_days)
    if callback.message is not None:
        await callback.message.answer(
            "📅 Введите дни напоминаний через запятую, например: <code>10,7,3,1</code>\n"
            "<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.message(StateFilter(AdminNotificationSettingsStates.waiting_days), F.text)
async def handle_change_days_value(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text.startswith("/"):
        return
    try:
        days = settings_service.parse_notification_days(message.text)
        await settings_service.set_notification_days(days)
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return

    await state.clear()
    await admin_log_service.log(
        admin_telegram_id=message.from_user.id,
        action=AdminActionType.NOTIFICATION_SETTINGS_UPDATED,
        details={"field": "notification_days", "value": days},
    )
    config = await settings_service.get_notification_settings()
    await message.answer(
        f"✅ Дни напоминаний сохранены: {', '.join(str(d) for d in config.reminder_days)}",
        reply_markup=notification_settings_keyboard(config),
    )


@router.callback_query(F.data == NTF_INTERVAL)
async def handle_interval_menu(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text(
        "⏱ <b>Интервал проверки уведомлений</b>\n\n"
        "⚠️ Режим «каждую минуту» нужен только для проверки.",
        reply_markup=notification_interval_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(NTF_INTERVAL_PREFIX))
async def handle_interval_select(
    callback: CallbackQuery,
    settings_service: SettingsService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    interval = callback.data.removeprefix(NTF_INTERVAL_PREFIX)
    if interval == CHECK_INTERVAL_EVERY_1_MINUTE:
        await callback.answer(
            "⚠️ Режим каждую минуту нужен только для проверки.",
            show_alert=True,
        )

    await settings_service.set_notification_check_interval(interval)
    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.NOTIFICATION_SETTINGS_UPDATED,
        details={"field": "notification_check_interval", "value": interval},
    )

    scheduler = get_expiry_scheduler()
    if scheduler is not None and scheduler.reschedule(interval):
        note = "✅ Интервал применён."
    else:
        note = "Настройка сохранена. Новый интервал применится после перезапуска бота."

    config = await settings_service.get_notification_settings()
    await callback.message.edit_text(
        f"{settings_service.format_notification_settings(config)}\n\n{note}",
        reply_markup=notification_settings_keyboard(config),
    )
    await callback.answer()


@router.callback_query(F.data == NTF_SEND_TEST)
async def handle_send_test(
    callback: CallbackQuery,
    bot: Bot,
    expiry_notification_service: ExpiryNotificationService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    text = await expiry_notification_service.send_test_to_admin(
        bot,
        admin_telegram_id=callback.from_user.id,
    )
    await callback.message.answer(text)
    await callback.answer()


@router.message(Command("cancel"), StateFilter(*SETTINGS_FSM_STATES))
async def handle_settings_fsm_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Отменено.",
        reply_markup=settings_home_keyboard(),
    )
