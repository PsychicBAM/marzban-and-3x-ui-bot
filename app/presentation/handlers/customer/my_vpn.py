from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from app.application.services.customer_history_service import CustomerHistoryService
from app.application.services.customer_vpn_service import CustomerVpnService
from app.application.services.plan_service import PlanService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.customer_history import history_keyboard
from app.presentation.keyboards.my_vpn import (
    MYVPN_HISTORY,
    MYVPN_HOME,
    MYVPN_LINKS_PREFIX,
    MYVPN_QR_PREFIX,
    MYVPN_RENEW_PREFIX,
    MYVPN_SELECT_PREFIX,
    my_vpn_keyboard,
    my_vpn_list_keyboard,
)
from app.application.services.user_service import UserService
from app.presentation.handlers.customer.renewal import start_renewal_flow
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE

router = Router(name="customer_my_vpn")


@router.message(menu_text_filter("menu.my_vpn"))
async def handle_my_vpn(message: Message, customer_vpn_service: CustomerVpnService, lang: str) -> None:
    if message.from_user is None:
        return

    items = await customer_vpn_service.list_subscriptions(message.from_user.id, lang=lang)
    if not items:
        await message.answer(t(lang, "myvpn.no_vpn"), reply_markup=customer_main_keyboard(lang))
        return

    if len(items) == 1:
        overview = await customer_vpn_service.build_overview(
            message.from_user.id,
            account_id=items[0].account_id,
            lang=lang,
        )
        if overview is None:
            await message.answer(t(lang, "myvpn.no_vpn"), reply_markup=customer_main_keyboard(lang))
            return
        text = customer_vpn_service.format_overview_message(overview, lang=lang)
        await message.answer(text, reply_markup=my_vpn_keyboard(overview.account_id, lang))
        return

    text = customer_vpn_service.format_subscription_list_message(items, lang=lang)
    await message.answer(text, reply_markup=my_vpn_list_keyboard(items, lang))


@router.callback_query(F.data.startswith(MYVPN_SELECT_PREFIX))
async def handle_my_vpn_select(
    callback: CallbackQuery,
    customer_vpn_service: CustomerVpnService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return

    account_id = _parse_account_id(callback.data, MYVPN_SELECT_PREFIX)
    if account_id is None:
        await callback.answer(t(lang, "common.invalid_request"), show_alert=True)
        return

    overview = await customer_vpn_service.build_overview(
        callback.from_user.id,
        account_id=account_id,
        lang=lang,
    )
    if overview is None:
        await callback.answer(t(lang, "common.vpn_not_found"), show_alert=True)
        return

    text = customer_vpn_service.format_overview_message(overview, lang=lang)
    await callback.message.answer(text, reply_markup=my_vpn_keyboard(overview.account_id, lang))
    await callback.answer()


@router.callback_query(F.data.startswith(MYVPN_LINKS_PREFIX))
async def handle_my_vpn_links(
    callback: CallbackQuery,
    customer_vpn_service: CustomerVpnService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    account_id = _parse_account_id(callback.data, MYVPN_LINKS_PREFIX)
    if account_id is None:
        await callback.answer(t(lang, "common.invalid_request"), show_alert=True)
        return

    account = await customer_vpn_service.get_account_for_user(callback.from_user.id, account_id)
    if account is None:
        await callback.answer(t(lang, "common.vpn_not_found"), show_alert=True)
        return

    if callback.message is None:
        await callback.answer()
        return

    links = await customer_vpn_service.resolve_subscription_links(account)
    text = customer_vpn_service.format_links_message(links, lang=lang)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith(MYVPN_QR_PREFIX))
async def handle_my_vpn_qr(
    callback: CallbackQuery,
    bot: Bot,
    customer_vpn_service: CustomerVpnService,
    provisioning_notification_service: ProvisioningNotificationService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    account_id = _parse_account_id(callback.data, MYVPN_QR_PREFIX)
    if account_id is None:
        await callback.answer(t(lang, "common.invalid_request"), show_alert=True)
        return

    account = await customer_vpn_service.get_account_for_user(callback.from_user.id, account_id)
    if account is None:
        await callback.answer(t(lang, "common.vpn_not_found"), show_alert=True)
        return

    if callback.message is None:
        await callback.answer()
        return

    links = await customer_vpn_service.resolve_subscription_links(account)
    if not links:
        await callback.message.answer(t(lang, "myvpn.links_error"))
        await callback.answer()
        return

    await send_qr_codes_for_links(
        bot,
        telegram_id=callback.from_user.id,
        links=links,
        notification_service=provisioning_notification_service,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(MYVPN_RENEW_PREFIX))
async def handle_my_vpn_renew(
    callback: CallbackQuery,
    plan_service: PlanService,
    customer_vpn_service: CustomerVpnService,
    lang: str,
) -> None:
    if callback.data is None:
        await callback.answer()
        return

    account_id = _parse_account_id(callback.data, MYVPN_RENEW_PREFIX)
    if account_id is None:
        await callback.answer(t(lang, "common.invalid_request"), show_alert=True)
        return

    await start_renewal_flow(
        callback,
        vpn_account_id=account_id,
        plan_service=plan_service,
        customer_vpn_service=customer_vpn_service,
        lang=lang,
    )


@router.callback_query(F.data == MYVPN_HISTORY)
async def handle_my_vpn_history(
    callback: CallbackQuery,
    user_service: UserService,
    customer_history_service: CustomerHistoryService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    text, page, pages = await customer_history_service.get_page(user.id, lang=lang, page=0)
    await callback.message.answer(
        text,
        reply_markup=history_keyboard(lang, page=page, pages=pages),
        parse_mode=CUSTOMER_PARSE_MODE,
    )
    await callback.answer()


@router.callback_query(F.data == MYVPN_HOME)
async def handle_my_vpn_home(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer(t(lang, "common.main_menu_short"), reply_markup=customer_main_keyboard(lang))
    await callback.answer()


def _parse_account_id(data: str, prefix: str) -> int | None:
    suffix = data.removeprefix(prefix)
    try:
        account_id = int(suffix)
    except ValueError:
        return None
    return account_id if account_id > 0 else None
