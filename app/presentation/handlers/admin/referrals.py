from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import ReferralError
from app.application.services.referral_service import ReferralService
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_referral import (
    RF_BACK_ADMIN,
    RF_CANCEL,
    RF_EDIT_MILESTONE,
    RF_EDIT_MILESTONE_REWARD,
    RF_EDIT_MIN_AMOUNT,
    RF_EDIT_REWARD,
    RF_HISTORY,
    RF_HOME,
    RF_REWARDS,
    RF_SETTINGS,
    RF_STATS,
    RF_TOGGLE_AUTO,
    RF_TOGGLE_ENABLED,
    RF_TOGGLE_FIRST,
    RF_TOGGLE_ZERO,
    RF_TOP,
    referral_admin_home_keyboard,
    referral_back_home_keyboard,
    referral_settings_cancel_keyboard,
    referral_settings_keyboard,
)
from app.presentation.states.admin_referral import AdminReferralSettingsStates
from app.presentation.utils.telegram import safe_edit_message_text

router = Router(name="admin_referrals")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.message(F.text == "🎁 Рефералы")
async def handle_referral_admin_menu(message: Message) -> None:
    await message.answer(
        "🎁 Реферальная программа\n\nУправление настройками и статистикой.",
        reply_markup=referral_admin_home_keyboard(),
    )


@router.callback_query(F.data == RF_BACK_ADMIN)
async def handle_referral_back_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == RF_CANCEL)
async def handle_referral_cancel(callback: CallbackQuery, state: FSMContext, referral_service: ReferralService) -> None:
    await state.clear()
    await _show_settings(callback, referral_service)
    await callback.answer("Отменено.")


@router.callback_query(F.data == RF_HOME)
async def handle_referral_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await safe_edit_message_text(
            callback.message,
            "🎁 Реферальная программа\n\nУправление настройками и статистикой.",
            reply_markup=referral_admin_home_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == RF_SETTINGS)
async def handle_referral_settings(callback: CallbackQuery, state: FSMContext, referral_service: ReferralService) -> None:
    await state.clear()
    await _show_settings(callback, referral_service)
    await callback.answer()


@router.callback_query(F.data == RF_STATS)
async def handle_referral_stats(callback: CallbackQuery, referral_service: ReferralService) -> None:
    text = await referral_service.get_admin_stats_text()
    if callback.message is not None:
        await safe_edit_message_text(callback.message, text, reply_markup=referral_back_home_keyboard())
    await callback.answer()


@router.callback_query(F.data == RF_TOP)
async def handle_referral_top(callback: CallbackQuery, referral_service: ReferralService) -> None:
    text = await referral_service.format_admin_top()
    if callback.message is not None:
        await safe_edit_message_text(callback.message, text, reply_markup=referral_back_home_keyboard())
    await callback.answer()


@router.callback_query(F.data == RF_HISTORY)
async def handle_referral_history(callback: CallbackQuery, referral_service: ReferralService) -> None:
    text = await referral_service.format_admin_history()
    if callback.message is not None:
        await safe_edit_message_text(callback.message, text, reply_markup=referral_back_home_keyboard())
    await callback.answer()


@router.callback_query(F.data == RF_REWARDS)
async def handle_referral_rewards(callback: CallbackQuery, referral_service: ReferralService) -> None:
    text = await referral_service.format_admin_rewards()
    if callback.message is not None:
        await safe_edit_message_text(callback.message, text, reply_markup=referral_back_home_keyboard())
    await callback.answer()


@router.callback_query(F.data == RF_TOGGLE_ENABLED)
async def handle_toggle_enabled(callback: CallbackQuery, referral_service: ReferralService) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    await referral_service.toggle_enabled(admin_telegram_id=callback.from_user.id)
    await _show_settings(callback, referral_service)
    await callback.answer("Обновлено.")


@router.callback_query(F.data == RF_TOGGLE_FIRST)
async def handle_toggle_first(callback: CallbackQuery, referral_service: ReferralService) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    await referral_service.toggle_count_first_only(admin_telegram_id=callback.from_user.id)
    await _show_settings(callback, referral_service)
    await callback.answer("Обновлено.")


@router.callback_query(F.data == RF_TOGGLE_ZERO)
async def handle_toggle_zero(callback: CallbackQuery, referral_service: ReferralService) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    await referral_service.toggle_allow_zero(admin_telegram_id=callback.from_user.id)
    await _show_settings(callback, referral_service)
    await callback.answer("Обновлено.")


