from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import VpnPanelValidationError, VpnProvisioningError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.manual_key_flow_service import ManualKeyFlowService
from app.application.services.manual_provisioning_service import ManualProvisioningService
from app.application.services.plan_service import PlanService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.domain.enums import AdminActionType
from app.infrastructure.db.models.user import User
from app.infrastructure.db.uow import UnitOfWork
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_manual_key import (
    MK_CANCEL,
    MK_CONFIRM_CANCEL,
    MK_CONFIRM_CREATE,
    MK_DONE_ADMIN,
    MK_EXTEND_NO,
    MK_EXTEND_YES,
    MK_ISSUING_PREFIX,
    MK_MODE_EXISTING,
    MK_MODE_STANDALONE,
    MK_NAME_EDIT,
    MK_NAME_OK,
    MK_PARAMS_CUSTOM,
    MK_PARAMS_TARIFF,
    MK_PLAN_PREFIX,
    MK_SEND_CUSTOMER,
    MK_SKIP_COMMENT,
    MK_USER_PREFIX,
    account_name_keyboard,
    after_create_keyboard,
    confirmation_keyboard,
    extend_choice_keyboard,
    issuing_mode_keyboard,
    mode_keyboard,
    params_mode_keyboard,
    skip_comment_keyboard,
    tariff_keyboard,
    user_search_results_keyboard,
)
from app.presentation.services.customer_vpn_delivery import send_qr_codes_for_links
from app.presentation.states.admin_manual_key import AdminManualKeyStates

logger = logging.getLogger(__name__)

router = Router(name="admin_manual_key")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


async def _callback_ack(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as exc:
        logger.debug("callback answer skipped: %s", str(exc)[:200])


@router.message(F.text == "➕ Создать ключ")
async def handle_create_key_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "➕ <b>Создание VPN-ключа</b>\n\nДля кого создать ключ?",
        reply_markup=mode_keyboard(),
    )


@router.callback_query(F.data == MK_CANCEL)
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await _callback_ack(callback)
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("Отменено.", reply_markup=admin_main_keyboard())


@router.callback_query(F.data == MK_MODE_EXISTING)
async def handle_mode_existing(callback: CallbackQuery, state: FSMContext) -> None:
    await _callback_ack(callback)
    await state.update_data(mode="existing")
    await state.set_state(AdminManualKeyStates.waiting_user_search)
    if callback.message is not None:
        await callback.message.answer(
            "🔍 Введите для поиска:\n"
            "• Telegram ID\n"
            "• @username\n"
            "• имя\n\n"
            "<i>/cancel для отмены</i>",
        )


@router.callback_query(F.data == MK_MODE_STANDALONE)
async def handle_mode_standalone(callback: CallbackQuery, state: FSMContext) -> None:
    await _callback_ack(callback)
    await state.update_data(mode="standalone", extend_existing=False)
    await state.set_state(AdminManualKeyStates.waiting_account_name)
    if callback.message is not None:
        await callback.message.answer(
            "🔑 Введите имя VPN-аккаунта:\n"
            "(латиница, цифры, _ и -, без пробелов)\n\n"
            "<i>/cancel для отмены</i>",
        )


@router.message(StateFilter(AdminManualKeyStates.waiting_user_search), F.text, ~F.text.startswith("/"))
async def handle_user_search(
    message: Message,
    state: FSMContext,
    flow_service: ManualKeyFlowService,
) -> None:
    if message.text is None:
        return
    users = await flow_service.search_users(message.text.strip())
    if not users:
        await message.answer("Пользователи не найдены. Попробуйте другой запрос.")
        return
    await message.answer(
        f"Найдено: {len(users)}. Выберите клиента:",
        reply_markup=user_search_results_keyboard(users),
    )


@router.callback_query(F.data.startswith(MK_USER_PREFIX))
async def handle_user_selected(
    callback: CallbackQuery,
    state: FSMContext,
    uow: UnitOfWork,
    flow_service: ManualKeyFlowService,
) -> None:
    if callback.data is None or callback.message is None:
        await _callback_ack(callback)
        return
    user_id = int(callback.data.removeprefix(MK_USER_PREFIX))
    user = await uow.users.get_by_id(user_id)
    if user is None:
        await _callback_ack(callback, "Клиент не найден.", show_alert=True)
        return

    await _callback_ack(callback)

    display_name = _user_display_name(user)
    await state.update_data(
        user_id=user.id,
        target_telegram_id=user.telegram_id,
        target_display_name=display_name,
    )
    await state.set_state(None)

    if await flow_service.user_has_active_account(user.id):
        await callback.message.answer(
            f"У клиента <b>{display_name}</b> уже есть активный VPN.\nЧто сделать?",
            reply_markup=extend_choice_keyboard(),
        )
    else:
        await state.update_data(extend_existing=False)
        await _prompt_account_name(callback.message, state, flow_service, user)


