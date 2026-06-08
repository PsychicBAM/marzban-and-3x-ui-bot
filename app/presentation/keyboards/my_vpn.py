from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

MYVPN_LINKS_PREFIX = "myvpn:links:"
MYVPN_QR_PREFIX = "myvpn:qr:"
MYVPN_RENEW_PREFIX = "myvpn:renew:"
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
