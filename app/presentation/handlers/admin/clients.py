from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.dto.admin_customer import AdminCustomerActionOutcome
from app.application.exceptions import PaymentRequestNotFoundError
from app.application.services.admin_customer_service import AdminCustomerService
from app.application.services.plan_service import PlanService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_clients import (
    ACL_ACT_CLEAR,
    ACL_ACT_DELETE,
    ACL_ACT_DISABLE,
    ACL_ACT_ENABLE,
    ACL_ACT_EXTEND,
    ACL_ACT_IP,
    ACL_ACT_LINK,
    ACL_ACT_QR,
    ACL_ADMIN,
    ACL_CANCEL_CONFIRM,
    ACL_CONFIRM_DELETE,
    ACL_CONFIRM_DISABLE,
    ACL_DASH,
    ACL_FILTER_PREFIX,
    ACL_OPEN_PREFIX,
    ACL_PAGE_PREFIX,
    ACL_SEARCH,
    ACL_SEARCH_RESULT_PREFIX,
    client_card_keyboard,
    client_list_keyboard,
    clients_dashboard_keyboard,
    confirm_delete_keyboard,
    confirm_disable_keyboard,
    search_results_keyboard,
)
from app.presentation.services.customer_vpn_delivery import send_qr_codes_for_links
from app.presentation.states.admin_client import (
    AdminClientExtendStates,
    AdminClientIpLimitStates,
    AdminClientSearchStates,
)

logger = logging.getLogger(__name__)

router = Router(name="admin_clients")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.message(F.text == "👥 Клиенты")
async def handle_clients_menu(
    message: Message,
    admin_customer_service: AdminCustomerService,
) -> None:
    stats = await admin_customer_service.get_stats()
    text = admin_customer_service.format_dashboard(stats)
    await message.answer(text, reply_markup=clients_dashboard_keyboard())