@router.callback_query(F.data.in_({MK_EXTEND_YES, MK_EXTEND_NO}))
async def handle_extend_choice(
    callback: CallbackQuery,
    state: FSMContext,
    uow: UnitOfWork,
    flow_service: ManualKeyFlowService,
) -> None:
    if callback.data is None or callback.message is None:
        await _callback_ack(callback)
        return
    extend = callback.data == MK_EXTEND_YES
    await state.update_data(extend_existing=extend)
    data = await state.get_data()
    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        await _callback_ack(callback, "Сессия истекла.", show_alert=True)
        return
    user = await uow.users.get_by_id(user_id)
    if user is None:
        await _callback_ack(callback, "Клиент не найден.", show_alert=True)
        return
    await _callback_ack(callback)
    await _prompt_account_name(callback.message, state, flow_service, user, extend=extend)


@router.callback_query(F.data == MK_NAME_OK)
async def handle_name_ok(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await _callback_ack(callback)
        return
    await _callback_ack(callback)
    data = await state.get_data()
    suggested = data.get("suggested_name")
    if suggested and not data.get("account_name"):
        await state.update_data(account_name=suggested)
    await _ask_params_mode(callback.message)


@router.callback_query(F.data == MK_NAME_EDIT)
async def handle_name_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await _callback_ack(callback)
    await state.set_state(AdminManualKeyStates.waiting_account_name)
    if callback.message is not None:
        await callback.message.answer(
            "✏️ Введите имя VPN-аккаунта:\n<i>/cancel для отмены</i>",
        )


@router.message(StateFilter(AdminManualKeyStates.waiting_account_name), F.text, ~F.text.startswith("/"))
async def handle_account_name_input(
    message: Message,
    state: FSMContext,
    flow_service: ManualKeyFlowService,
    manual_provisioning_service: ManualProvisioningService,
) -> None:
    if message.text is None:
        return
    try:
        account_name = flow_service.validate_account_name(message.text)
    except VpnPanelValidationError as exc:
        await message.answer(exc.message)
        return

    data = await state.get_data()
    profile_dict = data.get("profile")
    if profile_dict is not None:
        profile = flow_service.resolve_profile_from_fsm_data(data)
        if profile is not None and not data.get("extend_existing"):
            conflicts = await manual_provisioning_service.check_name_conflicts(
                account_name,
                profile.issuing_mode,
            )
            if conflicts:
                await message.answer(
                    f"Имя <code>{account_name}</code> уже занято в: {', '.join(conflicts)}.\n"
                    "Введите другое имя.",
                )
                return

    await state.update_data(account_name=account_name)
    await state.set_state(None)

    if profile_dict is None:
        await _ask_params_mode(message)
        return

    await _show_confirmation(message, state, flow_service)


@router.callback_query(F.data.in_({MK_PARAMS_TARIFF, MK_PARAMS_CUSTOM}))
async def handle_params_mode(callback: CallbackQuery, state: FSMContext, plan_service: PlanService) -> None:
    if callback.data is None or callback.message is None:
        await _callback_ack(callback)
        return
    if callback.data == MK_PARAMS_TARIFF:
        await _callback_ack(callback)
        plans = await plan_service.list_active_plans()
        if not plans:
            await callback.message.answer("Нет активных тарифов.")
            return
        await callback.message.answer("📦 Выберите тариф:", reply_markup=tariff_keyboard(plans))
    else:
        await _callback_ack(callback)
        await state.set_state(AdminManualKeyStates.waiting_custom_duration)
        await callback.message.answer(
            "📅 Введите срок в днях (целое число > 0):\n<i>/cancel для отмены</i>",
        )


@router.callback_query(F.data.startswith(MK_PLAN_PREFIX))
async def handle_plan_selected(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    flow_service: ManualKeyFlowService,
    manual_provisioning_service: ManualProvisioningService,
) -> None:
    if callback.data is None or callback.message is None:
        await _callback_ack(callback)
        return
    plan_id = int(callback.data.removeprefix(MK_PLAN_PREFIX))
    await _callback_ack(callback)
    plan = await plan_service.get_plan(plan_id)
    if plan is None:
        await callback.message.answer("⚠️ Тариф не найден.")
        return
    profile = flow_service.profile_from_plan(plan)
    await state.update_data(profile=flow_service.profile_to_dict(profile))
    ok = await _validate_name_conflicts(state, manual_provisioning_service, flow_service)
    if not ok:
        await state.set_state(AdminManualKeyStates.waiting_account_name)
        await callback.message.answer(
            "⚠️ Имя VPN занято на панели. Введите другое имя:\n<i>/cancel для отмены</i>",
        )
        return
    await _show_confirmation(callback.message, state, flow_service)


@router.message(StateFilter(AdminManualKeyStates.waiting_custom_duration), F.text, ~F.text.startswith("/"))
async def handle_custom_duration(message: Message, state: FSMContext, flow_service: ManualKeyFlowService) -> None:
    if message.text is None:
        return
    try:
        days = flow_service.validate_custom_duration(message.text)
    except (ValueError, Exception):
        await message.answer("Некорректное значение. Введите целое число > 0.")
        return
    await state.update_data(custom_duration_days=days)
    await state.set_state(AdminManualKeyStates.waiting_custom_traffic)
    await message.answer(
        "📶 Введите лимит трафика в ГБ (0 = безлимит):\n<i>/cancel для отмены</i>",
    )


@router.message(StateFilter(AdminManualKeyStates.waiting_custom_traffic), F.text, ~F.text.startswith("/"))
async def handle_custom_traffic(message: Message, state: FSMContext, flow_service: ManualKeyFlowService) -> None:
    if message.text is None:
        return
    try:
        traffic = flow_service.validate_custom_int(message.text, field="Трафик")
    except (ValueError, Exception) as exc:
        await message.answer(str(exc) if str(exc) else "Некорректное значение.")
        return
    await state.update_data(custom_traffic_gb=traffic)
    await state.set_state(AdminManualKeyStates.waiting_custom_ip)
    await message.answer(
        "📱 Введите лимит устройств (0 = безлимит):\n<i>/cancel для отмены</i>",
    )


@router.message(StateFilter(AdminManualKeyStates.waiting_custom_ip), F.text, ~F.text.startswith("/"))
async def handle_custom_ip(message: Message, state: FSMContext, flow_service: ManualKeyFlowService) -> None:
    if message.text is None:
        return
    try:
        ip_limit = flow_service.validate_custom_int(message.text, field="Лимит устройств")
    except (ValueError, Exception) as exc:
        await message.answer(str(exc) if str(exc) else "Некорректное значение.")
        return
    await state.update_data(custom_ip_limit=ip_limit)
    await state.set_state(None)
    await message.answer("🖥 Выберите режим выдачи:", reply_markup=issuing_mode_keyboard())


@router.callback_query(F.data.startswith(MK_ISSUING_PREFIX))
async def handle_custom_issuing(callback: CallbackQuery, state: FSMContext, flow_service: ManualKeyFlowService) -> None:
    if callback.data is None or callback.message is None:
        await _callback_ack(callback)
        return
    try:
        issuing_mode = flow_service.validate_issuing_mode(callback.data.removeprefix(MK_ISSUING_PREFIX))
    except ValueError as exc:
        await _callback_ack(callback, str(exc), show_alert=True)
        return
    await _callback_ack(callback)
    data = await state.get_data()
    duration = data.get("custom_duration_days")
    traffic = data.get("custom_traffic_gb")
    ip_limit = data.get("custom_ip_limit")
    if duration is None or traffic is None or ip_limit is None:
        await callback.message.answer(
            "⚠️ Не все параметры заданы. Введите срок, трафик и лимит устройств.",
        )
        await state.set_state(AdminManualKeyStates.waiting_custom_duration)
        await callback.message.answer(
            "📅 Введите срок в днях (целое число > 0):\n<i>/cancel для отмены</i>",
        )
        return
    profile = flow_service.profile_from_dict(
        {
            "name": "Ручные параметры",
            "duration_days": duration,
            "traffic_limit_gb": traffic,
            "ip_limit": ip_limit,
            "issuing_mode": issuing_mode,
            "plan_id": None,
        },
    )
    profile_dict = flow_service.profile_to_dict(profile)
    await state.update_data(profile=profile_dict, issuing_mode=issuing_mode)
    await state.set_state(AdminManualKeyStates.waiting_custom_comment)
    await callback.message.answer(
        "💬 Комментарий администратора (необязательно):\n"
        "Отправьте текст или нажмите «Пропустить».\n<i>/cancel для отмены</i>",
        reply_markup=skip_comment_keyboard(),
    )


@router.message(StateFilter(AdminManualKeyStates.waiting_custom_comment), F.text, ~F.text.startswith("/"))
async def handle_custom_comment(
    message: Message,
    state: FSMContext,
    flow_service: ManualKeyFlowService,
    manual_provisioning_service: ManualProvisioningService,
) -> None:
    if message.text is None:
        return
    await state.update_data(admin_comment=message.text.strip())
    await state.set_state(None)
    ok = await _validate_name_conflicts(state, manual_provisioning_service, flow_service)
    if not ok:
        await state.set_state(AdminManualKeyStates.waiting_account_name)
        await message.answer(
            "⚠️ Имя VPN занято на панели. Введите другое имя:\n<i>/cancel для отмены</i>",
        )
        return
    await _show_confirmation(message, state, flow_service)


@router.callback_query(F.data == MK_SKIP_COMMENT)
async def handle_skip_comment(
    callback: CallbackQuery,
    state: FSMContext,
    flow_service: ManualKeyFlowService,
    manual_provisioning_service: ManualProvisioningService,
) -> None:
    if callback.message is None:
        await _callback_ack(callback)
        return
    await _callback_ack(callback)
    await state.update_data(admin_comment=None)
    await state.set_state(None)
    ok = await _validate_name_conflicts(state, manual_provisioning_service, flow_service)
    if not ok:
        await state.set_state(AdminManualKeyStates.waiting_account_name)
        await callback.message.answer(
            "⚠️ Имя VPN занято на панели. Введите другое имя:\n<i>/cancel для отмены</i>",
        )
        return
    await _show_confirmation(callback.message, state, flow_service)


@router.callback_query(F.data == MK_CONFIRM_CANCEL)
async def handle_confirm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await handle_cancel(callback, state)


@router.callback_query(F.data == MK_CONFIRM_CREATE)
async def handle_confirm_create(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    flow_service: ManualKeyFlowService,
    manual_provisioning_service: ManualProvisioningService,
    provisioning_notification_service: ProvisioningNotificationService,
) -> None:
    if callback.message is None or callback.from_user is None:
        await _callback_ack(callback)
        return

    await _callback_ack(callback, "⏳ Создаю ключ…")

    data = await state.get_data()
    if data.get("mode") == "standalone":
        user_id = await manual_provisioning_service.resolve_standalone_user_id()
        await state.update_data(user_id=user_id)

    try:
        request = flow_service.build_request(await state.get_data())
        result = await manual_provisioning_service.create_manual_vpn(
            request,
            admin_telegram_id=callback.from_user.id,
        )
    except VpnProvisioningError as exc:
        await callback.message.answer(f"⚠️ {exc.message}")
        return
    except Exception as exc:
        logger.exception("Manual VPN creation failed")
        await callback.message.answer(f"⚠️ Ошибка: {str(exc)[:200]}")
        return

    text = flow_service.format_success_admin(result)
    for_existing = data.get("mode") == "existing" and bool(data.get("target_telegram_id"))
    await callback.message.answer(
        text,
        reply_markup=after_create_keyboard(for_existing_user=for_existing),
    )

    if result.subscription_links:
        await send_qr_codes_for_links(
            bot,
            telegram_id=callback.from_user.id,
            links=result.subscription_links,
            notification_service=provisioning_notification_service,
        )

    await state.update_data(
        result_links=result.subscription_links,
        result_target_telegram_id=data.get("target_telegram_id"),
        result_mode=data.get("mode"),
        result_customer_message=flow_service.customer_delivery_message(result),
    )


@router.callback_query(F.data == MK_SEND_CUSTOMER)
async def handle_send_customer(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    provisioning_notification_service: ProvisioningNotificationService,
    admin_log_service: AdminLogService,
) -> None:
    if callback.message is None or callback.from_user is None:
        await _callback_ack(callback)
        return
    data = await state.get_data()
    telegram_id = data.get("result_target_telegram_id")
    links = data.get("result_links") or {}
    customer_message = data.get("result_customer_message")
    if not isinstance(telegram_id, int) or telegram_id <= 0 or not links:
        await _callback_ack(callback, "Нет данных для отправки.", show_alert=True)
        return
    await _callback_ack(callback)
    try:
        if customer_message:
            await bot.send_message(telegram_id, customer_message)
        await send_qr_codes_for_links(
            bot,
            telegram_id=telegram_id,
            links=links,
            notification_service=provisioning_notification_service,
        )
        await admin_log_service.log(
            admin_telegram_id=callback.from_user.id,
            action=AdminActionType.MANUAL_VPN_SENT_TO_CUSTOMER,
            details={"target_telegram_id": telegram_id, "panels": list(links.keys())},
        )
        await callback.message.answer("📩 Ключ отправлен клиенту.")
    except Exception as exc:
        logger.warning("Failed to send manual VPN to customer", extra={"error": str(exc)[:300]})
        await callback.message.answer("⚠️ Не удалось отправить клиенту.")
        return


@router.callback_query(F.data == MK_DONE_ADMIN)
async def handle_done_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await _callback_ack(callback)
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("Админ-панель", reply_markup=admin_main_keyboard())


async def _prompt_account_name(
    message: Message,
    state: FSMContext,
    flow_service: ManualKeyFlowService,
    user: User,
    *,
    extend: bool = False,
) -> None:
    if extend:
        account = await flow_service.get_renewal_account(user.id)
        if account is not None and account.vpn_account_name:
            await state.update_data(suggested_name=account.vpn_account_name)
            await message.answer(
                f"🔑 Имя существующего аккаунта: <code>{account.vpn_account_name}</code>",
                reply_markup=account_name_keyboard(),
            )
            return

    suggested = flow_service.default_account_name(user)
    if suggested:
        await state.update_data(suggested_name=suggested)
        await message.answer(
            f"🔑 Предлагаемое имя: <code>{suggested}</code>",
            reply_markup=account_name_keyboard(),
        )
    else:
        await state.set_state(AdminManualKeyStates.waiting_account_name)
        await message.answer(
            "У клиента нет username. Введите имя VPN-аккаунта вручную:\n<i>/cancel для отмены</i>",
        )


async def _ask_params_mode(message: Message) -> None:
    await message.answer("Как задать параметры?", reply_markup=params_mode_keyboard())


async def _validate_name_conflicts(
    state: FSMContext,
    manual_provisioning_service: ManualProvisioningService,
    flow_service: ManualKeyFlowService,
) -> bool:
    data = await state.get_data()
    if data.get("extend_existing"):
        return True
    account_name = data.get("account_name") or data.get("suggested_name")
    profile_dict = flow_service.profile_dict_from_fsm_data(data)
    if not account_name or not profile_dict:
        return True
    profile = flow_service.profile_from_dict(profile_dict)
    conflicts = await manual_provisioning_service.check_name_conflicts(account_name, profile.issuing_mode)
    return not conflicts


async def _show_confirmation(
    message: Message,
    state: FSMContext,
    flow_service: ManualKeyFlowService,
) -> bool:
    data = await state.get_data()
    if not data.get("account_name") and data.get("suggested_name"):
        await state.update_data(account_name=data["suggested_name"])
        data = await state.get_data()

    profile_dict = flow_service.profile_dict_from_fsm_data(data)
    if profile_dict is None:
        await message.answer(
            "⚠️ Не все параметры заданы. Выберите тариф или введите параметры вручную.",
        )
        await _ask_params_mode(message)
        return False

    await state.update_data(profile=profile_dict)
    profile = flow_service.profile_from_dict(profile_dict)
    user_id = data.get("user_id")
    renewal = None
    if isinstance(user_id, int) and data.get("mode") == "existing":
        renewal = await flow_service.get_renewal_account(user_id)

    preview_expiry = flow_service.preview_expiry(
        duration_days=profile.duration_days,
        extend_existing=bool(data.get("extend_existing")),
        user_id=user_id if isinstance(user_id, int) else None,
        renewal_account=renewal if data.get("extend_existing") else None,
    )
    await state.update_data(preview_expiry=preview_expiry.isoformat())
    text = flow_service.format_confirmation({**data, "profile": profile_dict, "preview_expiry": preview_expiry})
    await message.answer(text, reply_markup=confirmation_keyboard())
    return True


def _user_display_name(user: User) -> str:
    parts = [user.first_name, user.last_name]
    name = " ".join(part for part in parts if part)
    if user.username:
        return f"{name} (@{user.username})" if name else f"@{user.username}"
    return name or f"ID {user.telegram_id}"
