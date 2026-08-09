from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import (
    FreePlanNotEligibleError,
    PaymentRequestDuplicateError,
    PaymentRequestNotFoundError,
    VpnPanelValidationError,
)
from app.application.services.admin_log_service import AdminLogService
from app.application.services.free_plan_activation_service import FreePlanActivationService
from app.application.services.payment_request_service import PaymentRequestService
from app.application.services.plan_service import PlanService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.application.services.customer_vpn_service import CustomerVpnService
from app.application.services.promo_activation_service import PromoActivationService
from app.application.services.subscription_purchase_service import SubscriptionPurchaseService
from app.domain.enums import PaymentRequestType
from app.presentation.services.promo_checkout_helpers import get_pricing_from_state, show_promo_prompt
from app.config.settings import Settings
from app.domain.enums import AdminActionType
from app.presentation.services.customer_provisioning_delivery import deliver_provisioning_to_customer
from app.presentation.services.referral_notifications import send_referral_notifications
from app.presentation.services.payment_request_admin_notification import notify_admins_new_payment_request
from app.domain.enums import ReceiptFileType
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.utils.customer_ui import send_keygate_card
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE
from app.presentation.utils.telegram import edit_or_answer_text
from app.presentation.keyboards.purchase import (
    PURCHASE_CANCEL,
    PURCHASE_CHOICE_RENEW_PREFIX,
    PURCHASE_CHOICE_SEPARATE_PREFIX,
    PURCHASE_FREE_PREFIX,
    PURCHASE_PAID_PREFIX,
    PURCHASE_RENEW_ACCOUNT_PREFIX,
    PURCHASE_SEPARATE_PAID_PREFIX,
    purchase_checkout_keyboard,
    purchase_choice_keyboard,
    purchase_free_keyboard,
    purchase_renew_account_keyboard,
    purchase_separate_checkout_keyboard,
)
from app.presentation.keyboards.tariffs import PURCHASE_CALLBACK_PREFIX, plan_selection_keyboard
from app.presentation.states.purchase import PurchaseReceiptStates, PurchaseSubscriptionStates

router = Router(name="customer_purchase")


@router.message(menu_text_filter("menu.buy_vpn"))
async def handle_buy_vpn(message: Message, state: FSMContext, plan_service: PlanService, lang: str) -> None:
    await state.clear()
    plans = await plan_service.list_active_plans()
    if not plans:
        await message.answer(
            t(lang, "purchase.no_plans"),
            reply_markup=customer_main_keyboard(lang),
            parse_mode=CUSTOMER_PARSE_MODE,
        )
        return

    await send_keygate_card(
        message,
        caption=t(lang, "purchase.banner_caption"),
        reply_markup=plan_selection_keyboard(plans),
    )


