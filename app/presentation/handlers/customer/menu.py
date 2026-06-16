from __future__ import annotations

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import (
    customer_bonuses_keyboard,
    customer_help_keyboard,
    customer_main_keyboard,
    customer_more_keyboard,
)
from app.presentation.states.admin_panel import AdminPanelStates

router = Router(name="customer_menu")


@router.message(menu_text_filter("menu.help"))
async def handle_help_submenu(message: Message, lang: str) -> None:
    await message.answer(
        t(lang, "submenu.help.intro"),
        reply_markup=customer_help_keyboard(lang),
    )


@router.message(menu_text_filter("menu.bonuses"))
async def handle_bonuses_submenu(message: Message, lang: str) -> None:
    await message.answer(
        t(lang, "submenu.bonuses.intro"),
        reply_markup=customer_bonuses_keyboard(lang),
    )


@router.message(menu_text_filter("menu.more"))
async def handle_more_submenu(message: Message, lang: str) -> None:
    await message.answer(
        t(lang, "submenu.more.intro"),
        reply_markup=customer_more_keyboard(lang),
    )


@router.message(menu_text_filter("menu.back"), ~StateFilter(AdminPanelStates.submenu))
async def handle_back_to_main_menu(message: Message, lang: str) -> None:
    await message.answer(
        t(lang, "common.main_menu_short"),
        reply_markup=customer_main_keyboard(lang),
    )


@router.message(menu_text_filter("menu.promo_codes"))
async def handle_promo_codes_info(message: Message, lang: str) -> None:
    await message.answer(
        t(lang, "submenu.bonuses.promo_codes_info"),
        reply_markup=customer_bonuses_keyboard(lang),
    )
