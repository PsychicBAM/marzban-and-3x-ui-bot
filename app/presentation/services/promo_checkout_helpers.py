from __future__ import annotations

from decimal import Decimal

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.services.customer_vpn_service import CustomerVpnService
from app.application.services.payment_request_service import PaymentRequestService
from app.application.services.plan_service import PlanService
from app.application.services.promo_code_service import PromoCodeService
from app.domain.enums import PaymentRequestType
from app.presentation.keyboards.purchase import (
    purchase_checkout_keyboard,
    purchase_separate_checkout_keyboard,
)
from app.presentation.keyboards.promo_checkout import promo_prompt_keyboard
from app.presentation.keyboards.renewal import renewal_checkout_keyboard
from app.presentation.i18n import t


async def show_promo_prompt(
    message: Message,
    state: FSMContext,
    *,
    flow: str,
    plan_id: int,
    request_type: str,
    vpn_account_id: int | None = None,
    target_vpn_account_name: str | None = None,
    target_display_name: str | None = None,
    edit: bool = True,
    lang: str | None = None,
) -> None:
    await save_checkout_context(
        state,
        flow=flow,
        plan_id=plan_id,
        request_type=request_type,
        vpn_account_id=vpn_account_id,
        target_vpn_account_name=target_vpn_account_name,
        target_display_name=target_display_name,
    )
    text = t(lang, "promo.prompt_title", text=t(lang, "promo.prompt"))
    if edit:
        await message.edit_text(text, reply_markup=promo_prompt_keyboard())
    else:
        await message.answer(text, reply_markup=promo_prompt_keyboard())


def promo_prompt_text(lang: str | None) -> str:
    return t(lang, "promo.prompt")


async def save_checkout_context(
    state: FSMContext,
    *,
    flow: str,
    plan_id: int,
    request_type: str,
    vpn_account_id: int | None = None,
    target_vpn_account_name: str | None = None,
    target_display_name: str | None = None,
) -> None:
    await state.update_data(
        checkout_flow=flow,
        plan_id=plan_id,
        request_type=request_type,
        vpn_account_id=vpn_account_id,
        target_vpn_account_name=target_vpn_account_name,
        target_display_name=target_display_name,
        promo_code_id=None,
        promo_code=None,
        original_amount=None,
        discount_amount=Decimal("0"),
        final_amount=None,
        extra_days_from_promo=0,
    )


async def apply_promo_to_state(state: FSMContext, result) -> None:
    await state.update_data(
        promo_code_id=result.promo_code_id,
        promo_code=result.code,
        original_amount=str(result.original_amount),
        discount_amount=str(result.discount_amount),
        final_amount=str(result.final_amount),
        extra_days_from_promo=result.extra_days,
    )


async def get_pricing_from_state(data: dict) -> dict:
    final_raw = data.get("final_amount")
    original_raw = data.get("original_amount")
    discount_raw = data.get("discount_amount", "0")
    return {
        "promo_code_id": data.get("promo_code_id"),
        "promo_code": data.get("promo_code"),
        "original_amount": Decimal(original_raw) if original_raw else None,
        "discount_amount": Decimal(str(discount_raw)),
        "final_amount": Decimal(final_raw) if final_raw else None,
        "extra_days_from_promo": int(data.get("extra_days_from_promo") or 0),
    }


def promo_summary_from_state(data: dict, promo_service: PromoCodeService, *, lang: str | None = None) -> str | None:
    if not data.get("promo_code"):
        return None
    from app.application.dto.promo_code import PromoApplyResult

    result = PromoApplyResult(
        promo_code_id=int(data["promo_code_id"]),
        code=str(data["promo_code"]),
        discount_type="",
        original_amount=Decimal(str(data["original_amount"])),
        discount_amount=Decimal(str(data["discount_amount"])),
        final_amount=Decimal(str(data["final_amount"])),
        extra_days=int(data.get("extra_days_from_promo") or 0),
    )
    return promo_service.format_applied_message(result, lang=lang)


