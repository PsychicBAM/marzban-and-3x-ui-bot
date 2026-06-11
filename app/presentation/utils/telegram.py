from __future__ import annotations

import logging

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message, User as TelegramUser

from app.application.dto.user import TelegramUserData
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE

logger = logging.getLogger(__name__)

_MESSAGE_NOT_MODIFIED = "message is not modified"


async def safe_edit_message_text(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | ParseMode = CUSTOMER_PARSE_MODE,
) -> bool:
    """Edit message text; ignore unchanged content. Returns True if Telegram applied the edit."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except TelegramBadRequest as exc:
        if _MESSAGE_NOT_MODIFIED in str(exc).lower():
            return False
        logger.warning("edit_text failed", extra={"error": str(exc)[:300]})
        raise


async def safe_edit_message_caption(
    message: Message,
    caption: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | ParseMode = CUSTOMER_PARSE_MODE,
) -> bool:
    """Edit photo caption; ignore unchanged content. Returns True if Telegram applied the edit."""
    try:
        await message.edit_caption(caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except TelegramBadRequest as exc:
        if _MESSAGE_NOT_MODIFIED in str(exc).lower():
            return False
        logger.warning("edit_caption failed", extra={"error": str(exc)[:300]})
        raise


async def edit_or_answer_text(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | ParseMode = CUSTOMER_PARSE_MODE,
) -> Message:
    """Edit text message, or send a new one if the source is a photo card."""
    if message.photo:
        return await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    return message


def map_telegram_user(user: TelegramUser) -> TelegramUserData:
    return TelegramUserData(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
    )
