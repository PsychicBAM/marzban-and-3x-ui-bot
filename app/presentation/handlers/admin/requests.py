from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import (
    PaymentRequestAlreadyProcessedError,
    PaymentRequestNotFoundError,
)
from app.application.services.admin_log_service import AdminLogService
from app.application.services.payment_approval_service import PaymentApprovalService
from app.application.services.payment_request_service import PaymentRequestService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.presentation.services.customer_provisioning_delivery import deliver_provisioning_to_customer
from app.presentation.services.referral_notifications import send_referral_notifications
from app.domain.enums import AdminActionType, ReceiptFileType
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.payment_requests import (
    CB_APPROVE_PREFIX,
    CB_LIST,
    CB_OPEN_PREFIX,
    CB_REJECT_PREFIX,
    empty_requests_keyboard,
    pending_requests_keyboard,
    request_details_keyboard,
)

router = Router(name="admin_requests")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())

CUSTOMER_REJECTED_TEXT = (
    "❌ Оплата не подтверждена. Если вы считаете, что это ошибка, свяжитесь с поддержкой."
)


@router.message(F.text == "📥 Заявки")
async def handle_admin_requests(message: Message, payment_request_service: PaymentRequestService) -> None:
    await _send_pending_list(message, payment_request_service)


@router.callback_query(F.data == CB_LIST)
async def handle_requests_list_callback(
    callback: CallbackQuery,
    payment_request_service: PaymentRequestService,
) -> None:
    await _send_pending_list(callback, payment_request_service)


@router.callback_query(F.data.startswith(CB_OPEN_PREFIX))
async def handle_open_request(
    callback: CallbackQuery,
    bot: Bot,
    payment_request_service: PaymentRequestService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    request_id = _parse_id(callback.data, CB_OPEN_PREFIX)
    if request_id is None:
        await callback.answer("Некорректная заявка.", show_alert=True)
        return

    try:
        item = await payment_request_service.get_request(request_id)
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    text = payment_request_service.format_request_details(item)
    await callback.message.edit_text(text, reply_markup=request_details_keyboard(item.id))

    caption = payment_request_service.format_receipt_caption(item)
    if item.receipt_file_type == ReceiptFileType.PHOTO.value and item.receipt_file_id:
        await bot.send_photo(callback.message.chat.id, item.receipt_file_id, caption=caption)
    elif item.receipt_file_type == ReceiptFileType.DOCUMENT.value and item.receipt_file_id:
        await bot.send_document(callback.message.chat.id, item.receipt_file_id, caption=caption)

    await callback.answer()


@router.callback_query(F.data.startswith(CB_APPROVE_PREFIX))
async def handle_approve_request(
    callback: CallbackQuery,
    bot: Bot,
    payment_approval_service: PaymentApprovalService,
    provisioning_notification_service: ProvisioningNotificationService,
    admin_log_service: AdminLogService,
) -> None:
    await _process_approval(
        callback,
        bot,
        payment_approval_service,
        provisioning_notification_service,
        admin_log_service,
    )


@router.callback_query(F.data.startswith(CB_REJECT_PREFIX))
async def handle_reject_request(
    callback: CallbackQuery,
    bot: Bot,
    payment_request_service: PaymentRequestService,
    admin_log_service: AdminLogService,
) -> None:
    await _process_rejection(callback, bot, payment_request_service, admin_log_service)


async def _send_pending_list(
    target: Message | CallbackQuery,
    payment_request_service: PaymentRequestService,
) -> None:
    requests = await payment_request_service.list_pending_requests()
    text = payment_request_service.format_pending_list(requests)
    keyboard = pending_requests_keyboard(requests) if requests else empty_requests_keyboard()

    if isinstance(target, CallbackQuery):
        if target.message is None:
            await target.answer()
            return
        await target.message.edit_text(text, reply_markup=keyboard)
        await target.answer()
        return

    await target.answer(text, reply_markup=keyboard)


async def _process_approval(
    callback: CallbackQuery,
    bot: Bot,
    payment_approval_service: PaymentApprovalService,
    provisioning_notification_service: ProvisioningNotificationService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    request_id = _parse_id(callback.data, CB_APPROVE_PREFIX)
    if request_id is None:
        await callback.answer("Некорректная заявка.", show_alert=True)
        return

    try:
        outcome = await payment_approval_service.approve_with_provisioning(
            request_id,
            admin_telegram_id=callback.from_user.id,
        )
    except PaymentRequestAlreadyProcessedError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    admin_text = outcome.admin_message
    if outcome.notify_customer and outcome.provisioning is not None:
        try:
            qr_admin_note = await deliver_provisioning_to_customer(
                bot,
                telegram_id=outcome.telegram_id,
                customer_message=outcome.customer_message,
                provisioning=outcome.provisioning,
                notification_service=provisioning_notification_service,
                admin_log_service=admin_log_service,
                admin_telegram_id=callback.from_user.id,
                payment_request_id=outcome.request_id,
            )
            admin_text += qr_admin_note
        except Exception:
            admin_text += "\n⚠️ Не удалось уведомить клиента в Telegram."
    elif outcome.failed:
        await callback.answer("VPN не выдан. См. сообщение ниже.", show_alert=True)
    elif outcome.partial:
        await callback.answer("Частичная выдача VPN.", show_alert=True)

    await callback.message.answer(admin_text, reply_markup=admin_main_keyboard())
    if outcome.referral_notifications:
        await send_referral_notifications(bot, outcome.referral_notifications)
    if not outcome.failed and not outcome.partial:
        await callback.answer("Готово.")


async def _process_rejection(
    callback: CallbackQuery,
    bot: Bot,
    payment_request_service: PaymentRequestService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    request_id = _parse_id(callback.data, CB_REJECT_PREFIX)
    if request_id is None:
        await callback.answer("Некорректная заявка.", show_alert=True)
        return

    try:
        item = await payment_request_service.reject_request(
            request_id,
            admin_telegram_id=callback.from_user.id,
        )
        await admin_log_service.log(
            admin_telegram_id=callback.from_user.id,
            action=AdminActionType.PAYMENT_REJECTED,
            details={"payment_request_id": item.id, "user_id": item.user_id, "plan_id": item.plan_id},
        )
    except PaymentRequestAlreadyProcessedError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return

    admin_text = f"❌ Заявка #{item.id} отклонена."
    try:
        await bot.send_message(item.telegram_id, CUSTOMER_REJECTED_TEXT)
    except Exception:
        admin_text += "\n⚠️ Не удалось уведомить клиента в Telegram."

    await callback.message.answer(admin_text, reply_markup=admin_main_keyboard())
    await callback.answer("Готово.")


def _parse_id(callback_data: str, prefix: str) -> int | None:
    try:
        return int(callback_data.removeprefix(prefix))
    except ValueError:
        return None
