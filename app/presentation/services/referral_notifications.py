from __future__ import annotations

import logging

from aiogram import Bot

from app.application.dto.referral import ReferralNotification

logger = logging.getLogger(__name__)


async def send_referral_notifications(bot: Bot, notifications: list[ReferralNotification]) -> None:
    for item in notifications:
        try:
            await bot.send_message(item.telegram_id, item.message)
        except Exception:
            logger.warning(
                "Failed to send referral notification",
                extra={"telegram_id": item.telegram_id},
            )
