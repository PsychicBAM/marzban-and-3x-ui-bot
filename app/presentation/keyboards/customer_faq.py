from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.presentation.i18n import t

FAQ_MENU = "faq:menu"
FAQ_BACK_MENU = "faq:back_menu"
FAQ_BACK_LIST = "faq:back_list"

FAQ_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("faq:q1", "faq.q.vpn_connect", "faq.a.vpn_connect"),
    ("faq:q2", "faq.q.refresh_sub", "faq.a.refresh_sub"),
    ("faq:q3", "faq.q.device_limit", "faq.a.device_limit"),
    ("faq:q4", "faq.q.qr_code", "faq.a.qr_code"),
    ("faq:q5", "faq.q.renew", "faq.a.renew"),
    ("faq:q6", "faq.q.referral", "faq.a.referral"),
    ("faq:q7", "faq.q.promo_off", "faq.a.promo_off"),
)

_ANSWER_BY_CALLBACK = {item[0]: item[2] for item in FAQ_ITEMS}


def faq_menu_keyboard(lang: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(lang, question_key), callback_data=callback)]
        for callback, question_key, _ in FAQ_ITEMS
    ]
    rows.append([InlineKeyboardButton(text=t(lang, "faq.btn.back_menu"), callback_data=FAQ_BACK_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def faq_answer_keyboard(lang: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "faq.btn.back_list"), callback_data=FAQ_BACK_LIST)],
        ],
    )


def faq_answer_key(callback_data: str) -> str | None:
    return _ANSWER_BY_CALLBACK.get(callback_data)
