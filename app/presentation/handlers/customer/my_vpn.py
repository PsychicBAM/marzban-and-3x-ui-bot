from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from app.application.services.customer_vpn_service import CustomerVpnService, NO_VPN_TEXT
from app.application.services.plan_service import PlanService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.my_vpn import (
    MYVPN_HOME,
    MYVPN_LINKS_PREFIX,
    MYVPN_QR_PREFIX,
    MYVPN_RENEW_PREFIX,
    my_vpn_keyboard,
)
from app.presentation.handlers.customer.renewal import start_renewal_flow
from app.presentation.services.customer_vpn_delivery import send_qr_codes_for_links

router = Router(name="customer_my_vpn")


@router.message(F.text == "📊 Мой VPN")
async def handle_my_vpn(message: Message, customer_vpn_service: CustomerVpnService) -> None:
    if message.from_user is None:
        return

    overview = await customer_vpn_service.build_overview(message.from_user.id)
    if overview is None:
        await message.answer(NO_VPN_TEXT, reply_markup=customer_main_keyboard())
        return

    text = customer_vpn_service.format_overview_message(overview)
    await message.answer(text, reply_markup=my_vpn_keyboard(overview.account_id))


@router.callback_query(F.data.startswith(MYVPN_LINKS_PREFIX))
async def handle_my_vpn_links(
    callback: CallbackQuery,
    customer_vpn_service: CustomerVpnService,
) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    account_id = _parse_account_id(callback.data, MYVPN_LINKS_PREFIX)
    if account_id is None:
        await callback.answer("Некорректный запрос.", show_alert=True)
        return

    account = await customer_vpn_service.get_account_for_user(callback.from_user.id, account_id)
    if account is None:
        await callback.answer("VPN не найден.", show_alert=True)
        return

    if callback.message is None:
        await callback.answer()
        return

    links = await customer_vpn_service.resolve_subscription_links(account)
    text = customer_vpn_service.format_links_message(links)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith(MYVPN_QR_PREFIX))
async def handle_my_vpn_qr(
    callback: CallbackQuery,
    bot: Bot,
    customer_vpn_service: CustomerVpnService,
    provisioning_notification_service: ProvisioningNotificationService,
) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    account_id = _parse_account_id(callback.data, MYVPN_QR_PREFIX)
    if account_id is None:
        await callback.answer("Некорректный запрос.", show_alert=True)
        return

    account = await customer_vpn_service.get_account_for_user(callback.from_user.id, account_id)
    if account is None:
        await callback.answer("VPN не найден.", show_alert=True)
        return

    if callback.message is None:
        await callback.answer()
        return

    links = await customer_vpn_service.resolve_subscription_links(account)
    if not links:
        await callback.message.answer("Не удалось получить ссылку. Свяжитесь с поддержкой.")
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
) -> None:
    if callback.data is None:
        await callback.answer()
        return

    account_id = _parse_account_id(callback.data, MYVPN_RENEW_PREFIX)
    if account_id is None:
        await callback.answer("Некорректный запрос.", show_alert=True)
        return

    await start_renewal_flow(
        callback,
        vpn_account_id=account_id,
        plan_service=plan_service,
        customer_vpn_service=customer_vpn_service,
    )


@router.callback_query(F.data == MYVPN_HOME)
async def handle_my_vpn_home(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer("🏠 Главное меню", reply_markup=customer_main_keyboard())
    await callback.answer()


def _parse_account_id(data: str, prefix: str) -> int | None:
    suffix = data.removeprefix(prefix)
    try:
        account_id = int(suffix)
    except ValueError:
        return None
    return account_id if account_id > 0 else None
