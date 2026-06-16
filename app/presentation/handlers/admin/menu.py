from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.presentation.filters.admin import IsAdminFilter
from app.presentation.keyboards.admin import (
    ADMIN_BACK,
    ADMIN_HOME,
    ADMIN_MANAGEMENT,
    ADMIN_MARKETING,
    ADMIN_SYSTEM,
    admin_main_keyboard,
    admin_management_keyboard,
    admin_marketing_keyboard,
    admin_system_keyboard,
)
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.states.admin_panel import AdminPanelStates

router = Router(name="admin_menu")
router.message.filter(IsAdminFilter())

PLACEHOLDER = "🚧 Раздел в разработке. Функция будет доступна на следующем этапе."

ADMIN_PLACEHOLDER_BUTTONS: set[str] = set()

MANAGEMENT_INTRO = "🛠 Управление\nВыберите раздел:"
MARKETING_INTRO = "📣 Маркетинг\nИнструменты для продаж и удержания клиентов:"
SYSTEM_INTRO = "🩺 Система\nСтатистика и технический контроль:"


@router.message(F.text == ADMIN_MANAGEMENT)
async def handle_management_submenu(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminPanelStates.submenu)
    await message.answer(MANAGEMENT_INTRO, reply_markup=admin_management_keyboard())


@router.message(F.text == ADMIN_MARKETING)
async def handle_marketing_submenu(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminPanelStates.submenu)
    await message.answer(MARKETING_INTRO, reply_markup=admin_marketing_keyboard())


@router.message(F.text == ADMIN_SYSTEM)
async def handle_system_submenu(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminPanelStates.submenu)
    await message.answer(SYSTEM_INTRO, reply_markup=admin_system_keyboard())


@router.message(F.text == ADMIN_BACK, StateFilter(AdminPanelStates.submenu))
async def handle_admin_submenu_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🔐 Админ-панель", reply_markup=admin_main_keyboard())


@router.message(F.text == ADMIN_HOME)
async def handle_back_to_customer_menu(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await message.answer("🏠 Главное меню клиента", reply_markup=customer_main_keyboard(lang))


@router.message(F.text.in_(ADMIN_PLACEHOLDER_BUTTONS))
async def handle_admin_menu_items(message: Message) -> None:
    await message.answer(PLACEHOLDER, reply_markup=admin_main_keyboard())