@router.callback_query(F.data.startswith(PURCHASE_CALLBACK_PREFIX))
async def handle_plan_selected(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    subscription_purchase_service: SubscriptionPurchaseService,
    lang: str,
) -> None:
    await state.clear()
    if callback.data is None or callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    plan_id_str = callback.data.removeprefix(PURCHASE_CALLBACK_PREFIX)
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        await callback.answer(t(lang, "common.invalid_plan"), show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer(t(lang, "common.plan_unavailable"), show_alert=True)
        return

    if plan_service.is_free(plan):
        ready = await _ensure_primary_vpn_name_or_ask(
            callback,
            state,
            subscription_purchase_service,
            plan_id=plan.id,
            pending_action="free",
            lang=lang,
        )
        if not ready:
            return
        text = plan_service.format_free_plan_checkout(
            plan_details=plan_service.format_plan_details(plan),
        )
        keyboard = purchase_free_keyboard(plan.id)
        await edit_or_answer_text(callback.message, text, reply_markup=keyboard)
        await callback.answer()
        return

    if await subscription_purchase_service.user_has_active_vpn(callback.from_user.id):
        await edit_or_answer_text(
            callback.message,
            t(lang, "purchase.subscription_choice"),
            reply_markup=purchase_choice_keyboard(plan.id),
        )
        await callback.answer()
        return

    ready = await _ensure_primary_vpn_name_or_ask(
        callback,
        state,
        subscription_purchase_service,
        plan_id=plan.id,
        pending_action="checkout",
        lang=lang,
    )
    if not ready:
        return

    await _show_standard_checkout(callback.message, state, plan=plan, lang=lang)
    await callback.answer()


@router.message(StateFilter(PurchaseSubscriptionStates.waiting_vpn_base_name), F.text, ~F.text.startswith("/"))
async def handle_vpn_base_name_input(
    message: Message,
    state: FSMContext,
    plan_service: PlanService,
    subscription_purchase_service: SubscriptionPurchaseService,
    lang: str,
) -> None:
    if message.from_user is None or message.text is None:
        return

    data = await state.get_data()
    plan_id = data.get("plan_id")
    pending_action = data.get("pending_vpn_name_action")
    if not isinstance(plan_id, int) or pending_action not in {"checkout", "free", "separate"}:
        await state.clear()
        await message.answer(t(lang, "common.session_expired_purchase"), reply_markup=customer_main_keyboard(lang))
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await state.clear()
        await message.answer(t(lang, "common.plan_unavailable"), reply_markup=customer_main_keyboard(lang))
        return

    try:
        user = await subscription_purchase_service.get_user(message.from_user.id)
        account_name = await subscription_purchase_service.assign_primary_vpn_account_name(
            user,
            message.text,
        )
    except VpnPanelValidationError:
        await message.answer(
            t(lang, "purchase.vpn_name_invalid"),
            parse_mode=CUSTOMER_PARSE_MODE,
        )
        return
    except PaymentRequestNotFoundError as exc:
        await state.clear()
        await message.answer(exc.message, reply_markup=customer_main_keyboard(lang))
        return

    await state.update_data(pending_vpn_name_action=None)

    if pending_action == "separate":
        await state.set_state(PurchaseSubscriptionStates.waiting_label)
        await message.answer(
            f"✅ VPN: <code>{account_name}</code>\n\n{t(lang, 'purchase.separate_name')}",
            parse_mode=CUSTOMER_PARSE_MODE,
        )
        return

    await state.set_state(None)

    if pending_action == "free":
        text = plan_service.format_free_plan_checkout(
            plan_details=plan_service.format_plan_details(plan),
        )
        await message.answer(
            f"✅ VPN: <code>{account_name}</code>\n\n{text}",
            reply_markup=purchase_free_keyboard(plan.id),
            parse_mode=CUSTOMER_PARSE_MODE,
        )
        return

    await message.answer(
        f"✅ VPN: <code>{account_name}</code>",
        parse_mode=CUSTOMER_PARSE_MODE,
    )
    await _show_standard_checkout(message, state, plan=plan, lang=lang)


@router.callback_query(F.data.startswith(PURCHASE_CHOICE_RENEW_PREFIX))
async def handle_purchase_choice_renew(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    subscription_purchase_service: SubscriptionPurchaseService,
    customer_vpn_service: CustomerVpnService,
    admin_log_service: AdminLogService,
    lang: str,
) -> None:
    await state.clear()
    if callback.data is None or callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, PURCHASE_CHOICE_RENEW_PREFIX)
    if plan_id is None:
        await callback.answer(t(lang, "common.invalid_plan"), show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer(t(lang, "common.plan_unavailable"), show_alert=True)
        return

    accounts = await subscription_purchase_service.list_active_accounts(callback.from_user.id)
    if not accounts:
        await callback.answer(t(lang, "common.no_active_vpn"), show_alert=True)
        return

    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.SUBSCRIPTION_RENEWAL_SELECTED,
        details={"plan_id": plan_id, "account_count": len(accounts)},
    )

    if len(accounts) == 1:
        await _show_renewal_checkout(
            callback.message,
            state,
            plan=plan,
            vpn_account_id=accounts[0].id,
            lang=lang,
        )
        await callback.answer()
        return

    await edit_or_answer_text(
        callback.message,
        t(lang, "purchase.renew_which"),
        reply_markup=purchase_renew_account_keyboard(plan.id, accounts),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(PURCHASE_RENEW_ACCOUNT_PREFIX))