@router.callback_query(F.data == ACL_DASH)
async def handle_clients_dashboard(
    callback: CallbackQuery,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    stats = await admin_customer_service.get_stats()
    text = admin_customer_service.format_dashboard(stats)
    await callback.message.edit_text(text, reply_markup=clients_dashboard_keyboard())
    await callback.answer()


@router.callback_query(F.data == ACL_ADMIN)
async def handle_clients_back_admin(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer("Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith(ACL_FILTER_PREFIX))
async def handle_clients_filter(
    callback: CallbackQuery,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    parsed = _parse_filter_page(callback.data, ACL_FILTER_PREFIX)
    if parsed is None:
        await callback.answer("Некорректный фильтр.", show_alert=True)
        return
    status_filter, page = parsed
    items, total = await admin_customer_service.list_clients(status_filter, page=page)
    text = admin_customer_service.format_client_list(status_filter, items, page=page, total=total)
    await callback.message.edit_text(
        text,
        reply_markup=client_list_keyboard(status_filter, items, page=page, total=total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(ACL_PAGE_PREFIX))
async def handle_clients_page(
    callback: CallbackQuery,
    admin_customer_service: AdminCustomerService,
) -> None:
    await handle_clients_filter(callback, admin_customer_service)


@router.callback_query(F.data.startswith(ACL_OPEN_PREFIX) | F.data.startswith(ACL_SEARCH_RESULT_PREFIX))
async def handle_open_client(
    callback: CallbackQuery,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    user_id = _parse_user_id(callback.data, (ACL_OPEN_PREFIX, ACL_SEARCH_RESULT_PREFIX))
    if user_id is None:
        await callback.answer("Некорректный клиент.", show_alert=True)
        return
    try:
        card = await admin_customer_service.get_client_card(user_id)
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    text = admin_customer_service.format_client_card(card)
    await callback.message.edit_text(
        text,
        reply_markup=client_card_keyboard(
            user_id,
            is_deleted=card.is_deleted,
            has_vpn=card.vpn_account_id is not None,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == ACL_SEARCH)
async def handle_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminClientSearchStates.waiting_query)
    if callback.message is not None:
        await callback.message.answer(
            "🔎 Введите запрос: Telegram ID, username, имя или VPN-аккаунт.\n"
            "<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.message(StateFilter(AdminClientSearchStates.waiting_query), F.text)
async def handle_search_query(
    message: Message,
    state: FSMContext,
    admin_customer_service: AdminCustomerService,
) -> None:
    if message.text and message.text.startswith("/"):
        return
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите непустой запрос.")
        return
    results = await admin_customer_service.search_clients(query)
    await state.clear()
    if not results:
        await message.answer("Ничего не найдено.", reply_markup=clients_dashboard_keyboard())
        return
    await message.answer(
        f"🔎 Найдено: {len(results)}",
        reply_markup=search_results_keyboard(results),
    )


@router.message(Command("cancel"), StateFilter(AdminClientSearchStates.waiting_query))
async def handle_search_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Поиск отменён.", reply_markup=admin_main_keyboard())


@router.callback_query(F.data.startswith(ACL_ACT_LINK))
async def handle_send_link(
    callback: CallbackQuery,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
) -> None:
    await _run_action(callback, bot, admin_customer_service, ACL_ACT_LINK, admin_customer_service.send_links_to_customer)


@router.callback_query(F.data.startswith(ACL_ACT_QR))
async def handle_send_qr(
    callback: CallbackQuery,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
    provisioning_notification_service: ProvisioningNotificationService,
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    user_id = _parse_user_id(callback.data, (ACL_ACT_QR,))
    if user_id is None:
        await callback.answer("Некорректный клиент.", show_alert=True)
        return
    try:
        outcome = await admin_customer_service.send_qr_to_customer(
            user_id,
            admin_telegram_id=callback.from_user.id,
        )
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await _deliver_outcome(bot, outcome, provisioning_notification_service)
    if callback.message is not None:
        await callback.message.answer(outcome.admin_message)
    await callback.answer()


@router.callback_query(F.data.startswith(ACL_ACT_DISABLE))
async def handle_disable_prompt(callback: CallbackQuery) -> None:
    await _prompt_confirm(callback, ACL_ACT_DISABLE, "Вы точно хотите отключить клиента?", confirm_disable_keyboard)


@router.callback_query(F.data.startswith(ACL_CONFIRM_DISABLE))
async def handle_disable_confirm(
    callback: CallbackQuery,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
) -> None:
    await _run_action(callback, bot, admin_customer_service, ACL_CONFIRM_DISABLE, admin_customer_service.disable_client)


@router.callback_query(F.data.startswith(ACL_ACT_ENABLE))
async def handle_enable(
    callback: CallbackQuery,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
) -> None:
    await _run_action(callback, bot, admin_customer_service, ACL_ACT_ENABLE, admin_customer_service.enable_client)


@router.callback_query(F.data.startswith(ACL_ACT_DELETE))
async def handle_delete_prompt(callback: CallbackQuery) -> None:
    await _prompt_confirm(
        callback,
        ACL_ACT_DELETE,
        "Вы точно хотите удалить VPN клиента? Старый срок больше не будет использоваться при новой покупке.",
        confirm_delete_keyboard,
    )


@router.callback_query(F.data.startswith(ACL_CONFIRM_DELETE))
async def handle_delete_confirm(
    callback: CallbackQuery,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
) -> None:
    await _run_action(callback, bot, admin_customer_service, ACL_CONFIRM_DELETE, admin_customer_service.delete_client)


@router.callback_query(F.data.startswith(ACL_CANCEL_CONFIRM))
async def handle_confirm_cancel(
    callback: CallbackQuery,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    user_id = _parse_user_id(callback.data, (ACL_CANCEL_CONFIRM,))
    if user_id is None:
        await callback.answer()
        return
    try:
        card = await admin_customer_service.get_client_card(user_id)
    except PaymentRequestNotFoundError:
        await callback.answer()
        return
    await callback.message.edit_text(
        admin_customer_service.format_client_card(card),
        reply_markup=client_card_keyboard(
            user_id,
            is_deleted=card.is_deleted,
            has_vpn=card.vpn_account_id is not None,
        ),
    )
    await callback.answer("Отменено.")


@router.callback_query(F.data.startswith(ACL_ACT_CLEAR))
async def handle_clear_ips(
    callback: CallbackQuery,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
) -> None:
    await _run_action(callback, bot, admin_customer_service, ACL_ACT_CLEAR, admin_customer_service.clear_ips)


@router.callback_query(F.data.startswith(ACL_ACT_EXTEND))
async def handle_extend_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
        return
    user_id = _parse_user_id(callback.data, (ACL_ACT_EXTEND,))
    if user_id is None:
        await callback.answer("Некорректный клиент.", show_alert=True)
        return
    await state.update_data(user_id=user_id)
    await state.set_state(AdminClientExtendStates.waiting_days)
    if callback.message is not None:
        await callback.message.answer("Введите количество дней для продления (> 0):\n<i>/cancel для отмены</i>")
    await callback.answer()


@router.message(StateFilter(AdminClientExtendStates.waiting_days), F.text)
async def handle_extend_days(
    message: Message,
    state: FSMContext,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text.startswith("/"):
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число дней.")
        return
    data = await state.get_data()
    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        await state.clear()
        await message.answer("Сессия истекла.")
        return
    await state.clear()
    try:
        outcome = await admin_customer_service.manual_extend(
            user_id,
            days=days,
            admin_telegram_id=message.from_user.id,
        )
    except PaymentRequestNotFoundError as exc:
        await message.answer(exc.message)
        return
    await _deliver_outcome(bot, outcome)
    await message.answer(outcome.admin_message, reply_markup=admin_main_keyboard())


@router.callback_query(F.data.startswith(ACL_ACT_IP))
async def handle_ip_limit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
        return
    user_id = _parse_user_id(callback.data, (ACL_ACT_IP,))
    if user_id is None:
        await callback.answer("Некорректный клиент.", show_alert=True)
        return
    await state.update_data(user_id=user_id)
    await state.set_state(AdminClientIpLimitStates.waiting_value)
    if callback.message is not None:
        await callback.message.answer(
            "Введите новый IP limit (целое число, 0 = безлимит):\n<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.message(StateFilter(AdminClientIpLimitStates.waiting_value), F.text)
async def handle_ip_limit_value(
    message: Message,
    state: FSMContext,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
    plan_service: PlanService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text.startswith("/"):
        return
    try:
        new_limit = plan_service.parse_ip_limit(message.text.strip())
    except Exception:
        await message.answer("Некорректное значение. Введите целое число >= 0.")
        return
    data = await state.get_data()
    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        await state.clear()
        await message.answer("Сессия истекла.")
        return
    await state.clear()
    try:
        outcome = await admin_customer_service.change_ip_limit(
            user_id,
            new_limit=new_limit,
            admin_telegram_id=message.from_user.id,
        )
    except PaymentRequestNotFoundError as exc:
        await message.answer(exc.message)
        return
    await message.answer(outcome.admin_message, reply_markup=admin_main_keyboard())


@router.message(
    Command("cancel"),
    StateFilter(AdminClientExtendStates.waiting_days, AdminClientIpLimitStates.waiting_value),
)
async def handle_fsm_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_main_keyboard())


async def _run_action(
    callback: CallbackQuery,
    bot: Bot,
    service: AdminCustomerService,
    prefix: str,
    action,
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    user_id = _parse_user_id(callback.data, (prefix,))
    if user_id is None:
        await callback.answer("Некорректный клиент.", show_alert=True)
        return
    try:
        outcome = await action(user_id, admin_telegram_id=callback.from_user.id)
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await _deliver_outcome(bot, outcome)
    if callback.message is not None:
        await callback.message.answer(outcome.admin_message)
    await callback.answer()


async def _deliver_outcome(
    bot: Bot,
    outcome: AdminCustomerActionOutcome,
    notification_service: ProvisioningNotificationService | None = None,
) -> None:
    if outcome.customer_telegram_id is None:
        return
    if outcome.customer_message:
        try:
            await bot.send_message(outcome.customer_telegram_id, outcome.customer_message)
        except Exception as exc:
            logger.warning("Failed to notify customer", extra={"error": str(exc)[:300]})
    if outcome.qr_deliveries and notification_service is not None:
        links = {item.panel: item.link for item in outcome.qr_deliveries if item.link}
        try:
            await send_qr_codes_for_links(
                bot,
                telegram_id=outcome.customer_telegram_id,
                links=links,
                notification_service=notification_service,
            )
        except Exception as exc:
            logger.warning("Failed to send admin QR", extra={"error": str(exc)[:300]})


async def _prompt_confirm(
    callback: CallbackQuery,
    prefix: str,
    text: str,
    keyboard_factory,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    user_id = _parse_user_id(callback.data, (prefix,))
    if user_id is None:
        await callback.answer("Некорректный клиент.", show_alert=True)
        return
    await callback.message.answer(text, reply_markup=keyboard_factory(user_id))
    await callback.answer()


def _parse_user_id(data: str, prefixes: tuple[str, ...]) -> int | None:
    for prefix in prefixes:
        if data.startswith(prefix):
            suffix = data.removeprefix(prefix)
            try:
                return int(suffix)
            except ValueError:
                return None
    return None


def _parse_filter_page(data: str, prefix: str) -> tuple[str, int] | None:
    suffix = data.removeprefix(prefix)
    parts = suffix.split(":", maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return parts[0], int(parts[1])
    except ValueError:
        return None
