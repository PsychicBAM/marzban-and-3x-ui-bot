from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, User

from app.application.services.user_service import UserService
from app.application.utils.referral_code import parse_start_referral_payload
from app.config.settings import Settings
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.i18n import t
from app.presentation.utils.customer_ui import CAPTION_MAX_LEN, send_keygate_card
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE
from app.presentation.utils.telegram import map_telegram_user

logger = logging.getLogger(__name__)

router = Router(name="start")


def _display_first_name(lang: str, user: User) -> str:
    return user.first_name or t(lang, "user.default_name")


def _start_caption(lang: str, *, first_name: str, is_admin: bool) -> str:
    caption = t(lang, "start.greeting", first_name=first_name)
    if is_admin:
        caption += t(lang, "start.admin_note")
    return caption


@router.message(CommandStart())
async def handle_start(
    message: Message,
    settings: Settings,
    user_service: UserService,
) -> None:
    user = message.from_user
    if user is None:
        return

    referral_code = parse_start_referral_payload(message.text)
    user_info = await user_service.register_or_update(
        map_telegram_user(user),
        referral_code=referral_code,
    )
    is_admin = settings.is_admin(user.id)
    lang = user_info.language_code
    first_name = _display_first_name(lang, user)
    caption = _start_caption(lang, first_name=first_name, is_admin=is_admin)
    keyboard = customer_main_keyboard(lang)

    logger.info(
        "User started bot",
        extra={"telegram_id": user.id, "username": user.username, "is_admin": is_admin},
    )

    if len(caption) <= CAPTION_MAX_LEN:
        await send_keygate_card(
            message,
            caption=caption,
            reply_markup=keyboard,
            menu_hint=t(lang, "start.menu_hint"),
        )
        return

    await send_keygate_card(
        message,
        caption=t(lang, "start.banner_caption"),
        reply_markup=None,
    )
    await message.answer(
        caption,
        reply_markup=keyboard,
        parse_mode=CUSTOMER_PARSE_MODE,
    )


@router.message(Command("admin"))
async def handle_admin_command(
    message: Message,
    settings: Settings,
    user_service: UserService,
) -> None:
    user = message.from_user
    if user is None:
        return

    await user_service.register_or_update(map_telegram_user(user))

    if not settings.is_admin(user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return

    await message.answer("🔐 Админ-панель", reply_markup=admin_main_keyboard())
