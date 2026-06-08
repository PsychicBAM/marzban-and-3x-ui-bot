from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.config.settings import Settings
from app.presentation.filters.admin import IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.customer import customer_main_keyboard

router = Router(name="admin_menu")
router.message.filter(IsAdminFilter())

PLACEHOLDER = "🚧 Раздел в разработке. Функция будет доступна на следующем этапе."

ADMIN_PLACEHOLDER_BUTTONS: set[str] = set()


@router.message(F.text == "🏠 Главное меню")
async def handle_back_to_customer_menu(message: Message) -> None:
    await message.answer("🏠 Главное меню клиента", reply_markup=customer_main_keyboard())


@router.message(F.text.in_(ADMIN_PLACEHOLDER_BUTTONS))
async def handle_admin_menu_items(message: Message) -> None:
    await message.answer(PLACEHOLDER, reply_markup=admin_main_keyboard())
