from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import PaymentRequestDuplicateError, PaymentRequestNotFoundError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.customer_vpn_service import CustomerVpnService
from app.application.services.promo_activation_service import PromoActivationService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.application.services.payment_request_service import PaymentRequestService
from app.application.services.plan_service import PlanService
from app.config.settings import Settings
from app.domain.enums import PaymentRequestType, ReceiptFileType
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.renewal import (
    RENEW_CANCEL,
    RENEW_PAID_PREFIX,
    RENEW_SELECT_PREFIX,
    renewal_plan_keyboard,
)
from app.presentation.services.customer_provisioning_delivery import deliver_provisioning_to_customer
from app.presentation.services.payment_request_admin_notification import notify_admins_new_payment_request
from app.presentation.services.promo_checkout_helpers import get_pricing_from_state, show_promo_prompt
from app.presentation.services.referral_notifications import send_referral_notifications
from app.presentation.states.renewal import RenewReceiptStates

router = Router(name="customer_renewal")


@router.message(menu_text_filter("menu.renew_vpn"))
async def handle_renew_vpn_menu(
    message: Message,
    state: FSMContext,
    plan_service: PlanService,
    customer_vpn_service: CustomerVpnService,
    lang: str,
) -> None:
    await state.clear()
    account = None
    if message.from_user is not None:
        account = await customer_vpn_service.get_primary_account(message.from_user.id)
    await _send_renewal_plan_list(message, plan_service, vpn_account=account, lang=lang)


@router.callback_query(F.data.startswith(RENEW_SELECT_PREFIX))
async def handle_renew_plan_selected(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    lang: str,
) -> None:
    await state.clear()
    if callback.data is None or callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    parsed = _parse_plan_and_account(callback.data, RENEW_SELECT_PREFIX)
    if parsed is None:
        await callback.answer(t(lang, "common.invalid_plan"), show_alert=True)
        return
    plan_id, vpn_account_id = parsed

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer(t(lang, "common.plan_unavailable"), show_alert=True)
        return

    await show_promo_prompt(
        callback.message,
        state,
        flow="renewal",
        plan_id=plan.id,
        request_type=PaymentRequestType.RENEWAL.value,
        vpn_account_id=vpn_account_id,
        lang=lang,
    )
    await callback.answer()


