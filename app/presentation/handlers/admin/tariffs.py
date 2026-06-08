from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.services.plan_service import PlanService
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.handlers.admin.tariff_helpers import send_tariff_list
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_tariffs import CB_BACK_ADMIN, CB_LIST

router = Router(name="admin_tariffs")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.message(F.text == "💰 Тарифы")
async def handle_admin_tariffs(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    await state.clear()
    await send_tariff_list(message, plan_service)


@router.callback_query(F.data == CB_LIST)
async def handle_tariff_list_callback(callback: CallbackQuery, state: FSMContext, plan_service: PlanService) -> None:
    await state.clear()
    await send_tariff_list(callback, plan_service)


@router.callback_query(F.data == CB_BACK_ADMIN)
async def handle_back_to_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer("🔐 Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()
