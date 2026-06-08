from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile

from app.application.dto.provisioning import ProvisioningResult
from app.application.services.admin_log_service import AdminLogService
from app.application.services.provisioning_notification_service import (
    PanelQrDelivery,
    ProvisioningNotificationService,
    QR_FAILURE_CUSTOMER_MESSAGE,
)
logger = logging.getLogger(__name__)


async def deliver_provisioning_to_customer(
    bot: Bot,
    *,
    telegram_id: int,
    customer_message: str,
    provisioning: ProvisioningResult,
    notification_service: ProvisioningNotificationService,
    admin_log_service: AdminLogService,
    admin_telegram_id: int,
    payment_request_id: int | None = None,
) -> str:
    """
    Send provisioning text message and per-panel QR images.
    Returns admin supplement describing QR delivery status.
    """
    await bot.send_message(telegram_id, customer_message)

    deliveries = notification_service.build_panel_qr_deliveries(provisioning)
    await notification_service.log_qr_failures(
        admin_log_service,
        admin_telegram_id=admin_telegram_id,
        payment_request_id=payment_request_id,
        deliveries=deliveries,
    )

    for delivery in deliveries:
        if delivery.succeeded and delivery.png_bytes is not None:
            try:
                photo = BufferedInputFile(delivery.png_bytes, filename=delivery.filename)
                await bot.send_photo(telegram_id, photo, caption=delivery.caption)
            except Exception as exc:
                safe_error = str(exc)[:500]
                logger.warning(
                    "Failed to send QR photo to customer",
                    extra={"panel": delivery.panel, "error": safe_error},
                )
                _mark_delivery_failed(delivery, safe_error)
                await bot.send_message(telegram_id, QR_FAILURE_CUSTOMER_MESSAGE)
        elif delivery.error is not None:
            await bot.send_message(telegram_id, QR_FAILURE_CUSTOMER_MESSAGE)

    return notification_service.admin_qr_status_message(deliveries)


def _mark_delivery_failed(delivery: PanelQrDelivery, error: str) -> None:
    delivery.png_bytes = None
    delivery.error = error
