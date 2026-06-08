from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import PlanValidationError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.plan_service import FIELD_LABELS, PlanService
from app.domain.enums import AdminActionType
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin_tariffs import (
    CB_EDIT,
    CB_EDIT_FIELD_PREFIX,
    CB_EDIT_SELECT_PREFIX,
    CB_ISSUING_EDIT_PREFIX,
    CB_LIST,
    edit_fields_keyboard,
    issuing_mode_keyboard,
    plan_list_keyboard,
)
from app.presentation.states.tariff import TariffEditStates

router = Router(name="admin_tariff_edit")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.callback_query(F.data == CB_EDIT)
async def handle_edit_menu(callback: CallbackQuery, state: FSMContext, plan_service: PlanService) -> None:
    await state.clear()
    if callback.message is None:
        await callback.answer()
        return

    plans = await plan_service.list_all_plans()
    if not plans:
        await callback.answer("Тарифов пока нет.", show_alert=True)
        return

    await callback.message.edit_text(
        "✏️ <b>Редактирование тарифа</b>\n\nВыберите тариф:",
        reply_markup=plan_list_keyboard(plans, callback_prefix=CB_EDIT_SELECT_PREFIX),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(CB_EDIT_SELECT_PREFIX))
async def handle_edit_select_plan(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
) -> None:
    await state.clear()
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, CB_EDIT_SELECT_PREFIX)
    if plan_id is None:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    plan = await plan_service.get_plan(plan_id)
    if plan is None:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    text = (
        f"{plan_service.format_admin_plan_full(plan)}\n\n"
        "Выберите поле для редактирования:"
    )
    await callback.message.edit_text(text, reply_markup=edit_fields_keyboard(plan.id))
    await callback.answer()


@router.callback_query(F.data.startswith(CB_EDIT_FIELD_PREFIX))
async def handle_edit_select_field(callback: CallbackQuery, state: FSMContext, plan_service: PlanService) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    payload = callback.data.removeprefix(CB_EDIT_FIELD_PREFIX)
    plan_id_str, _, field = payload.partition(":")
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    plan = await plan_service.get_plan(plan_id)
    if plan is None:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    if field == "issuing_mode":
        await callback.message.edit_text(
            f"Редактирование тарифа <b>#{plan.id}</b>\n\nВыберите новый режим выдачи:",
            reply_markup=issuing_mode_keyboard(
                callback_prefix=f"{CB_ISSUING_EDIT_PREFIX}{plan_id}:",
                back_callback=f"{CB_EDIT_SELECT_PREFIX}{plan_id}",
            ),
        )
        await callback.answer()
        return

    await state.update_data(plan_id=plan_id, field=field)
    await state.set_state(TariffEditStates.enter_value)
    await callback.message.answer(plan_service.get_field_prompt(field))
    await callback.answer()


@router.callback_query(F.data.startswith(CB_ISSUING_EDIT_PREFIX))
async def handle_edit_issuing_mode(
    callback: CallbackQuery,
    plan_service: PlanService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    payload = callback.data.removeprefix(CB_ISSUING_EDIT_PREFIX)
    plan_id_str, _, mode = payload.partition(":")
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    try:
        plan, old_value, new_value = await plan_service.set_plan_issuing_mode(plan_id, mode)
    except PlanValidationError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    await _log_field_update(
        admin_log_service,
        admin_telegram_id=callback.from_user.id,
        plan_id=plan.id,
        field="issuing_mode",
        old_value=old_value,
        new_value=new_value,
        plan_service=plan_service,
    )
    await callback.message.edit_text(
        _build_edit_success_text(plan_service, plan, "issuing_mode", old_value, new_value),
        reply_markup=edit_fields_keyboard(plan.id),
    )
    await callback.answer("Сохранено.")


@router.message(StateFilter(TariffEditStates.enter_value))
async def handle_edit_enter_value(
    message: Message,
    state: FSMContext,
    plan_service: PlanService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    plan_id = data.get("plan_id")
    field = data.get("field")
    if not isinstance(plan_id, int) or not isinstance(field, str):
        await state.clear()
        await message.answer("Сессия редактирования истекла. Откройте тарифы заново.")
        return

    try:
        plan, old_value, new_value = await plan_service.update_plan_field(
            plan_id,
            field,
            message.text or "",
        )
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return

    await _log_field_update(
        admin_log_service,
        admin_telegram_id=message.from_user.id,
        plan_id=plan.id,
        field=field,
        old_value=old_value,
        new_value=new_value,
        plan_service=plan_service,
    )
    await state.clear()
    await message.answer(
        _build_edit_success_text(plan_service, plan, field, old_value, new_value),
        reply_markup=edit_fields_keyboard(plan.id),
    )


@router.message(Command("cancel"), StateFilter(TariffEditStates))
async def edit_cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Редактирование отменено.")


async def _log_field_update(
    admin_log_service: AdminLogService,
    *,
    admin_telegram_id: int,
    plan_id: int,
    field: str,
    old_value: object,
    new_value: object,
    plan_service: PlanService,
) -> None:
    await admin_log_service.log(
        admin_telegram_id=admin_telegram_id,
        action=AdminActionType.TARIFF_UPDATED,
        details={
            "plan_id": plan_id,
            "field": field,
            "old": plan_service.format_field_value(field, old_value),
            "new": plan_service.format_field_value(field, new_value),
        },
    )


def _build_edit_success_text(
    plan_service: PlanService,
    plan: object,
    field: str,
    old_value: object,
    new_value: object,
) -> str:
    old_fmt = plan_service.format_field_value(field, old_value)
    new_fmt = plan_service.format_field_value(field, new_value)
    from app.application.dto.plan import PlanInfo

    assert isinstance(plan, PlanInfo)
    return (
        f"✅ Поле <b>{FIELD_LABELS.get(field, field)}</b> обновлено.\n"
        f"{old_fmt} → {new_fmt}\n\n"
        f"{plan_service.format_admin_plan_full(plan)}\n\n"
        "Выберите поле для редактирования:"
    )


def _parse_plan_id(callback_data: str, prefix: str) -> int | None:
    try:
        return int(callback_data.removeprefix(prefix))
    except ValueError:
        return None
