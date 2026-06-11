from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup

from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE

logger = logging.getLogger(__name__)

CAPTION_MAX_LEN = 1024

_BANNER_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "assets" / "keygate_banner.png",
    Path.cwd() / "app" / "assets" / "keygate_banner.png",
)


def resolve_banner_path() -> Path | None:
    for path in _BANNER_CANDIDATES:
        if path.is_file():
            return path
    return None


BANNER_PATH = _BANNER_CANDIDATES[0]


def _truncate_caption(caption: str) -> str:
    if len(caption) <= CAPTION_MAX_LEN:
        return caption
    return caption[: CAPTION_MAX_LEN - 1] + "…"


async def _answer_photo(
    target: Message | Bot,
    *,
    chat_id: int | None,
    photo: FSInputFile,
    caption: str,
    reply_markup: ReplyKeyboardMarkup | InlineKeyboardMarkup | None,
    parse_mode: str | ParseMode,
) -> Message:
    if isinstance(target, Message):
        return await target.answer_photo(
            photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    if chat_id is None:
        raise ValueError("chat_id is required when target is Bot")
    return await target.send_photo(
        chat_id,
        photo,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


async def _answer_text(
    target: Message | Bot,
    *,
    chat_id: int | None,
    text: str,
    reply_markup: ReplyKeyboardMarkup | InlineKeyboardMarkup | None,
    parse_mode: str | ParseMode,
) -> Message:
    if isinstance(target, Message):
        return await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    if chat_id is None:
        raise ValueError("chat_id is required when target is Bot")
    return await target.send_message(
        chat_id,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


async def send_keygate_card(
    target: Message | Bot,
    *,
    chat_id: int | None = None,
    caption: str,
    reply_markup: ReplyKeyboardMarkup | InlineKeyboardMarkup | None = None,
    parse_mode: str | ParseMode = CUSTOMER_PARSE_MODE,
    menu_hint: str | None = None,
) -> Message:
    """Send KeyGate banner as a branded card (photo + caption + keyboard)."""
    safe_caption = _truncate_caption(caption)
    banner_path = resolve_banner_path()
    if banner_path is not None:
        photo = FSInputFile(banner_path)
        if isinstance(reply_markup, ReplyKeyboardMarkup):
            try:
                return await _answer_photo(
                    target,
                    chat_id=chat_id,
                    photo=photo,
                    caption=safe_caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
            except TelegramBadRequest as exc:
                logger.info(
                    "Reply keyboard on photo failed; sending menu hint separately",
                    extra={"error": str(exc)[:200]},
                )
                photo_message = await _answer_photo(
                    target,
                    chat_id=chat_id,
                    photo=photo,
                    caption=safe_caption,
                    reply_markup=None,
                    parse_mode=parse_mode,
                )
                if menu_hint:
                    await _answer_text(
                        target,
                        chat_id=chat_id,
                        text=menu_hint,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
                return photo_message
        return await _answer_photo(
            target,
            chat_id=chat_id,
            photo=photo,
            caption=safe_caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    logger.warning("KeyGate banner asset missing", extra={"paths": [str(p) for p in _BANNER_CANDIDATES]})
    return await _answer_text(
        target,
        chat_id=chat_id,
        text=safe_caption,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


async def send_keygate_banner(
    target: Message | Bot,
    *,
    chat_id: int | None = None,
    caption: str,
    reply_markup: ReplyKeyboardMarkup | InlineKeyboardMarkup | None = None,
    lang: str | None = None,
    menu_hint: str | None = None,
) -> Message:
    """Backward-compatible alias for send_keygate_card."""
    del lang
    return await send_keygate_card(
        target,
        chat_id=chat_id,
        caption=caption,
        reply_markup=reply_markup,
        menu_hint=menu_hint,
    )


async def edit_keygate_card(
    message: Message,
    caption: str,
    *,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
    parse_mode: str | ParseMode = CUSTOMER_PARSE_MODE,
) -> bool:
    """Update caption/keyboard on a photo card, or fall back to text edit."""
    from app.presentation.utils.telegram import safe_edit_message_caption, safe_edit_message_text

    safe_caption = _truncate_caption(caption)
    if message.photo:
        return await safe_edit_message_caption(
            message,
            safe_caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    return await safe_edit_message_text(
        message,
        safe_caption,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
