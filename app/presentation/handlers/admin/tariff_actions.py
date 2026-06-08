from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.application.exceptions import PlanValidationError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.plan_service import PlanService
from app.domain.enums import AdminActionType
from app.presentation.filters.admin import IsAdminCallbackFilter
from app.presentation.handlers.admin.tariff_helpers import send_tariff_list
from app.presentation.keyboards.admin_tariffs import (
    CB_DISABLE,
    CB_DISABLE_PREFIX,
    CB_ENABLE,
    CB_ENABLE_PREFIX,
    plan_list_keyboard,
)

router = Router(name="admin_tariff_actions")
router.callback_query.filter(IsAdminCallbackFilter())


@router.callback_query(F.data == CB_DISABLE)
async def handle_disable_menu(callback: CallbackQuery, plan_service: PlanService) -> None:
    if callback.message is None:
        await callback.answer()
        return

    plans = [plan for plan in await plan_service.list_all_plans() if plan.is_active]
    if not plans:
        await callback.answer("Нет активных тарифов для отключения.", show_alert=True)
        return

    await callback.message.edit_text(
        "🚫 <b>Выключить тариф</b>\n\nВыберите тариф:",
        reply_markup=plan_list_keyboard(plans, callback_prefix=CB_DISABLE_PREFIX),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(CB_DISABLE_PREFIX))
async def handle_disable_plan(
    callback: CallbackQuery,
    plan_service: PlanService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, CB_DISABLE_PREFIX)
    if plan_id is None:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    try:
        plan = await plan_service.set_plan_active(plan_id, is_active=False)
    except PlanValidationError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.TARIFF_UPDATED,
        details={
            "plan_id": plan.id,
            "field": "is_active",
            "old": True,
            "new": False,
        },
    )
    await callback.answer("Тариф отключён.")
    await send_tariff_list(callback, plan_service)


@router.callback_query(F.data == CB_ENABLE)
async def handle_enable_menu(callback: CallbackQuery, plan_service: PlanService) -> None:
    if callback.message is None:
        await callback.answer()
        return

    plans = [plan for plan in await plan_service.list_all_plans() if not plan.is_active]
    if not plans:
        await callback.answer("Нет отключённых тарифов.", show_alert=True)
        return

    await callback.message.edit_text(
        "✅ <b>Включить тариф</b>\n\nВыберите тариф:",
        reply_markup=plan_list_keyboard(plans, callback_prefix=CB_ENABLE_PREFIX),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(CB_ENABLE_PREFIX))
async def handle_enable_plan(
    callback: CallbackQuery,
    plan_service: PlanService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, CB_ENABLE_PREFIX)
    if plan_id is None:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    try:
        plan = await plan_service.set_plan_active(plan_id, is_active=True)
    except PlanValidationError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.TARIFF_UPDATED,
        details={
            "plan_id": plan.id,
            "field": "is_active",
            "old": False,
            "new": True,
        },
    )
    await callback.answer("Тариф включён.")
    await send_tariff_list(callback, plan_service)


def _parse_plan_id(callback_data: str, prefix: str) -> int | None:
    try:
        return int(callback_data.removeprefix(prefix))
    except ValueError:
        return None
