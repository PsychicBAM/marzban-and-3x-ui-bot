from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message

from app.application.services.system_status_service import SystemStatusService
from app.presentation.filters.admin import IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard

logger = logging.getLogger(__name__)

router = Router(name="admin_system_status")
router.message.filter(IsAdminFilter())

ERROR_TEXT = "❌ Не удалось получить статус системы. Попробуйте позже."


@router.message(F.text == "🩺 Статус системы")
async def handle_system_status(message: Message, system_status_service: SystemStatusService) -> None:
    try:
        snapshot = await system_status_service.collect()
        text = system_status_service.format_admin_message(snapshot)
    except Exception:
        logger.exception("System status collection failed")
        await message.answer(ERROR_TEXT, reply_markup=admin_main_keyboard())
        return
    await message.answer(text, reply_markup=admin_main_keyboard())
