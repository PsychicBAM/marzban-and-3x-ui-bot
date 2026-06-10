from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import ReferralError
from app.application.services.referral_service import ReferralService
from app.infrastructure.db.uow import UnitOfWork
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.referral import (
    REF_APPLY,
    REF_BONUSES,
    REF_HOME,
    REF_LINK,
    REF_STATS,
    referral_inline_keyboard,
)
from app.presentation.services.referral_notifications import send_referral_notifications

router = Router(name="customer_referral")


@router.message(menu_text_filter("menu.invite_friend"))
async def handle_referral_menu(
    message: Message,
    bot: Bot,
    uow: UnitOfWork,
    referral_service: ReferralService,
    lang: str,
) -> None:
    if message.from_user is None:
        return
    user = await uow.users.get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer(t(lang, "common.start_first"))
        return
    me = await bot.get_me()
    stats = await referral_service.build_customer_stats(user, bot_username=me.username or "")
    pending_days = stats.pending_bonus_days
    await message.answer(
        referral_service.format_customer_home(stats, lang=lang),
        reply_markup=referral_inline_keyboard(has_pending=pending_days > 0),
    )


@router.callback_query(F.data == REF_LINK)
async def handle_referral_link(
    callback: CallbackQuery,
    bot: Bot,
    uow: UnitOfWork,
    referral_service: ReferralService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    user = await uow.users.get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    me = await bot.get_me()
    stats = await referral_service.build_customer_stats(user, bot_username=me.username or "")
    await callback.message.answer(referral_service.format_link_message(stats, lang=lang))
    await callback.answer()


@router.callback_query(F.data == REF_STATS)
async def handle_referral_stats(
    callback: CallbackQuery,
    bot: Bot,
    uow: UnitOfWork,
    referral_service: ReferralService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    user = await uow.users.get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    me = await bot.get_me()
    stats = await referral_service.build_customer_stats(user, bot_username=me.username or "")
    await callback.message.answer(referral_service.format_stats_message(stats, lang=lang))
    await callback.answer()


@router.callback_query(F.data == REF_BONUSES)
async def handle_referral_bonuses(
    callback: CallbackQuery,
    uow: UnitOfWork,
    referral_service: ReferralService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    user = await uow.users.get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    rewards = await referral_service.list_customer_rewards(user.id)
    text = referral_service.format_customer_bonuses(rewards, lang=lang)
    pending = sum(r.reward_days for r in rewards if r.status == "pending")
    await callback.message.answer(
        text,
        reply_markup=referral_inline_keyboard(has_pending=pending > 0),
    )
    await callback.answer()


@router.callback_query(F.data == REF_APPLY)
async def handle_referral_apply(
    callback: CallbackQuery,
    bot: Bot,
    uow: UnitOfWork,
    referral_service: ReferralService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    user = await uow.users.get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    try:
        outcome = await referral_service.apply_pending_for_user(user.id)
    except ReferralError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await send_referral_notifications(bot, outcome.notifications)
    await callback.message.answer(outcome.message, reply_markup=customer_main_keyboard(lang))
    if outcome.applied_count:
        await callback.answer(t(lang, "referral.apply_done_cb"))
    else:
        await callback.answer(t(lang, "referral.apply_no_vpn"))


@router.callback_query(F.data == REF_HOME)
async def handle_referral_home(callback: CallbackQuery, lang: str) -> None:
    if callback.message is not None:
        await callback.message.answer(t(lang, "common.main_menu"), reply_markup=customer_main_keyboard(lang))
    await callback.answer()
