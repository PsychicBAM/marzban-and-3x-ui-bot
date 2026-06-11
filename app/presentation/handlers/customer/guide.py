from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.presentation.filters.customer_menu import guide_menu_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.customer_guide import (
    GUIDE_BACK_DEVICES,
    GUIDE_BACK_MENU,
    GUIDE_DEVICES,
    guide_devices_keyboard,
    guide_step_key,
    guide_steps_keyboard,
)
from app.presentation.utils.customer_ui import edit_keygate_card, send_keygate_card
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE

router = Router(name="customer_guide")


def _guide_card_caption(lang: str) -> str:
    return t(lang, "guide.card_caption")


@router.message(guide_menu_filter())
async def handle_guide_menu(message: Message, lang: str) -> None:
    await send_keygate_card(
        message,
        caption=_guide_card_caption(lang),
        reply_markup=guide_devices_keyboard(lang),
    )


@router.callback_query(F.data == GUIDE_DEVICES)
async def handle_guide_devices(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await edit_keygate_card(
        callback.message,
        _guide_card_caption(lang),
        reply_markup=guide_devices_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("guide:") & ~F.data.in_({GUIDE_BACK_MENU, GUIDE_BACK_DEVICES, GUIDE_DEVICES}))
async def handle_guide_device(callback: CallbackQuery, lang: str) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    step_key = guide_step_key(callback.data)
    if step_key is None:
        await callback.answer()
        return
    if callback.message.photo:
        await edit_keygate_card(
            callback.message,
            t(lang, step_key),
            reply_markup=guide_steps_keyboard(lang),
        )
    else:
        await callback.message.answer(
            t(lang, step_key),
            reply_markup=guide_steps_keyboard(lang),
            parse_mode=CUSTOMER_PARSE_MODE,
        )
    await callback.answer()


@router.callback_query(F.data == GUIDE_BACK_DEVICES)
async def handle_guide_back_devices(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    if callback.message.photo:
        await edit_keygate_card(
            callback.message,
            _guide_card_caption(lang),
            reply_markup=guide_devices_keyboard(lang),
        )
    else:
        await callback.message.answer(
            _guide_card_caption(lang),
            reply_markup=guide_devices_keyboard(lang),
            parse_mode=CUSTOMER_PARSE_MODE,
        )
    await callback.answer()


@router.callback_query(F.data == GUIDE_BACK_MENU)
async def handle_guide_back_menu(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer(
        t(lang, "common.main_menu"),
        reply_markup=customer_main_keyboard(lang),
        parse_mode=CUSTOMER_PARSE_MODE,
    )
    await callback.answer()
