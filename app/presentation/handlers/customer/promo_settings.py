from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.infrastructure.db.uow import UnitOfWork
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.admin_broadcast import promo_settings_keyboard
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE
from app.presentation.utils.telegram import safe_edit_message_text

router = Router(name="customer_promo_settings")


def _promo_settings_text(*, enabled: bool, lang: str) -> str:
    status_key = "promo.settings.on" if enabled else "promo.settings.off"
    return (
        t(lang, "promo.settings.title", status=t(lang, status_key))
        + "\n\n"
        + t(lang, "promo.settings.desc")
    )


@router.message(menu_text_filter("menu.promo_news"))
async def handle_promo_settings(message: Message, uow: UnitOfWork, lang: str) -> None:
    if message.from_user is None:
        return
    user = await uow.users.get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer(t(lang, "common.start_first"), reply_markup=customer_main_keyboard(lang))
        return
    await message.answer(
        _promo_settings_text(enabled=user.promo_enabled, lang=lang),
        reply_markup=promo_settings_keyboard(enabled=user.promo_enabled),
        parse_mode=CUSTOMER_PARSE_MODE,
    )


@router.callback_query(F.data.in_({"promo:on", "promo:off"}))
async def handle_promo_toggle(callback: CallbackQuery, uow: UnitOfWork, lang: str) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return
    user = await uow.users.get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    enabled = callback.data == "promo:on"
    await uow.users.set_promo_enabled(user, enabled=enabled)
    if callback.message is not None:
        edited = await safe_edit_message_text(
            callback.message,
            _promo_settings_text(enabled=enabled, lang=lang),
            reply_markup=promo_settings_keyboard(enabled=enabled),
        )
        if edited:
            await callback.answer(t(lang, "common.saved"))
        else:
            await callback.answer(t(lang, "common.already_actual"))
        return
    await callback.answer(t(lang, "common.saved"))
