from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import PaymentRequestDuplicateError, PaymentRequestNotFoundError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.payment_request_service import PaymentRequestService
from app.application.services.plan_service import PlanService
from app.config.settings import Settings
from app.presentation.services.payment_request_admin_notification import notify_admins_new_payment_request
from app.domain.enums import ReceiptFileType
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.purchase import (
    PURCHASE_CANCEL,
    PURCHASE_PAID_PREFIX,
    purchase_checkout_keyboard,
)
from app.presentation.keyboards.tariffs import PURCHASE_CALLBACK_PREFIX, plan_selection_keyboard
from app.presentation.states.purchase import PurchaseReceiptStates

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
) -> None:
    await state.clear()
    if callback.data is None or callback.message is None:
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

    payment_details = await payment_request_service.get_payment_details_text()
    has_details = await payment_request_service.has_payment_details()
    text = payment_request_service.format_purchase_checkout(
        plan_details=plan_service.format_plan_details(plan),
        payment_details=payment_details,
        has_payment_details=has_details,
    )
    await callback.message.edit_text(
        text,
        reply_markup=purchase_checkout_keyboard(plan.id),
    )
    await callback.answer()


@router.callback_query(F.data == PURCHASE_CANCEL)
async def handle_purchase_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text("❌ Покупка отменена.")
    await callback.message.answer("Выберите действие в меню.", reply_markup=customer_main_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith(PURCHASE_PAID_PREFIX))
async def handle_purchase_paid(
    callback: CallbackQuery,
    state: FSMContext,
    payment_request_service: PaymentRequestService,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    plan_id_str = callback.data.removeprefix(PURCHASE_PAID_PREFIX)
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    if await payment_request_service.has_pending_purchase(callback.from_user.id):
        await callback.answer(
            "⏳ У вас уже есть заявка на проверке. Дождитесь ответа администратора.",
            show_alert=True,
        )
        return

    await state.update_data(plan_id=plan_id)
    await state.set_state(PurchaseReceiptStates.waiting_receipt)
    await callback.message.answer(RECEIPT_PROMPT)
    await callback.answer()


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

    try:
        request = await payment_request_service.create_purchase_request(
            telegram_id=message.from_user.id,
            plan_id=plan_id,
            receipt_file_id=receipt_file_id,
            receipt_file_type=receipt_file_type,
            user_comment=user_comment,
            receipt_message_id=receipt_message_id,
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
