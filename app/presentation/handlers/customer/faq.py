from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.customer_faq import (
    FAQ_BACK_LIST,
    FAQ_BACK_MENU,
    FAQ_MENU,
    faq_answer_key,
    faq_answer_keyboard,
    faq_menu_keyboard,
)
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE
from app.presentation.utils.telegram import safe_edit_message_text

router = Router(name="customer_faq")


def _faq_list_text(lang: str) -> str:
    return f"{t(lang, 'faq.title')}\n\n{t(lang, 'faq.choose')}"


@router.message(menu_text_filter("menu.faq"))
async def handle_faq_menu(message: Message, lang: str) -> None:
    await message.answer(
        _faq_list_text(lang),
        reply_markup=faq_menu_keyboard(lang),
        parse_mode=CUSTOMER_PARSE_MODE,
    )


@router.callback_query(F.data == FAQ_MENU)
async def handle_faq_menu_callback(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await safe_edit_message_text(callback.message, _faq_list_text(lang), reply_markup=faq_menu_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("faq:q"))
async def handle_faq_question(callback: CallbackQuery, lang: str) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    answer_key = faq_answer_key(callback.data)
    if answer_key is None:
        await callback.answer()
        return
    await safe_edit_message_text(
        callback.message,
        t(lang, answer_key),
        reply_markup=faq_answer_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == FAQ_BACK_LIST)
async def handle_faq_back_list(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await safe_edit_message_text(callback.message, _faq_list_text(lang), reply_markup=faq_menu_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == FAQ_BACK_MENU)
async def handle_faq_back_menu(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer(
        t(lang, "common.main_menu"),
        reply_markup=customer_main_keyboard(lang),
        parse_mode=CUSTOMER_PARSE_MODE,
    )
    await callback.answer()
