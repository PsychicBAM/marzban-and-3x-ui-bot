from __future__ import annotations

import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.services.daily_report_service import DailyReportService
from app.application.services.system_status_service import SystemStatusService
from app.infrastructure.scheduler.expiry_scheduler import get_expiry_scheduler
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_system_status import (
    SS_BACK,
    SS_SEND_NOW,
    SS_SET_TIME,
    SS_TOGGLE_REPORT,
    system_status_keyboard,
)
from app.presentation.states.support_ticket import AdminDailyReportStates

logger = logging.getLogger(__name__)

router = Router(name="admin_system_status")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())

ERROR_TEXT = "❌ Не удалось получить статус системы. Попробуйте позже."


@router.message(F.text == "🩺 Статус системы")
async def handle_system_status(
    message: Message,
    system_status_service: SystemStatusService,
    daily_report_service: DailyReportService,
) -> None:
    try:
        snapshot = await system_status_service.collect()
        text = system_status_service.format_admin_message(snapshot)
        report_settings = await daily_report_service.get_settings()
        text += "\n\n📅 Ежедневный отчёт: " + ("вкл" if report_settings.is_enabled else "выкл")
        text += f"\n🕘 Время: {report_settings.report_hour:02d}:{report_settings.report_minute:02d}"
        keyboard = system_status_keyboard(report_enabled=report_settings.is_enabled)
    except Exception:
        logger.exception("System status collection failed")
        await message.answer(ERROR_TEXT, reply_markup=admin_main_keyboard())
        return
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == SS_TOGGLE_REPORT)
async def handle_toggle_report(
    callback: CallbackQuery,
    daily_report_service: DailyReportService,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    settings = await daily_report_service.get_settings()
    await daily_report_service.set_enabled(
        enabled=not settings.is_enabled,
        admin_telegram_id=callback.from_user.id,
    )
    scheduler = get_expiry_scheduler()
    if scheduler is not None:
        await scheduler.reschedule_daily_report()
    new_settings = await daily_report_service.get_settings()
    label = "вкл" if new_settings.is_enabled else "выкл"
    await callback.answer(f"Ежедневный отчёт: {label}", show_alert=True)


@router.callback_query(F.data == SS_SET_TIME)
async def handle_set_report_time(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminDailyReportStates.waiting_time)
    if callback.message:
        await callback.message.answer("Введите время отчёта в формате ЧЧ:ММ (например 09:00). /cancel — отмена")
    await callback.answer()


@router.message(StateFilter(AdminDailyReportStates.waiting_time))
async def handle_report_time_input(
    message: Message,
    state: FSMContext,
    daily_report_service: DailyReportService,
) -> None:
    if message.from_user is None or not message.text:
        return
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", message.text.strip())
    if not match:
        await message.answer("Некорректный формат. Пример: 09:00")
        return
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        await message.answer("Некорректное время.")
        return
    await daily_report_service.set_time(
        hour=hour,
        minute=minute,
        admin_telegram_id=message.from_user.id,
    )
    await state.clear()
    scheduler = get_expiry_scheduler()
    if scheduler is not None:
        await scheduler.reschedule_daily_report()
    await message.answer(f"✅ Время отчёта: {hour:02d}:{minute:02d}", reply_markup=admin_main_keyboard())


@router.callback_query(F.data == SS_SEND_NOW)
async def handle_send_report_now(
    callback: CallbackQuery,
    bot: Bot,
    daily_report_service: DailyReportService,
) -> None:
    sent, failed = await daily_report_service.send_to_admins(bot)
    if sent:
        await callback.answer(f"✅ Отчёт отправлен ({sent} адм.)", show_alert=True)
    else:
        await callback.answer("❌ Не удалось отправить отчёт.", show_alert=True)
    if failed:
        logger.warning("admin_daily_report_failed", extra={"failed": failed})


@router.callback_query(F.data == SS_BACK)
async def handle_status_back(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer("🔐 Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()