@router.callback_query(F.data == RF_TOGGLE_AUTO)
async def handle_toggle_auto(callback: CallbackQuery, referral_service: ReferralService) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    await referral_service.toggle_auto_apply(admin_telegram_id=callback.from_user.id)
    await _show_settings(callback, referral_service)
    await callback.answer("Обновлено.")


@router.callback_query(F.data == RF_EDIT_REWARD)
async def handle_edit_reward_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminReferralSettingsStates.waiting_reward_days)
    if callback.message is not None:
        await callback.message.answer(
            "🎁 Введите бонус за 1 оплаченного друга (дней, ≥ 0):\n/cancel для отмены",
            reply_markup=referral_settings_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == RF_EDIT_MILESTONE)
async def handle_edit_milestone_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminReferralSettingsStates.waiting_milestone_count)
    if callback.message is not None:
        await callback.message.answer(
            "🏆 Введите цель (число оплаченных друзей, ≥ 1):\n/cancel для отмены",
            reply_markup=referral_settings_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == RF_EDIT_MILESTONE_REWARD)
async def handle_edit_milestone_reward_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminReferralSettingsStates.waiting_milestone_reward_days)
    if callback.message is not None:
        await callback.message.answer(
            "🎉 Введите бонус за достижение цели (дней, ≥ 0):\n/cancel для отмены",
            reply_markup=referral_settings_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == RF_EDIT_MIN_AMOUNT)
async def handle_edit_min_amount_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminReferralSettingsStates.waiting_min_amount)
    if callback.message is not None:
        await callback.message.answer(
            "💰 Введите минимальную сумму покупки (₽, ≥ 0):\n/cancel для отмены",
            reply_markup=referral_settings_cancel_keyboard(),
        )
    await callback.answer()


@router.message(StateFilter(AdminReferralSettingsStates.waiting_reward_days), F.text, ~F.text.startswith("/"))
async def save_reward_days(
    message: Message,
    state: FSMContext,
    referral_service: ReferralService,
) -> None:
    if message.from_user is None:
        return
    try:
        value = referral_service.parse_int(message.text or "")
        info = await referral_service.set_reward_days_per_referral(
            value,
            admin_telegram_id=message.from_user.id,
        )
    except ReferralError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer(
        referral_service.format_admin_settings(info),
        reply_markup=referral_settings_keyboard(),
    )


@router.message(StateFilter(AdminReferralSettingsStates.waiting_milestone_count), F.text, ~F.text.startswith("/"))
async def save_milestone_count(
    message: Message,
    state: FSMContext,
    referral_service: ReferralService,
) -> None:
    if message.from_user is None:
        return
    try:
        value = referral_service.parse_int(message.text or "")
        info = await referral_service.set_milestone_count(value, admin_telegram_id=message.from_user.id)
    except ReferralError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer(
        referral_service.format_admin_settings(info),
        reply_markup=referral_settings_keyboard(),
    )


@router.message(StateFilter(AdminReferralSettingsStates.waiting_milestone_reward_days), F.text, ~F.text.startswith("/"))
async def save_milestone_reward_days(
    message: Message,
    state: FSMContext,
    referral_service: ReferralService,
) -> None:
    if message.from_user is None:
        return
    try:
        value = referral_service.parse_int(message.text or "")
        info = await referral_service.set_milestone_reward_days(
            value,
            admin_telegram_id=message.from_user.id,
        )
    except ReferralError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer(
        referral_service.format_admin_settings(info),
        reply_markup=referral_settings_keyboard(),
    )


@router.message(StateFilter(AdminReferralSettingsStates.waiting_min_amount), F.text, ~F.text.startswith("/"))
async def save_min_amount(
    message: Message,
    state: FSMContext,
    referral_service: ReferralService,
) -> None:
    if message.from_user is None:
        return
    try:
        value = referral_service.parse_decimal(message.text or "")
        info = await referral_service.set_min_purchase_amount(
            value,
            admin_telegram_id=message.from_user.id,
        )
    except ReferralError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer(
        referral_service.format_admin_settings(info),
        reply_markup=referral_settings_keyboard(),
    )


async def _show_settings(target: CallbackQuery | Message, referral_service: ReferralService) -> None:
    info = await referral_service.get_settings()
    text = referral_service.format_admin_settings(info)
    keyboard = referral_settings_keyboard()
    if isinstance(target, CallbackQuery):
        if target.message is not None:
            await safe_edit_message_text(target.message, text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)
