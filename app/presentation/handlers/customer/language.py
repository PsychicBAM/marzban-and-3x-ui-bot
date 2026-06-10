from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.application.services.user_service import UserService
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import LANG_EN, LANG_RU, LANG_SET_EN, LANG_SET_RU, LANG_BACK, language_picker_keyboard, t
from app.presentation.keyboards.customer import customer_main_keyboard

router = Router(name="customer_language")


@router.message(menu_text_filter("menu.language"))
async def handle_language_menu(message: Message, lang: str) -> None:
    await message.answer(t(lang, "lang.choose"), reply_markup=language_picker_keyboard(lang))


@router.callback_query(F.data == LANG_SET_RU)
async def handle_set_russian(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    await user_service.set_user_language(LANG_RU, telegram_id=callback.from_user.id)
    if callback.message is not None:
        await callback.message.answer(
            t(LANG_RU, "lang.changed_ru"),
            reply_markup=customer_main_keyboard(LANG_RU),
        )
    await callback.answer()


@router.callback_query(F.data == LANG_SET_EN)
async def handle_set_english(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    await user_service.set_user_language(LANG_EN, telegram_id=callback.from_user.id)
    if callback.message is not None:
        await callback.message.answer(
            t(LANG_EN, "lang.changed_en"),
            reply_markup=customer_main_keyboard(LANG_EN),
        )
    await callback.answer()


@router.callback_query(F.data == LANG_BACK)
async def handle_language_back(callback: CallbackQuery, lang: str) -> None:
    if callback.message is not None:
        await callback.message.answer(
            t(lang, "common.main_menu"),
            reply_markup=customer_main_keyboard(lang),
        )
    await callback.answer()
