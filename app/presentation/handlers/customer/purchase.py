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
from app.presentation.services.payment_request_admin_notification import notify_admins_new_payment_request
from app.domain.enums import ReceiptFileType
from app.presentation.keyboards.customer import customer_main_keyboard
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

NO_PLANS_TEXT = "😔 Сейчас нет доступных тарифов. Попробуйте позже или обратитесь в поддержку."
INVALID_RECEIPT_TEXT = (
    "Пожалуйста, отправьте <b>фото</b> или <b>документ</b> с чеком об оплате.\n"
    "Если не можете прикрепить файл — отправьте текстовый комментарий."
)
RECEIPT_PROMPT = (
    "📎 Отправьте <b>скриншот или фото чека</b> об оплате.\n"
    "Можно также отправить документ или текстовый комментарий.\n\n"
    "<i>Для отмены отправьте /cancel</i>"
)
SUCCESS_TEXT = "✅ Заявка отправлена администратору. После проверки оплаты бот выдаст VPN."
SUBSCRIPTION_CHOICE_TEXT = (
    "У вас уже есть активный VPN. Что вы хотите сделать?"
)
LABEL_PROMPT = (
    "✏️ Введите название для новой подписки <b>латиницей</b>.\n\n"
    "Примеры: <code>grandma</code> (для бабушки), <code>phone</code>, <code>work</code>\n"
    "Допустимы буквы a-z, цифры, _ и -\n\n"
    "<i>Для отмены отправьте /cancel</i>"
)


@router.message(F.text == "🛒 Купить VPN")
async def handle_buy_vpn(message: Message, state: FSMContext, plan_service: PlanService) -> None:
    await state.clear()
    plans = await plan_service.list_active_plans()
    if not plans:
        await message.answer(NO_PLANS_TEXT, reply_markup=customer_main_keyboard())
        return

    await message.answer(
        "🛒 <b>Выберите тариф:</b>",
        reply_markup=plan_selection_keyboard(plans),
    )


@router.callback_query(F.data.startswith(PURCHASE_CALLBACK_PREFIX))
async def handle_plan_selected(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    subscription_purchase_service: SubscriptionPurchaseService,
) -> None:
    await state.clear()
    if callback.data is None or callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    plan_id_str = callback.data.removeprefix(PURCHASE_CALLBACK_PREFIX)
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer("Тариф недоступен.", show_alert=True)
        return

    if plan_service.is_free(plan):
        text = plan_service.format_free_plan_checkout(
            plan_details=plan_service.format_plan_details(plan),
        )
        keyboard = purchase_free_keyboard(plan.id)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        return

    if await subscription_purchase_service.user_has_active_vpn(callback.from_user.id):
        await callback.message.edit_text(
            SUBSCRIPTION_CHOICE_TEXT,
            reply_markup=purchase_choice_keyboard(plan.id),
        )
        await callback.answer()
        return

    await _show_standard_checkout(callback.message, state, plan=plan)
    await callback.answer()


@router.callback_query(F.data.startswith(PURCHASE_CHOICE_RENEW_PREFIX))
async def handle_purchase_choice_renew(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    subscription_purchase_service: SubscriptionPurchaseService,
    customer_vpn_service: CustomerVpnService,
    admin_log_service: AdminLogService,
) -> None:
    await state.clear()
    if callback.data is None or callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, PURCHASE_CHOICE_RENEW_PREFIX)
    if plan_id is None:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer("Тариф недоступен.", show_alert=True)
        return

    accounts = await subscription_purchase_service.list_active_accounts(callback.from_user.id)
    if not accounts:
        await callback.answer("Активный VPN не найден.", show_alert=True)
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
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🔄 <b>Какую подписку продлить?</b>",
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
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    parsed = _parse_plan_and_account(callback.data, PURCHASE_RENEW_ACCOUNT_PREFIX)
    if parsed is None:
        await callback.answer("Некорректный запрос.", show_alert=True)
        return
    plan_id, account_id = parsed

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer("Тариф недоступен.", show_alert=True)
        return

    await _show_renewal_checkout(
        callback.message,
        state,
        plan=plan,
        vpn_account_id=account_id,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(PURCHASE_CHOICE_SEPARATE_PREFIX))
async def handle_purchase_choice_separate(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, PURCHASE_CHOICE_SEPARATE_PREFIX)
    if plan_id is None:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer("Тариф недоступен.", show_alert=True)
        return

    await admin_log_service.log(
        admin_telegram_id=callback.from_user.id,
        action=AdminActionType.SEPARATE_SUBSCRIPTION_SELECTED,
        details={"plan_id": plan_id},
    )
    await state.update_data(plan_id=plan_id)
    await state.set_state(PurchaseSubscriptionStates.waiting_label)
    await callback.message.answer(LABEL_PROMPT)
    await callback.answer()


@router.message(StateFilter(PurchaseSubscriptionStates.waiting_label), F.text, ~F.text.startswith("/"))
async def handle_subscription_label(
    message: Message,
    state: FSMContext,
    plan_service: PlanService,
    payment_request_service: PaymentRequestService,
    subscription_purchase_service: SubscriptionPurchaseService,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None or message.text is None:
        return

    data = await state.get_data()
    plan_id = data.get("plan_id")
    if not isinstance(plan_id, int):
        await state.clear()
        await message.answer("Сессия истекла. Начните покупку заново.", reply_markup=customer_main_keyboard())
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await state.clear()
        await message.answer("Тариф недоступен.", reply_markup=customer_main_keyboard())
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
    )


