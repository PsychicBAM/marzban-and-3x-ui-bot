from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
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
    ACL_PAGE_INFO_PREFIX,
    ACL_PAGE_PREFIX,
    ACL_SEARCH,
    ACL_SEARCH_PAGE_PREFIX,
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

from app.infrastructure.db.repositories.admin_customer_repo import (
    STATUS_ACTIVE,
    STATUS_DELETED,
    STATUS_DISABLED,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
)

VALID_STATUS_FILTERS = frozenset(
    {
        STATUS_ACTIVE,
        STATUS_EXPIRED,
        STATUS_DISABLED,
        STATUS_DELETED,
        STATUS_EXPIRING_SOON,
    },
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
    state: FSMContext,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await state.clear()
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
    parsed = _parse_list_callback(callback.data, ACL_FILTER_PREFIX)
    if parsed is None:
        await callback.answer("Некорректный фильтр.", show_alert=True)
        return
    status_filter, page = parsed
    await _render_client_list(
        callback,
        admin_customer_service,
        status_filter=status_filter,
        page=page,
    )


@router.callback_query(F.data.startswith(ACL_PAGE_PREFIX))
async def handle_clients_page(
    callback: CallbackQuery,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    parsed = _parse_list_callback(callback.data, ACL_PAGE_PREFIX)
    if parsed is None:
        await callback.answer("Некорректная страница.", show_alert=True)
        return
    status_filter, page = parsed
    await _render_client_list(
        callback,
        admin_customer_service,
        status_filter=status_filter,
        page=page,
    )


@router.callback_query(F.data.startswith(ACL_PAGE_INFO_PREFIX))
async def handle_page_indicator(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith(ACL_SEARCH_PAGE_PREFIX))
async def handle_search_page(
    callback: CallbackQuery,
    state: FSMContext,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    page = _parse_scoped_page(callback.data, ACL_SEARCH_PAGE_PREFIX)
    if page is None:
        await callback.answer("Некорректная страница.", show_alert=True)
        return
    data = await state.get_data()
    query = data.get("search_query")
    if not isinstance(query, str) or not query.strip():
        await callback.answer("Поиск истёк. Введите запрос снова.", show_alert=True)
        return
    items, total, page = await admin_customer_service.search_clients(query, page=page)
    text = admin_customer_service.format_search_results(query, items, page=page, total=total)
    await callback.message.edit_text(
        text,
        reply_markup=search_results_keyboard(items, page=page, total=total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(ACL_OPEN_PREFIX) | F.data.startswith(ACL_SEARCH_RESULT_PREFIX))
async def handle_open_client(
    callback: CallbackQuery,
    state: FSMContext,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    if callback.data.startswith(ACL_OPEN_PREFIX):
        parsed = _parse_open_client(callback.data)
        if parsed is None:
            await callback.answer("Некорректная подписка.", show_alert=True)
            return
        vpn_account_id, list_filter, list_page, search_page = parsed
    else:
        parsed = _parse_search_open(callback.data)
        if parsed is None:
            await callback.answer("Некорректная подписка.", show_alert=True)
            return
        vpn_account_id, search_page = parsed
        list_filter, list_page = None, None

    await state.update_data(
        acl_list_filter=list_filter,
        acl_list_page=list_page,
        acl_search_page=search_page,
    )

    try:
        card = await admin_customer_service.get_client_card(vpn_account_id)
    except PaymentRequestNotFoundError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    text = admin_customer_service.format_client_card(card)
    await callback.message.edit_text(
        text,
        reply_markup=client_card_keyboard(
            vpn_account_id,
            is_deleted=card.is_deleted,
            list_filter=list_filter,
            list_page=list_page,
            search_page=search_page,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == ACL_SEARCH)
async def handle_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminClientSearchStates.waiting_query)
    if callback.message is not None:
        await callback.message.answer(
            "🔎 Введите запрос: Telegram ID, username, имя, подписка, VPN-аккаунт, "
            "Marzban или 3x-ui email.\n"
            "<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.message(StateFilter(AdminClientSearchStates.waiting_query), F.text, ~F.text.startswith("/"))
async def handle_search_query(
    message: Message,
    state: FSMContext,
    admin_customer_service: AdminCustomerService,
) -> None:
    if not message.text:
        return
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите непустой запрос.")
        return
    items, total, page = await admin_customer_service.search_clients(query, page=0)
    if total == 0:
        await state.clear()
        await message.answer("Ничего не найдено.", reply_markup=clients_dashboard_keyboard())
        return
    await state.update_data(search_query=query)
    await state.set_state(AdminClientSearchStates.viewing_results)
    text = admin_customer_service.format_search_results(query, items, page=page, total=total)
    await message.answer(
        text,
        reply_markup=search_results_keyboard(items, page=page, total=total),
    )


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
    vpn_account_id = _parse_vpn_account_id(callback.data, (ACL_ACT_QR,))
    if vpn_account_id is None:
        await callback.answer("Некорректная подписка.", show_alert=True)
        return
    try:
        outcome = await admin_customer_service.send_qr_to_customer(
            vpn_account_id,
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
    await _prompt_confirm(callback, ACL_ACT_DISABLE, "Вы точно хотите отключить подписку?", confirm_disable_keyboard)


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
        "Вы точно хотите удалить эту VPN-подписку? Старый срок больше не будет использоваться при новой покупке.",
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
    state: FSMContext,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    vpn_account_id = _parse_vpn_account_id(callback.data, (ACL_CANCEL_CONFIRM,))
    if vpn_account_id is None:
        await callback.answer()
        return
    try:
        card = await admin_customer_service.get_client_card(vpn_account_id)
    except PaymentRequestNotFoundError:
        await callback.answer()
        return
    data = await state.get_data()
    list_filter = data.get("acl_list_filter")
    list_page = data.get("acl_list_page")
    search_page = data.get("acl_search_page")
    if list_filter is not None and not isinstance(list_filter, str):
        list_filter = None
    if list_page is not None and not isinstance(list_page, int):
        list_page = None
    if search_page is not None and not isinstance(search_page, int):
        search_page = None
    await callback.message.edit_text(
        admin_customer_service.format_client_card(card),
        reply_markup=client_card_keyboard(
            vpn_account_id,
            is_deleted=card.is_deleted,
            list_filter=list_filter,
            list_page=list_page,
            search_page=search_page,
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
    vpn_account_id = _parse_vpn_account_id(callback.data, (ACL_ACT_EXTEND,))
    if vpn_account_id is None:
        await callback.answer("Некорректная подписка.", show_alert=True)
        return
    await state.update_data(vpn_account_id=vpn_account_id)
    await state.set_state(AdminClientExtendStates.waiting_days)
    if callback.message is not None:
        await callback.message.answer("Введите количество дней для продления (> 0):\n<i>/cancel для отмены</i>")
    await callback.answer()


@router.message(StateFilter(AdminClientExtendStates.waiting_days), F.text, ~F.text.startswith("/"))
async def handle_extend_days(
    message: Message,
    state: FSMContext,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число дней.")
        return
    data = await state.get_data()
    vpn_account_id = data.get("vpn_account_id")
    if not isinstance(vpn_account_id, int):
        await state.clear()
        await message.answer("Сессия истекла.")
        return
    await state.clear()
    try:
        outcome = await admin_customer_service.manual_extend(
            vpn_account_id,
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
    vpn_account_id = _parse_vpn_account_id(callback.data, (ACL_ACT_IP,))
    if vpn_account_id is None:
        await callback.answer("Некорректная подписка.", show_alert=True)
        return
    await state.update_data(vpn_account_id=vpn_account_id)
    await state.set_state(AdminClientIpLimitStates.waiting_value)
    if callback.message is not None:
        await callback.message.answer(
            "Введите новый IP limit (целое число, 0 = безлимит):\n<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.message(StateFilter(AdminClientIpLimitStates.waiting_value), F.text, ~F.text.startswith("/"))
async def handle_ip_limit_value(
    message: Message,
    state: FSMContext,
    bot: Bot,
    admin_customer_service: AdminCustomerService,
    plan_service: PlanService,
) -> None:
    if message.from_user is None or message.text is None:
        return
    try:
        new_limit = plan_service.parse_ip_limit(message.text.strip())
    except Exception:
        await message.answer("Некорректное значение. Введите целое число >= 0.")
        return
    data = await state.get_data()
    vpn_account_id = data.get("vpn_account_id")
    if not isinstance(vpn_account_id, int):
        await state.clear()
        await message.answer("Сессия истекла.")
        return
    await state.clear()
    try:
        outcome = await admin_customer_service.change_ip_limit(
            vpn_account_id,
            new_limit=new_limit,
            admin_telegram_id=message.from_user.id,
        )
    except PaymentRequestNotFoundError as exc:
        await message.answer(exc.message)
        return
    await message.answer(outcome.admin_message, reply_markup=admin_main_keyboard())


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
    vpn_account_id = _parse_vpn_account_id(callback.data, (prefix,))
    if vpn_account_id is None:
        await callback.answer("Некорректная подписка.", show_alert=True)
        return
    try:
        outcome = await action(vpn_account_id, admin_telegram_id=callback.from_user.id)
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
    vpn_account_id = _parse_vpn_account_id(callback.data, (prefix,))
    if vpn_account_id is None:
        await callback.answer("Некорректная подписка.", show_alert=True)
        return
    await callback.message.answer(text, reply_markup=keyboard_factory(vpn_account_id))
    await callback.answer()


async def _render_client_list(
    callback: CallbackQuery,
    admin_customer_service: AdminCustomerService,
    *,
    status_filter: str,
    page: int,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    items, total, page = await admin_customer_service.list_clients(status_filter, page=page)
    text = admin_customer_service.format_client_list(status_filter, items, page=page, total=total)
    await callback.message.edit_text(
        text,
        reply_markup=client_list_keyboard(status_filter, items, page=page, total=total),
    )
    await callback.answer()


def _parse_list_callback(data: str, prefix: str) -> tuple[str, int] | None:
    parsed = _parse_filter_page(data, prefix)
    if parsed is None:
        return None
    status_filter, page = parsed
    if status_filter not in VALID_STATUS_FILTERS:
        return None
    return status_filter, page


def _parse_open_client(data: str) -> tuple[int, str | None, int | None, int | None] | None:
    if not data.startswith(ACL_OPEN_PREFIX):
        return None
    suffix = data.removeprefix(ACL_OPEN_PREFIX)
    parts = suffix.split(":")
    if not parts or not parts[0].isdigit():
        return None
    vpn_account_id = int(parts[0])
    if len(parts) >= 3:
        status_filter = parts[1]
        if status_filter not in VALID_STATUS_FILTERS:
            return None
        try:
            list_page = int(parts[2])
        except ValueError:
            return None
        return vpn_account_id, status_filter, list_page, None
    return vpn_account_id, None, None, None


def _parse_search_open(data: str) -> tuple[int, int] | None:
    if not data.startswith(ACL_SEARCH_RESULT_PREFIX):
        return None
    suffix = data.removeprefix(ACL_SEARCH_RESULT_PREFIX)
    parts = suffix.split(":")
    if not parts or not parts[0].isdigit():
        return None
    vpn_account_id = int(parts[0])
    if len(parts) >= 2:
        try:
            return vpn_account_id, int(parts[1])
        except ValueError:
            return None
    return vpn_account_id, 0


def _parse_vpn_account_id(data: str, prefixes: tuple[str, ...]) -> int | None:
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
    parts = suffix.rsplit(":", maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return parts[0], int(parts[1])
    except ValueError:
        return None


def _parse_scoped_page(data: str, prefix: str) -> int | None:
    suffix = data.removeprefix(prefix)
    parts = suffix.rsplit(":", maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None
