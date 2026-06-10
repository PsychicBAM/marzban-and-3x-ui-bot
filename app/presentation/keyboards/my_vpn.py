from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.customer_vpn import CustomerVpnListItem

MYVPN_LINKS_PREFIX = "myvpn:links:"
MYVPN_QR_PREFIX = "myvpn:qr:"
MYVPN_RENEW_PREFIX = "myvpn:renew:"
MYVPN_SELECT_PREFIX = "myvpn:select:"
MYVPN_HOME = "myvpn:home"


def my_vpn_keyboard(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Получить ссылку",
                    callback_data=f"{MYVPN_LINKS_PREFIX}{account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📷 Получить QR-code",
                    callback_data=f"{MYVPN_QR_PREFIX}{account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Продлить VPN",
                    callback_data=f"{MYVPN_RENEW_PREFIX}{account_id}",
                )
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data=MYVPN_HOME)],
        ],
    )


def my_vpn_list_keyboard(items: list[CustomerVpnListItem]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        suffix = " ⭐" if item.is_primary else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{item.title}{suffix}",
                    callback_data=f"{MYVPN_SELECT_PREFIX}{item.account_id}",
                ),
            ],
        )
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data=MYVPN_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
