from __future__ import annotations

from aiogram.types import CallbackQuery, Message

from app.application.services.plan_service import PlanService
from app.presentation.keyboards.admin_tariffs import admin_tariffs_menu_keyboard


async def send_tariff_list(
    target: Message | CallbackQuery,
    plan_service: PlanService,
) -> None:
    plans = await plan_service.list_all_plans()
    text = plan_service.format_admin_all_plans_list(plans)
    keyboard = admin_tariffs_menu_keyboard()

    if isinstance(target, CallbackQuery):
        if target.message is None:
            await target.answer()
            return
        await target.message.answer(text, reply_markup=keyboard)
        await target.answer()
        return

    await target.answer(text, reply_markup=keyboard)
