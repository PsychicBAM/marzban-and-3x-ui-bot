from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.config.settings import get_settings
from app.infrastructure.bootstrap import bootstrap_database
from app.infrastructure.logging.setup import setup_logging
from app.infrastructure.scheduler.expiry_scheduler import (
    ExpiryNotificationScheduler,
    set_expiry_scheduler,
)
from app.presentation.bot.factory import create_bot, create_dispatcher

logger = logging.getLogger(__name__)


async def run_bot() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    await bootstrap_database(settings)

    bot: Bot = create_bot(settings)
    dispatcher = create_dispatcher(settings)

    scheduler = ExpiryNotificationScheduler(settings)
    set_expiry_scheduler(scheduler)
    scheduler.start(bot)
    await scheduler.bootstrap()

    logger.info("Starting Telegram VPN bot")
    try:
        await dispatcher.start_polling(bot, settings=settings)
    finally:
        scheduler.shutdown()


def main() -> None:
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")


if __name__ == "__main__":
    main()