async def show_checkout_from_state(
    message: Message,
    state: FSMContext,
    *,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    promo_code_service: PromoCodeService,
    customer_vpn_service: CustomerVpnService | None = None,
    edit: bool = True,
    lang: str | None = None,
) -> None:
    data = await state.get_data()
    plan_id = data.get("plan_id")
    if not isinstance(plan_id, int):
        return
    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        return

    if data.get("final_amount") is None:
        await state.update_data(
            original_amount=str(plan.price),
            final_amount=str(plan.price),
            discount_amount="0",
        )
        data = await state.get_data()

    promo_summary = promo_summary_from_state(data, promo_code_service, lang=lang)
    payment_details = await payment_request_service.get_payment_details_text()
    has_details = await payment_request_service.has_payment_details()
    flow = data.get("checkout_flow", "purchase")

    if flow == "renewal":
        vpn_account_id = data.get("vpn_account_id")
        account = None
        if customer_vpn_service and message.from_user and isinstance(vpn_account_id, int):
            account = await customer_vpn_service.get_account_for_user(
                message.from_user.id,
                vpn_account_id,
            )
        extra_days = int(data.get("extra_days_from_promo") or 0)
        expected, current = await payment_request_service.preview_renewal_expiry(
            plan_duration_days=plan.duration_days,
            vpn_account=account,
            extra_days=extra_days,
        )
        text = payment_request_service.format_renewal_checkout(
            plan_details=plan_service.format_plan_details(plan),
            payment_details=payment_details,
            has_payment_details=has_details,
            current_expiry=current,
            expected_expiry=expected,
            has_account=account is not None,
            promo_summary=promo_summary,
        )
        vid = vpn_account_id if isinstance(vpn_account_id, int) else 0
        await _send_text(message, text, renewal_checkout_keyboard(plan.id, vpn_account_id=vid), edit=edit)
        return

    if flow == "separate":
        target_display = data.get("target_display_name", "")
        target_name = data.get("target_vpn_account_name", "")
        text = payment_request_service.format_separate_checkout(
            plan_details=plan_service.format_plan_details(plan),
            payment_details=payment_details,
            has_payment_details=has_details,
            display_name=str(target_display),
            vpn_account_name=str(target_name),
            promo_summary=promo_summary,
        )
        await _send_text(message, text, purchase_separate_checkout_keyboard(plan.id), edit=edit)
        return

    if flow == "purchase_renew":
        account = None
        vpn_account_id = data.get("vpn_account_id")
        if customer_vpn_service and message.from_user and isinstance(vpn_account_id, int):
            account = await customer_vpn_service.get_account_for_user(
                message.from_user.id,
                vpn_account_id,
            )
        extra_days = int(data.get("extra_days_from_promo") or 0)
        expected, current = await payment_request_service.preview_renewal_expiry(
            plan_duration_days=plan.duration_days,
            vpn_account=account,
            extra_days=extra_days,
        )
        text = payment_request_service.format_renewal_checkout(
            plan_details=plan_service.format_plan_details(plan),
            payment_details=payment_details,
            has_payment_details=has_details,
            current_expiry=current,
            expected_expiry=expected,
            has_account=account is not None,
            promo_summary=promo_summary,
        )
        vid = vpn_account_id if isinstance(vpn_account_id, int) else 0
        await _send_text(message, text, renewal_checkout_keyboard(plan.id, vpn_account_id=vid), edit=edit)
        return

    text = payment_request_service.format_purchase_checkout(
        plan_details=plan_service.format_plan_details(plan),
        payment_details=payment_details,
        has_payment_details=has_details,
        promo_summary=promo_summary,
    )
    await _send_text(message, text, purchase_checkout_keyboard(plan.id), edit=edit)


async def _send_text(message: Message, text: str, keyboard, *, edit: bool) -> None:
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


def resolve_request_type_from_state(data: dict) -> str:
    flow = data.get("checkout_flow", "purchase")
    if flow in {"renewal", "purchase_renew"}:
        return PaymentRequestType.RENEWAL.value
    return PaymentRequestType.PURCHASE.value
