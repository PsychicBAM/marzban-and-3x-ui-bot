from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.infrastructure.db.uow import UnitOfWork
from app.presentation.keyboards.admin_broadcast import promo_settings_keyboard
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.utils.telegram import safe_edit_message_text

router = Router(name="customer_promo_settings")


def _promo_settings_text(*, enabled: bool) -> str:
    status = "включены" if enabled else "выключены"
    return (
        f"🔔 <b>Акции и новости</b>: <b>{status}</b>\n\n"
        "Когда выключено, промо-рассылки от бота не приходят."
    )


@router.message(F.text == "🔔 Акции и новости")
async def handle_promo_settings(message: Message, uow: UnitOfWork) -> None:
    if message.from_user is None:
        return
    user = await uow.users.get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("Сначала нажмите /start.", reply_markup=customer_main_keyboard())
        return
    await message.answer(
        _promo_settings_text(enabled=user.promo_enabled),
        reply_markup=promo_settings_keyboard(enabled=user.promo_enabled),
    )


@router.callback_query(F.data.in_({"promo:on", "promo:off"}))
async def handle_promo_toggle(callback: CallbackQuery, uow: UnitOfWork) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return
    user = await uow.users.get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer("Сначала нажмите /start.", show_alert=True)
        return
    enabled = callback.data == "promo:on"
    await uow.users.set_promo_enabled(user, enabled=enabled)
    if callback.message is not None:
        edited = await safe_edit_message_text(
            callback.message,
            _promo_settings_text(enabled=enabled),
            reply_markup=promo_settings_keyboard(enabled=enabled),
        )
        if edited:
            await callback.answer("Сохранено.")
        else:
            await callback.answer("Настройки уже актуальны.")
        return
    await callback.answer("Сохранено.")
