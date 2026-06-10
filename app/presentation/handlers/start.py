from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.application.services.user_service import UserService
from app.application.utils.referral_code import parse_start_referral_payload
from app.config.settings import Settings
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.utils.telegram import map_telegram_user

logger = logging.getLogger(__name__)

router = Router(name="start")


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

    logger.info(
        "User started bot",
        extra={"telegram_id": user.id, "username": user.username, "is_admin": is_admin},
    )

    greeting = (
        f"Здравствуйте, {user_info.full_name}!\n\n"
        "Добро пожаловать в VPN-бот.\n"
        "Выберите действие в меню ниже."
    )

    if is_admin:
        greeting += "\n\n🔐 У вас есть доступ к админ-панели."
        await message.answer(greeting, reply_markup=admin_main_keyboard())
        return

    await message.answer(greeting, reply_markup=customer_main_keyboard())


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
