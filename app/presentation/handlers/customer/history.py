from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.application.services.customer_history_service import CustomerHistoryService
from app.application.services.user_service import UserService
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.customer_history import (
    HIST_BACK_MENU,
    HIST_PAGE_PREFIX,
    history_keyboard,
)
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE
from app.presentation.utils.telegram import safe_edit_message_text

router = Router(name="customer_history")


@router.message(menu_text_filter("menu.history"))
async def handle_history_menu(
    message: Message,
    user_service: UserService,
    customer_history_service: CustomerHistoryService,
    lang: str,
) -> None:
    if message.from_user is None:
        return
    user = await user_service.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer(t(lang, "common.start_first"), reply_markup=customer_main_keyboard(lang))
        return
    text, page, pages = await customer_history_service.get_page(user.id, lang=lang, page=0)
    await message.answer(
        text,
        reply_markup=history_keyboard(lang, page=page, pages=pages),
        parse_mode=CUSTOMER_PARSE_MODE,
    )


@router.callback_query(F.data.startswith(HIST_PAGE_PREFIX))
async def handle_history_page(
    callback: CallbackQuery,
    user_service: UserService,
    customer_history_service: CustomerHistoryService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        page = int(callback.data.removeprefix(HIST_PAGE_PREFIX))
    except ValueError:
        await callback.answer()
        return
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    text, page, pages = await customer_history_service.get_page(user.id, lang=lang, page=page)
    await safe_edit_message_text(
        callback.message,
        text,
        reply_markup=history_keyboard(lang, page=page, pages=pages),
    )
    await callback.answer()


@router.callback_query(F.data == HIST_BACK_MENU)
async def handle_history_back_menu(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer(
        t(lang, "common.main_menu"),
        reply_markup=customer_main_keyboard(lang),
        parse_mode=CUSTOMER_PARSE_MODE,
    )
    await callback.answer()


@router.callback_query(F.data == "hist:noop")
async def handle_history_noop(callback: CallbackQuery) -> None:
    await callback.answer()
