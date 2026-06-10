from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.application.services.settings_service import SettingsService
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard

router = Router(name="customer_menu")


@router.message(menu_text_filter("menu.instruction"))
async def handle_instruction(message: Message, settings_service: SettingsService, lang: str) -> None:
    config = await settings_service.get_instruction_settings()
    text = settings_service.format_customer_instruction(config)
    await message.answer(text, reply_markup=customer_main_keyboard(lang))


@router.message(menu_text_filter("menu.support"))
async def handle_support(message: Message, settings_service: SettingsService, lang: str) -> None:
    config = await settings_service.get_support_settings()
    text = settings_service.format_customer_support(config)
    await message.answer(text, reply_markup=customer_main_keyboard(lang))
