from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import PromoCodeError
from app.application.services.customer_vpn_service import CustomerVpnService
from app.application.services.payment_request_service import PaymentRequestService
from app.application.services.plan_service import PlanService
from app.application.services.promo_code_service import PromoCodeService
from app.domain.enums import PaymentRequestType
from app.infrastructure.db.uow import UnitOfWork
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.promo_checkout import (
    PROMO_CANCEL,
    PROMO_ENTER,
    PROMO_SKIP,
    promo_prompt_keyboard,
)
from app.presentation.services.promo_checkout_helpers import (
    apply_promo_to_state,
    resolve_request_type_from_state,
    show_checkout_from_state,
)
from app.presentation.states.promo_checkout import PromoCheckoutStates

router = Router(name="customer_promo_checkout")

PROMO_PROMPT_TEXT = "У вас есть промокод?"
CODE_PROMPT = "🎁 Введите промокод:\n<i>/cancel для отмены</i>"


@router.callback_query(F.data == PROMO_ENTER)
async def handle_promo_enter(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromoCheckoutStates.waiting_code)
    if callback.message is not None:
        await callback.message.answer(CODE_PROMPT)
    await callback.answer()


@router.callback_query(F.data == PROMO_SKIP)
async def handle_promo_skip(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    promo_code_service: PromoCodeService,
    customer_vpn_service: CustomerVpnService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    data = await state.get_data()
    plan_id = data.get("plan_id")
    if isinstance(plan_id, int):
        plan = await plan_service.get_active_plan(plan_id)
        if plan is not None:
            await state.update_data(
                original_amount=str(plan.price),
                final_amount=str(plan.price),
                discount_amount="0",
                promo_code_id=None,
                promo_code=None,
                extra_days_from_promo=0,
            )
    await show_checkout_from_state(
        callback.message,
        state,
        plan_service=plan_service,
        payment_request_service=payment_request_service,
        promo_code_service=promo_code_service,
        customer_vpn_service=customer_vpn_service,
    )
    await callback.answer()


@router.callback_query(F.data == PROMO_CANCEL)
async def handle_promo_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text("❌ Оформление отменено.")
        await callback.message.answer("Выберите действие в меню.", reply_markup=customer_main_keyboard())
    await callback.answer()


@router.message(StateFilter(PromoCheckoutStates.waiting_code), F.text, ~F.text.startswith("/"))
async def handle_promo_code_input(
    message: Message,
    state: FSMContext,
    uow: UnitOfWork,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    promo_code_service: PromoCodeService,
    customer_vpn_service: CustomerVpnService,
) -> None:
    if message.from_user is None or not message.text:
        return
    data = await state.get_data()
    plan_id = data.get("plan_id")
    if not isinstance(plan_id, int):
        await state.clear()
        await message.answer("Сессия истекла.", reply_markup=customer_main_keyboard())
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await message.answer("Тариф недоступен.", reply_markup=customer_main_keyboard())
        return

    user = await uow.users.get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("Отправьте /start.", reply_markup=customer_main_keyboard())
        return

    request_type = resolve_request_type_from_state(data)
    try:
        result = await promo_code_service.validate_and_apply(
            user_id=user.id,
            code=message.text,
            plan_id=plan.id,
            request_type=request_type,
            original_amount=plan.price,
        )
    except PromoCodeError as exc:
        await message.answer(exc.message)
        return

    await apply_promo_to_state(state, result)
    await message.answer(promo_code_service.format_applied_message(result))
    await show_checkout_from_state(
        message,
        state,
        plan_service=plan_service,
        payment_request_service=payment_request_service,
        promo_code_service=promo_code_service,
        customer_vpn_service=customer_vpn_service,
        edit=False,
    )