async def handle_purchase_renew_account(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    customer_vpn_service: CustomerVpnService,
    lang: str,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    parsed = _parse_plan_and_account(callback.data, PURCHASE_RENEW_ACCOUNT_PREFIX)
    if parsed is None:
        await callback.answer(t(lang, "common.invalid_request"), show_alert=True)
        return
    plan_id, account_id = parsed

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer(t(lang, "common.plan_unavailable"), show_alert=True)
        return

    await _show_renewal_checkout(
        callback.message,
        state,
        plan=plan,
        vpn_account_id=account_id,
        lang=lang,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(PURCHASE_CHOICE_SEPARATE_PREFIX))
async def handle_purchase_choice_separate(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    subscription_purchase_service: SubscriptionPurchaseService,
    admin_log_service: AdminLogService,
    lang: str,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, PURCHASE_CHOICE_SEPARATE_PREFIX)
    if plan_id is None:
        await callback.answer(t(lang, "common.invalid_plan"), show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer(t(lang, "common.plan_unavailable"), show_alert=True)
        return

    try:
        user = await subscription_purchase_service.get_user(callback.from_user.id)
        primary = await subscription_purchase_service.ensure_primary_vpn_account_name(user)
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    if primary is None:
        await state.update_data(plan_id=plan.id, pending_vpn_name_action="separate")
        await state.set_state(PurchaseSubscriptionStates.waiting_vpn_base_name)
        await callback.message.answer(
            t(lang, "purchase.need_vpn_name"),
            parse_mode=CUSTOMER_PARSE_MODE,
        )
        await callback.answer()
        return

    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.SEPARATE_SUBSCRIPTION_SELECTED,
        details={"plan_id": plan_id},
    )
    await state.update_data(plan_id=plan_id)
    await state.set_state(PurchaseSubscriptionStates.waiting_label)
    await callback.message.answer(t(lang, "purchase.separate_name"), parse_mode=CUSTOMER_PARSE_MODE)
    await callback.answer()


@router.message(StateFilter(PurchaseSubscriptionStates.waiting_label), F.text, ~F.text.startswith("/"))
async def handle_subscription_label(
    message: Message,
    state: FSMContext,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    subscription_purchase_service: SubscriptionPurchaseService,
    admin_log_service: AdminLogService,
    lang: str,
) -> None:
    if message.from_user is None or message.text is None:
        return

    data = await state.get_data()
    plan_id = data.get("plan_id")
    if not isinstance(plan_id, int):
        await state.clear()
        await message.answer(t(lang, "common.session_expired_purchase"), reply_markup=customer_main_keyboard(lang))
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await state.clear()
        await message.answer(t(lang, "common.plan_unavailable"), reply_markup=customer_main_keyboard(lang))
        return

    try:
        user = await subscription_purchase_service.get_user(message.from_user.id)
        vpn_account_name, display_name = await subscription_purchase_service.generate_unique_vpn_account_name(
            user,
            label=message.text.strip(),
        )
    except (VpnPanelValidationError, PaymentRequestNotFoundError) as exc:
        await message.answer(exc.message)
        return

    await admin_log_service.log(
        admin_telegram_id=message.from_user.id,
        action=AdminActionType.VPN_ACCOUNT_NAME_GENERATED,
        details={"plan_id": plan_id, "vpn_account_name": vpn_account_name},
    )

    await state.update_data(
        target_vpn_account_name=vpn_account_name,
        target_display_name=display_name,
    )
    await state.set_state(None)
    await show_promo_prompt(
        message,
        state,
        flow="separate",
        plan_id=plan.id,
        request_type=PaymentRequestType.PURCHASE.value,
        target_vpn_account_name=vpn_account_name,
        target_display_name=display_name,
        edit=False,
        lang=lang,
    )


@router.callback_query(F.data == PURCHASE_CANCEL)
async def handle_purchase_cancel(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    if callback.message is None:
        await callback.answer()
        return
    await edit_or_answer_text(callback.message, t(lang, "purchase.cancel"))
    await callback.message.answer(t(lang, "common.main_menu"), reply_markup=customer_main_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.startswith(PURCHASE_FREE_PREFIX))
async def handle_free_plan_activate(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    plan_service: PlanService,
    free_plan_activation_service: FreePlanActivationService,
    provisioning_notification_service: ProvisioningNotificationService,
    subscription_purchase_service: SubscriptionPurchaseService,
    admin_log_service: AdminLogService,
    settings: Settings,
    lang: str,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    plan_id_str = callback.data.removeprefix(PURCHASE_FREE_PREFIX)
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        await callback.answer(t(lang, "common.invalid_plan"), show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None or not plan_service.is_free(plan):
        await callback.answer(t(lang, "common.plan_unavailable"), show_alert=True)
        return

    ready = await _ensure_primary_vpn_name_or_ask(
        callback,
        state,
        subscription_purchase_service,
        plan_id=plan.id,
        pending_action="free",
        lang=lang,
    )
    if not ready:
        return

    await state.clear()

    try:
        outcome = await free_plan_activation_service.activate(
            callback.from_user.id,
            plan_id,
        )
    except FreePlanNotEligibleError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    log_admin_id = (
        settings.admin_telegram_ids[0]
        if settings.admin_telegram_ids
        else callback.from_user.id
    )
    if outcome.notify_customer and outcome.provisioning is not None:
        await deliver_provisioning_to_customer(
            bot,
            telegram_id=outcome.telegram_id,
            customer_message=outcome.customer_message,
            provisioning=outcome.provisioning,
            notification_service=provisioning_notification_service,
            admin_log_service=admin_log_service,
            admin_telegram_id=log_admin_id,
            payment_request_id=outcome.request_id,
        )
        await callback.message.answer(t(lang, "common.main_menu"), reply_markup=customer_main_keyboard(lang))
        await callback.answer(t(lang, "common.done"))
        return

    await callback.message.answer(
        outcome.customer_message,
        reply_markup=customer_main_keyboard(lang),
    )
    await callback.answer(outcome.customer_message, show_alert=True)


@router.callback_query(F.data.startswith(PURCHASE_PAID_PREFIX))
async def handle_purchase_paid(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    promo_activation_service: PromoActivationService,
    provisioning_notification_service: ProvisioningNotificationService,
    lang: str,
) -> None:
    await _start_receipt_flow(
        callback,
        state,
        bot,
        plan_service=plan_service,
        payment_request_service=payment_request_service,
        promo_activation_service=promo_activation_service,
        provisioning_notification_service=provisioning_notification_service,
        lang=lang,
        prefix=PURCHASE_PAID_PREFIX,
        purchase_mode="purchase",
    )


@router.callback_query(F.data.startswith(PURCHASE_SEPARATE_PAID_PREFIX))
async def handle_separate_purchase_paid(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    promo_activation_service: PromoActivationService,
    provisioning_notification_service: ProvisioningNotificationService,
    lang: str,
) -> None:
    await _start_receipt_flow(
        callback,
        state,
        bot,
        plan_service=plan_service,
        payment_request_service=payment_request_service,
        promo_activation_service=promo_activation_service,
        provisioning_notification_service=provisioning_notification_service,
        lang=lang,
        prefix=PURCHASE_SEPARATE_PAID_PREFIX,
        purchase_mode="separate",
    )


@router.message(StateFilter(PurchaseReceiptStates.waiting_receipt), F.photo)
async def handle_receipt_photo(
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
    file_id = message.photo[-1].file_id
    await _submit_receipt(
        message,
        state,
        bot,
        payment_request_service,
        settings,
        admin_log_service,
        receipt_file_id=file_id,
        receipt_file_type=ReceiptFileType.PHOTO.value,
        user_comment=None,
        receipt_message_id=message.message_id,
        lang=lang,
    )


@router.message(StateFilter(PurchaseReceiptStates.waiting_receipt), F.document)
async def handle_receipt_document(
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
    await _submit_receipt(
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


@router.message(StateFilter(PurchaseReceiptStates.waiting_receipt), F.text, ~F.text.startswith("/"))
async def handle_receipt_text(
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
        await message.answer(t(lang, "purchase.invalid_receipt"))
        return

    await _submit_receipt(
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


@router.message(StateFilter(PurchaseReceiptStates.waiting_receipt))
async def handle_receipt_invalid(message: Message, lang: str) -> None:
    await message.answer(t(lang, "purchase.invalid_receipt"))


async def _show_standard_checkout(
    message: Message,
    state: FSMContext,
    *,
    plan,
    lang: str,
) -> None:
    await show_promo_prompt(
        message,
        state,
        flow="purchase",
        plan_id=plan.id,
        request_type=PaymentRequestType.PURCHASE.value,
        lang=lang,
    )


async def _show_renewal_checkout(
    message: Message,
    state: FSMContext,
    *,
    plan,
    vpn_account_id: int,
    lang: str,
) -> None:
    await show_promo_prompt(
        message,
        state,
        flow="purchase_renew",
        plan_id=plan.id,
        request_type=PaymentRequestType.RENEWAL.value,
        vpn_account_id=vpn_account_id,
        lang=lang,
    )


async def _start_receipt_flow(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    *,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    promo_activation_service: PromoActivationService,
    provisioning_notification_service: ProvisioningNotificationService,
    lang: str,
    prefix: str,
    purchase_mode: str,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, prefix)
    if plan_id is None:
        await callback.answer(t(lang, "common.invalid_plan"), show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer(t(lang, "common.plan_unavailable"), show_alert=True)
        return
    if plan_service.is_free(plan):
        await callback.answer(t(lang, "common.free_use_button"), show_alert=True)
        return

    if await payment_request_service.has_pending_purchase(callback.from_user.id):
        await callback.answer(t(lang, "common.pending_purchase"), show_alert=True)
        return

    data = await state.get_data()
    pricing = await get_pricing_from_state(data)
    if pricing["final_amount"] is not None and pricing["final_amount"] == 0 and pricing["promo_code_id"]:
        try:
            target_name = data.get("target_vpn_account_name") if purchase_mode == "separate" else None
            target_display = data.get("target_display_name") if purchase_mode == "separate" else None
            outcome = await promo_activation_service.activate(
                telegram_id=callback.from_user.id,
                plan_id=plan_id,
                request_type=PaymentRequestType.PURCHASE.value,
                promo_code_id=int(pricing["promo_code_id"]),
                original_amount=pricing["original_amount"] or plan.price,
                discount_amount=pricing["discount_amount"],
                final_amount=pricing["final_amount"],
                extra_days_from_promo=pricing["extra_days_from_promo"],
                target_vpn_account_name=target_name if isinstance(target_name, str) else None,
                target_display_name=target_display if isinstance(target_display, str) else None,
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
        if callback.message is not None:
            await callback.message.answer(outcome.customer_message, reply_markup=customer_main_keyboard(lang))
        await callback.answer(t(lang, "purchase.promo_activated"))
        return

    if purchase_mode == "separate":
        target_name = data.get("target_vpn_account_name")
        target_display = data.get("target_display_name")
        if not isinstance(target_name, str) or not isinstance(target_display, str):
            await callback.answer(t(lang, "common.enter_subscription_name"), show_alert=True)
            return
        await state.update_data(
            plan_id=plan_id,
            purchase_mode=purchase_mode,
            target_vpn_account_name=target_name,
            target_display_name=target_display,
        )
    else:
        await state.update_data(plan_id=plan_id, purchase_mode="purchase", **{k: v for k, v in pricing.items() if v is not None})

    await state.set_state(PurchaseReceiptStates.waiting_receipt)
    await callback.message.answer(t(lang, "purchase.receipt_prompt"))
    await callback.answer()


async def _submit_receipt(
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
    if not isinstance(plan_id, int):
        await state.clear()
        await message.answer(t(lang, "common.session_expired_purchase"), reply_markup=customer_main_keyboard(lang))
        return

    purchase_mode = data.get("purchase_mode", "purchase")
    pricing = await get_pricing_from_state(data)
    try:
        if purchase_mode == "separate":
            target_name = data.get("target_vpn_account_name")
            target_display = data.get("target_display_name")
            if not isinstance(target_name, str) or not isinstance(target_display, str):
                raise PaymentRequestNotFoundError(t(lang, "purchase.subscription_data_missing"))
            request = await payment_request_service.create_purchase_request(
                telegram_id=message.from_user.id,
                plan_id=plan_id,
                receipt_file_id=receipt_file_id,
                receipt_file_type=receipt_file_type,
                user_comment=user_comment,
                receipt_message_id=receipt_message_id,
                target_vpn_account_name=target_name,
                target_display_name=target_display,
                promo_code_id=pricing["promo_code_id"],
                original_amount=pricing["original_amount"],
                discount_amount=pricing["discount_amount"],
                final_amount=pricing["final_amount"],
                extra_days_from_promo=pricing["extra_days_from_promo"],
            )
        else:
            request = await payment_request_service.create_purchase_request(
                telegram_id=message.from_user.id,
                plan_id=plan_id,
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
    await message.answer(t(lang, "purchase.success"), reply_markup=customer_main_keyboard(lang))
    await notify_admins_new_payment_request(
        bot,
        settings=settings,
        payment_request_service=payment_request_service,
        admin_log_service=admin_log_service,
        request=request,
    )


def _parse_plan_id(data: str, prefix: str) -> int | None:
    suffix = data.removeprefix(prefix)
    try:
        return int(suffix)
    except ValueError:
        return None


def _parse_plan_and_account(data: str, prefix: str) -> tuple[int, int] | None:
    suffix = data.removeprefix(prefix)
    parts = suffix.split(":", maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


async def _ensure_primary_vpn_name_or_ask(
    callback: CallbackQuery,
    state: FSMContext,
    subscription_purchase_service: SubscriptionPurchaseService,
    *,
    plan_id: int,
    pending_action: str,
    lang: str,
) -> bool:
    """
    Ensure primary VPN account name exists.

    Returns True when checkout/activation can continue.
    Returns False when the customer was asked to enter a base name.
    """
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return False

    try:
        user = await subscription_purchase_service.get_user(callback.from_user.id)
        primary = await subscription_purchase_service.ensure_primary_vpn_account_name(user)
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return False

    if primary is not None:
        return True

    await state.update_data(plan_id=plan_id, pending_vpn_name_action=pending_action)
    await state.set_state(PurchaseSubscriptionStates.waiting_vpn_base_name)
    await callback.message.answer(
        t(lang, "purchase.need_vpn_name"),
        parse_mode=CUSTOMER_PARSE_MODE,
    )
    await callback.answer()
    return False