@router.callback_query(F.data == PURCHASE_CANCEL)
async def handle_purchase_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text("❌ Покупка отменена.")
    await callback.message.answer("Выберите действие в меню.", reply_markup=customer_main_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith(PURCHASE_FREE_PREFIX))
async def handle_free_plan_activate(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    plan_service: PlanService,
    free_plan_activation_service: FreePlanActivationService,
    provisioning_notification_service: ProvisioningNotificationService,
    admin_log_service: AdminLogService,
    settings: Settings,
) -> None:
    await state.clear()
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    plan_id_str = callback.data.removeprefix(PURCHASE_FREE_PREFIX)
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None or not plan_service.is_free(plan):
        await callback.answer("Тариф недоступен.", show_alert=True)
        return

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
        await callback.message.answer("Выберите действие в меню.", reply_markup=customer_main_keyboard())
        await callback.answer("Готово.")
        return

    await callback.message.answer(
        outcome.customer_message,
        reply_markup=customer_main_keyboard(),
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
) -> None:
    await _start_receipt_flow(
        callback,
        state,
        bot,
        plan_service=plan_service,
        payment_request_service=payment_request_service,
        promo_activation_service=promo_activation_service,
        provisioning_notification_service=provisioning_notification_service,
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
) -> None:
    await _start_receipt_flow(
        callback,
        state,
        bot,
        plan_service=plan_service,
        payment_request_service=payment_request_service,
        promo_activation_service=promo_activation_service,
        provisioning_notification_service=provisioning_notification_service,
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
    )


@router.message(StateFilter(PurchaseReceiptStates.waiting_receipt), F.document)
async def handle_receipt_document(
    message: Message,
    state: FSMContext,
    bot: Bot,
    payment_request_service: PaymentRequestService,
    settings: Settings,
    admin_log_service: AdminLogService,
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
    )


@router.message(StateFilter(PurchaseReceiptStates.waiting_receipt), F.text, ~F.text.startswith("/"))
async def handle_receipt_text(
    message: Message,
    state: FSMContext,
    bot: Bot,
    payment_request_service: PaymentRequestService,
    settings: Settings,
    admin_log_service: AdminLogService,
) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer(INVALID_RECEIPT_TEXT)
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
    )


@router.message(StateFilter(PurchaseReceiptStates.waiting_receipt))
async def handle_receipt_invalid(message: Message) -> None:
    await message.answer(INVALID_RECEIPT_TEXT)


async def _show_standard_checkout(
    message: Message,
    state: FSMContext,
    *,
    plan,
) -> None:
    await show_promo_prompt(
        message,
        state,
        flow="purchase",
        plan_id=plan.id,
        request_type=PaymentRequestType.PURCHASE.value,
    )


async def _show_renewal_checkout(
    message: Message,
    state: FSMContext,
    *,
    plan,
    vpn_account_id: int,
) -> None:
    await show_promo_prompt(
        message,
        state,
        flow="purchase_renew",
        plan_id=plan.id,
        request_type=PaymentRequestType.RENEWAL.value,
        vpn_account_id=vpn_account_id,
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
    prefix: str,
    purchase_mode: str,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    plan_id = _parse_plan_id(callback.data, prefix)
    if plan_id is None:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer("Тариф недоступен.", show_alert=True)
        return
    if plan_service.is_free(plan):
        await callback.answer(
            "Для бесплатного тарифа нажмите «🎁 Активировать бесплатно».",
            show_alert=True,
        )
        return

    if await payment_request_service.has_pending_purchase(callback.from_user.id):
        await callback.answer(
            "⏳ У вас уже есть заявка на проверке. Дождитесь ответа администратора.",
            show_alert=True,
        )
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
        if callback.message is not None:
            await callback.message.answer(outcome.customer_message, reply_markup=customer_main_keyboard())
        await callback.answer("✅ VPN активирован по промокоду.")
        return

    if purchase_mode == "separate":
        target_name = data.get("target_vpn_account_name")
        target_display = data.get("target_display_name")
        if not isinstance(target_name, str) or not isinstance(target_display, str):
            await callback.answer("Сначала введите название подписки.", show_alert=True)
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
    await callback.message.answer(RECEIPT_PROMPT)
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
) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    plan_id = data.get("plan_id")
    if not isinstance(plan_id, int):
        await state.clear()
        await message.answer("Сессия истекла. Начните покупку заново.", reply_markup=customer_main_keyboard())
        return

    purchase_mode = data.get("purchase_mode", "purchase")
    pricing = await get_pricing_from_state(data)
    try:
        if purchase_mode == "separate":
            target_name = data.get("target_vpn_account_name")
            target_display = data.get("target_display_name")
            if not isinstance(target_name, str) or not isinstance(target_display, str):
                raise PaymentRequestNotFoundError("Данные подписки не найдены. Начните заново.")
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
        await message.answer(exc.message, reply_markup=customer_main_keyboard())
        return
    except PaymentRequestNotFoundError as exc:
        await state.clear()
        await message.answer(exc.message, reply_markup=customer_main_keyboard())
        return

    await state.clear()
    await message.answer(SUCCESS_TEXT, reply_markup=customer_main_keyboard())
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
