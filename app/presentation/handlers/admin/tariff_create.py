from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import PlanValidationError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.plan_service import PlanService
from app.domain.enums import AdminActionType
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.handlers.admin.tariff_helpers import send_tariff_list
from app.presentation.keyboards.admin_tariffs import (
    CB_ADD,
    CB_CREATE_CANCEL,
    CB_CREATE_CONFIRM,
    CB_ISSUING_CREATE_PREFIX,
    CB_LIST,
    create_confirm_keyboard,
    issuing_mode_keyboard,
)
from app.presentation.states.tariff import TariffCreateStates

router = Router(name="admin_tariff_create")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.callback_query(F.data == CB_ADD)
async def handle_add_tariff(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer(
        "➕ <b>Создание тарифа</b>\n\n"
        "Введите <b>название</b> тарифа:\n\n"
        "<i>Для отмены отправьте /cancel</i>",
    )
    await state.set_state(TariffCreateStates.name)
    await callback.answer()


@router.message(StateFilter(TariffCreateStates.name))
async def create_step_name(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    try:
        name = plan_service.parse_name(message.text or "")
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return
    await state.update_data(name=name)
    await state.set_state(TariffCreateStates.price)
    await message.answer("Введите <b>цену</b> тарифа в рублях (число ≥ 0):")


@router.message(StateFilter(TariffCreateStates.price))
async def create_step_price(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    try:
        price = plan_service.parse_price(message.text or "")
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return
    await state.update_data(price=str(price))
    await state.set_state(TariffCreateStates.duration_days)
    await message.answer("Введите <b>срок</b> тарифа в днях (целое число > 0):")


@router.message(StateFilter(TariffCreateStates.duration_days))
async def create_step_duration(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    try:
        days = plan_service.parse_duration_days(message.text or "")
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return
    await state.update_data(duration_days=days)
    await state.set_state(TariffCreateStates.traffic_limit_gb)
    await message.answer("Введите <b>лимит трафика</b> в ГБ (0 = безлимит):")


@router.message(StateFilter(TariffCreateStates.traffic_limit_gb))
async def create_step_traffic(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    try:
        traffic = plan_service.parse_traffic_limit_gb(message.text or "")
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return
    await state.update_data(traffic_limit_gb=traffic)
    await state.set_state(TariffCreateStates.ip_limit)
    await message.answer("Введите <b>лимит устройств</b> (0 = безлимит):")


@router.message(StateFilter(TariffCreateStates.ip_limit))
async def create_step_ip_limit(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    try:
        ip_limit = plan_service.parse_ip_limit(message.text or "")
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return
    await state.update_data(ip_limit=ip_limit)
    await state.set_state(TariffCreateStates.issuing_mode)
    await message.answer(
        "Выберите <b>режим выдачи</b>:",
        reply_markup=issuing_mode_keyboard(
            callback_prefix=CB_ISSUING_CREATE_PREFIX,
            back_callback=CB_CREATE_CANCEL,
        ),
    )


@router.callback_query(
    StateFilter(TariffCreateStates.issuing_mode),
    F.data.startswith(CB_ISSUING_CREATE_PREFIX),
)
async def create_step_issuing_mode(callback: CallbackQuery, state: FSMContext, plan_service: PlanService) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    mode = callback.data.removeprefix(CB_ISSUING_CREATE_PREFIX)
    try:
        issuing_mode = plan_service.parse_issuing_mode(mode)
    except PlanValidationError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await state.update_data(issuing_mode=issuing_mode)
    await state.set_state(TariffCreateStates.description)
    await callback.message.answer(
        "Введите <b>описание</b> тарифа (или «-» чтобы пропустить):",
    )
    await callback.answer()


@router.message(StateFilter(TariffCreateStates.description))
async def create_step_description(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    try:
        description = plan_service.parse_description(message.text or "")
    except PlanValidationError as exc:
        await message.answer(exc.message)
        return
    await state.update_data(description=description)
    await state.set_state(TariffCreateStates.confirm)
    data = await state.get_data()
    text = plan_service.format_create_confirmation(data)
    await message.answer(text, reply_markup=create_confirm_keyboard())


@router.callback_query(StateFilter(TariffCreateStates.confirm), F.data == CB_CREATE_CONFIRM)
async def create_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    data = await state.get_data()
    try:
        create_input = plan_service.build_create_input_from_state(data)
        plan = await plan_service.create_plan(create_input)
    except PlanValidationError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.TARIFF_CREATED,
        details={"plan_id": plan.id, "name": plan.name},
    )
    await state.clear()
    await callback.message.answer(f"✅ Тариф <b>{plan.name}</b> успешно создан.")
    await send_tariff_list(callback, plan_service)


@router.callback_query(F.data == CB_CREATE_CANCEL)
async def create_cancel(callback: CallbackQuery, state: FSMContext, plan_service: PlanService) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("❌ Создание тарифа отменено.")
    await send_tariff_list(callback, plan_service)


@router.message(Command("cancel"), StateFilter(TariffCreateStates))
async def create_cancel_command(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    await state.clear()
    await message.answer("❌ Создание тарифа отменено.")
    await send_tariff_list(message, plan_service)
