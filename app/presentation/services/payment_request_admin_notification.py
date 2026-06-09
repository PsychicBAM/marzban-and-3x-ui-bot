from __future__ import annotations

import logging

from aiogram import Bot

from app.application.dto.payment_request import PaymentRequestInfo
from app.application.services.admin_log_service import AdminLogService
from app.application.services.payment_request_service import PaymentRequestService
from app.config.settings import Settings
from app.domain.enums import AdminActionType
from app.presentation.keyboards.payment_requests import new_payment_request_keyboard

logger = logging.getLogger(__name__)


async def notify_admins_new_payment_request(
    bot: Bot,
    *,
    settings: Settings,
    payment_request_service: PaymentRequestService,
    admin_log_service: AdminLogService,
    request: PaymentRequestInfo,
) -> None:
    """Push a new payment request alert to every configured admin."""
    admin_ids = settings.admin_telegram_ids
    if not admin_ids:
        logger.warning(
            "Skipping payment request admin notification: no ADMIN_TELEGRAM_IDS",
            extra={"payment_request_id": request.id},
        )
        return

    text = payment_request_service.format_admin_new_request_notification(request)
    keyboard = new_payment_request_keyboard(request.id)

    notified = 0
    failed = 0
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard)
            notified += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "Failed to notify admin about new payment request",
                extra={
                    "payment_request_id": request.id,
                    "admin_telegram_id": admin_id,
                    "error": str(exc)[:300],
                },
            )

    await admin_log_service.log(
        admin_telegram_id=admin_ids[0],
        action=AdminActionType.PAYMENT_REQUEST_ADMIN_NOTIFIED,
        details={
            "payment_request_id": request.id,
            "user_id": request.user_id,
            "request_type": request.request_type,
            "notified_count": notified,
            "failed_count": failed,
        },
    )
