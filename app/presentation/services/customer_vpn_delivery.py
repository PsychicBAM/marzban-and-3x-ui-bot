from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile

from app.application.services.provisioning_notification_service import (
    ProvisioningNotificationService,
    QR_FAILURE_CUSTOMER_MESSAGE,
)

logger = logging.getLogger(__name__)


async def send_qr_codes_for_links(
    bot: Bot,
    *,
    telegram_id: int,
    links: dict[str, str],
    notification_service: ProvisioningNotificationService,
) -> None:
    if not links:
        await bot.send_message(telegram_id, "Не удалось получить ссылку. Свяжитесь с поддержкой.")
        return

    deliveries = notification_service.build_panel_qr_deliveries_from_links(links)
    for delivery in deliveries:
        if delivery.succeeded and delivery.png_bytes is not None:
            try:
                photo = BufferedInputFile(delivery.png_bytes, filename=delivery.filename)
                await bot.send_photo(telegram_id, photo, caption=delivery.caption)
            except Exception as exc:
                logger.warning(
                    "Failed to send on-demand QR photo",
                    extra={"panel": delivery.panel, "error": str(exc)[:300]},
                )
                await bot.send_message(
                    telegram_id,
                    f"🔗 {delivery.panel}:\n{delivery.link}\n\n{QR_FAILURE_CUSTOMER_MESSAGE}",
                )
        elif delivery.error is not None:
            await bot.send_message(
                telegram_id,
                f"🔗 {delivery.panel}:\n{delivery.link}\n\n{QR_FAILURE_CUSTOMER_MESSAGE}",
            )
