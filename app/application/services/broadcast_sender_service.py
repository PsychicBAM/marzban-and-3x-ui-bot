from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from app.application.services.broadcast_service import BroadcastService
from app.domain.enums import BroadcastRecipientStatus, BroadcastStatus
from app.infrastructure.db.session import session_scope
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

SEND_DELAY_SECONDS = 0.05
BATCH_SIZE = 25


class BroadcastSenderService:
    def __init__(self, broadcast_service: BroadcastService) -> None:
        self._broadcast_service = broadcast_service

    async def send_broadcast(
        self,
        bot: Bot,
        broadcast_id: int,
        *,
        admin_telegram_id: int,
    ) -> None:
        try:
            while True:
                async with session_scope() as session:
                    uow = UnitOfWork(session)
                    broadcast = await uow.broadcasts.get_by_id(broadcast_id)
                    if broadcast is None:
                        return
                    if broadcast.status != BroadcastStatus.SENDING.value:
                        return

                    pending = await uow.broadcasts.list_pending_recipients(
                        broadcast_id,
                        limit=BATCH_SIZE,
                    )
                    if not pending:
                        break

                    text_html = BroadcastService.format_message_html(broadcast.text)
                    for recipient in pending:
                        await self._send_one(
                            bot,
                            uow,
                            recipient,
                            telegram_id=recipient.telegram_id,
                            text_html=text_html,
                            photo_file_id=broadcast.photo_file_id,
                        )
                        await asyncio.sleep(SEND_DELAY_SECONDS)

            async with session_scope() as session:
                uow = UnitOfWork(session)
                service = BroadcastService(uow, self._broadcast_service._admin_log)
                await service.finalize_broadcast(
                    broadcast_id,
                    admin_telegram_id=admin_telegram_id,
                    success=True,
                )
        except Exception as exc:
            logger.exception(
                "Broadcast job failed",
                extra={"broadcast_id": broadcast_id, "error": str(exc)[:300]},
            )
            async with session_scope() as session:
                uow = UnitOfWork(session)
                broadcast = await uow.broadcasts.get_by_id(broadcast_id)
                if broadcast is not None:
                    await uow.broadcasts.update_status(
                        broadcast,
                        status=BroadcastStatus.FAILED.value,
                    )
                service = BroadcastService(uow, self._broadcast_service._admin_log)
                await service.finalize_broadcast(
                    broadcast_id,
                    admin_telegram_id=admin_telegram_id,
                    success=False,
                )

    async def _send_one(
        self,
        bot: Bot,
        uow: UnitOfWork,
        recipient,
        *,
        telegram_id: int,
        text_html: str,
        photo_file_id: str | None,
    ) -> None:
        try:
            if photo_file_id:
                await bot.send_photo(
                    telegram_id,
                    photo=photo_file_id,
                    caption=text_html,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await bot.send_message(
                    telegram_id,
                    text_html,
                    parse_mode=ParseMode.HTML,
                )
            await uow.broadcasts.mark_recipient(
                recipient,
                status=BroadcastRecipientStatus.SENT.value,
            )
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 0.5)
            await self._send_one(
                bot,
                uow,
                recipient,
                telegram_id=telegram_id,
                text_html=text_html,
                photo_file_id=photo_file_id,
            )
        except TelegramForbiddenError as exc:
            await uow.broadcasts.mark_recipient(
                recipient,
                status=BroadcastRecipientStatus.BLOCKED.value,
                error_message="bot blocked by user",
            )
            logger.info(
                "Broadcast recipient blocked bot",
                extra={"telegram_id": telegram_id, "error": str(exc)[:200]},
            )
        except TelegramBadRequest as exc:
            message = str(exc)
            if "chat not found" in message.lower() or "user is deactivated" in message.lower():
                await uow.broadcasts.mark_recipient(
                    recipient,
                    status=BroadcastRecipientStatus.BLOCKED.value,
                    error_message=message[:512],
                )
            else:
                await uow.broadcasts.mark_recipient(
                    recipient,
                    status=BroadcastRecipientStatus.FAILED.value,
                    error_message=message[:512],
                )
            logger.warning(
                "Broadcast send failed",
                extra={"telegram_id": telegram_id, "error": message[:200]},
            )
        except Exception as exc:
            await uow.broadcasts.mark_recipient(
                recipient,
                status=BroadcastRecipientStatus.FAILED.value,
                error_message=str(exc)[:512],
            )
            logger.warning(
                "Broadcast send failed",
                extra={"telegram_id": telegram_id, "error": str(exc)[:200]},
            )