@router.callback_query(F.data == RENEW_CANCEL)
async def handle_renew_cancel(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text(t(lang, "renewal.cancel"))
    await callback.message.answer(t(lang, "common.main_menu"), reply_markup=customer_main_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.startswith(RENEW_PAID_PREFIX))
async def handle_renew_paid(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    promo_activation_service: PromoActivationService,
    provisioning_notification_service: ProvisioningNotificationService,
    lang: str,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    parsed = _parse_plan_and_account(callback.data, RENEW_PAID_PREFIX)
    if parsed is None:
        await callback.answer(t(lang, "common.invalid_plan"), show_alert=True)
        return
    plan_id, vpn_account_id = parsed

    if await payment_request_service.has_pending_renewal(callback.from_user.id):
        await callback.answer(t(lang, "common.pending_renewal"), show_alert=True)
        return

    data = await state.get_data()
    await state.update_data(plan_id=plan_id, vpn_account_id=vpn_account_id or None)
    pricing = await get_pricing_from_state({**data, "plan_id": plan_id, "vpn_account_id": vpn_account_id})
    plan = await plan_service.get_active_plan(plan_id)
    if (
        plan is not None
        and pricing["final_amount"] is not None
        and pricing["final_amount"] == 0
        and pricing["promo_code_id"]
    ):
        try:
            outcome = await promo_activation_service.activate(
                telegram_id=callback.from_user.id,
                plan_id=plan_id,
                request_type=PaymentRequestType.RENEWAL.value,
                promo_code_id=int(pricing["promo_code_id"]),
                original_amount=pricing["original_amount"] or plan.price,
                discount_amount=pricing["discount_amount"],
                final_amount=pricing["final_amount"],
                extra_days_from_promo=pricing["extra_days_from_promo"],
                vpn_account_id=vpn_account_id,
            )
        except PaymentRequestNotFoundError as exc:
            await callback.answer(exc.message, show_alert=True)
            return
        await state.clear()
        if outcome.notify_customer and outcome.provisioning is not None:
            await deliver_provisioning_to_customer(
                bot,
                telegram_id=outcome.telegram_id,
                provisioning=outcome.provisioning,
                notification_service=provisioning_notification_service,
            )
        if outcome.referral_notifications:
            await send_referral_notifications(bot, outcome.referral_notifications)
        await callback.message.answer(outcome.customer_message, reply_markup=customer_main_keyboard(lang))
        await callback.answer(t(lang, "renewal.promo_activated"))
        return

    await state.set_state(RenewReceiptStates.waiting_receipt)
    await callback.message.answer(t(lang, "renewal.receipt_prompt"))
    await callback.answer()


@router.message(StateFilter(RenewReceiptStates.waiting_receipt), F.photo)
async def handle_renew_receipt_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    payment_request_service: PaymentRequestService,
    settings: Settings,
    admin_log_service: AdminLogService,
    lang: str,
) -> None:
    if message.from_user is None or not message.photo:
        return
    await _submit_renew_receipt(
        message,
        state,
        bot,
        payment_request_service,
        settings,
        admin_log_service,
        receipt_file_id=message.photo[-1].file_id,
        receipt_file_type=ReceiptFileType.PHOTO.value,
        user_comment=None,
        receipt_message_id=message.message_id,
        lang=lang,
    )


@router.message(StateFilter(RenewReceiptStates.waiting_receipt), F.document)
async def handle_renew_receipt_document(
    message: Message,
    state: FSMContext,
    bot: Bot,
    payment_request_service: PaymentRequestService,
    settings: Settings,
    admin_log_service: AdminLogService,
    lang: str,
) -> None:
    if message.from_user is None or message.document is None:
        return
    await _submit_renew_receipt(
        message,
        state,
        bot,
        payment_request_service,
        settings,
        admin_log_service,
        receipt_file_id=message.document.file_id,
        receipt_file_type=ReceiptFileType.DOCUMENT.value,
        user_comment=message.caption,
        receipt_message_id=message.message_id,
        lang=lang,
    )


@router.message(StateFilter(RenewReceiptStates.waiting_receipt), F.text, ~F.text.startswith("/"))
async def handle_renew_receipt_text(
    message: Message,
    state: FSMContext,
    bot: Bot,
    payment_request_service: PaymentRequestService,
    settings: Settings,
    admin_log_service: AdminLogService,
    lang: str,
) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer(t(lang, "renewal.invalid_receipt"))
        return
    await _submit_renew_receipt(
        message,
        state,
        bot,
        payment_request_service,
        settings,
        admin_log_service,
        receipt_file_id=None,
        receipt_file_type=ReceiptFileType.TEXT.value,
        user_comment=text,
        receipt_message_id=message.message_id,
        lang=lang,
    )


@router.message(StateFilter(RenewReceiptStates.waiting_receipt))
async def handle_renew_receipt_invalid(message: Message, lang: str) -> None:
    await message.answer(t(lang, "renewal.invalid_receipt"))


async def start_renewal_flow(
    callback: CallbackQuery,
    *,
    vpn_account_id: int,
    plan_service: PlanService,
    customer_vpn_service: CustomerVpnService,
    lang: str,
) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    plans = await plan_service.list_active_plans()
    if not plans:
        await callback.message.answer(t(lang, "renewal.no_plans"), reply_markup=customer_main_keyboard(lang))
        await callback.answer()
        return

    account = await customer_vpn_service.get_account_for_user(
        callback.from_user.id,
        vpn_account_id,
    )
    resolved_id = account.id if account is not None else vpn_account_id
    await callback.message.answer(
        t(lang, "renewal.choose_plan"),
        reply_markup=renewal_plan_keyboard(plans, vpn_account_id=resolved_id),
    )
    await callback.answer()


async def _send_renewal_plan_list(
    message: Message,
    plan_service: PlanService,
    *,
    vpn_account: VpnAccount | None,
    lang: str,
) -> None:
    plans = await plan_service.list_active_plans()
    if not plans:
        await message.answer(t(lang, "renewal.no_plans"), reply_markup=customer_main_keyboard(lang))
        return

    account_id = vpn_account.id if vpn_account is not None else None
    await message.answer(
        t(lang, "renewal.choose_plan"),
        reply_markup=renewal_plan_keyboard(plans, vpn_account_id=account_id),
    )


async def _submit_renew_receipt(
    message: Message,
    state: FSMContext,
    bot: Bot,
    payment_request_service: PaymentRequestService,
    settings: Settings,
    admin_log_service: AdminLogService,
    *,
    receipt_file_id: str | None,
    receipt_file_type: str,
    user_comment: str | None,
    receipt_message_id: int | None,
    lang: str,
) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    plan_id = data.get("plan_id")
    vpn_account_id = data.get("vpn_account_id")
    if not isinstance(plan_id, int):
        await state.clear()
        await message.answer(t(lang, "common.session_expired_renewal"), reply_markup=customer_main_keyboard(lang))
        return
    resolved_account_id = vpn_account_id if isinstance(vpn_account_id, int) else None

    pricing = await get_pricing_from_state(data)
    try:
        request = await payment_request_service.create_renewal_request(
            telegram_id=message.from_user.id,
            plan_id=plan_id,
            vpn_account_id=resolved_account_id,
            receipt_file_id=receipt_file_id,
            receipt_file_type=receipt_file_type,
            user_comment=user_comment,
            receipt_message_id=receipt_message_id,
            promo_code_id=pricing["promo_code_id"],
            original_amount=pricing["original_amount"],
            discount_amount=pricing["discount_amount"],
            final_amount=pricing["final_amount"],
            extra_days_from_promo=pricing["extra_days_from_promo"],
        )
    except PaymentRequestDuplicateError as exc:
        await state.clear()
        await message.answer(exc.message, reply_markup=customer_main_keyboard(lang))
        return
    except PaymentRequestNotFoundError as exc:
        await state.clear()
        await message.answer(exc.message, reply_markup=customer_main_keyboard(lang))
        return

    await state.clear()
    await message.answer(t(lang, "renewal.success"), reply_markup=customer_main_keyboard(lang))
    await notify_admins_new_payment_request(
        bot,
        settings=settings,
        payment_request_service=payment_request_service,
        admin_log_service=admin_log_service,
        request=request,
    )


def _parse_plan_and_account(data: str, prefix: str) -> tuple[int, int | None] | None:
    suffix = data.removeprefix(prefix)
    parts = suffix.split(":", maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        plan_id = int(parts[0])
        account_token = int(parts[1])
    except ValueError:
        return None
    vpn_account_id = account_token if account_token > 0 else None
    return plan_id, vpn_account_id
