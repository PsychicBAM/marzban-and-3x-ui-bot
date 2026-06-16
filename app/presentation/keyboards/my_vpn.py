from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.customer_vpn import CustomerVpnListItem

MYVPN_LINKS_PREFIX = "myvpn:links:"
MYVPN_QR_PREFIX = "myvpn:qr:"
MYVPN_RENEW_PREFIX = "myvpn:renew:"
MYVPN_SELECT_PREFIX = "myvpn:select:"
MYVPN_HOME = "myvpn:home"
MYVPN_HISTORY = "myvpn:history"


from app.presentation.i18n import t


def my_vpn_keyboard(account_id: int, lang: str | None = None) -> InlineKeyboardMarkup:
    code = lang or "ru"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(code, "myvpn.get_link"),
                    callback_data=f"{MYVPN_LINKS_PREFIX}{account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(code, "myvpn.get_qr"),
                    callback_data=f"{MYVPN_QR_PREFIX}{account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(code, "menu.renew_vpn"),
                    callback_data=f"{MYVPN_RENEW_PREFIX}{account_id}",
                )
            ],
            [InlineKeyboardButton(text=t(code, "menu.history"), callback_data=MYVPN_HISTORY)],
            [InlineKeyboardButton(text=t(code, "common.main_menu_short"), callback_data=MYVPN_HOME)],
        ],
    )


def my_vpn_list_keyboard(items: list[CustomerVpnListItem], lang: str | None = None) -> InlineKeyboardMarkup:
    code = lang or "ru"
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
    rows.append([InlineKeyboardButton(text=t(code, "menu.history"), callback_data=MYVPN_HISTORY)])
    rows.append([InlineKeyboardButton(text=t(code, "common.main_menu_short"), callback_data=MYVPN_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
