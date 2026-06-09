from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.payment_request import PaymentRequestInfo

CB_LIST = "preq:list"
CB_OPEN_PREFIX = "preq:open:"
CB_APPROVE_PREFIX = "preq:approve:"
CB_REJECT_PREFIX = "preq:reject:"


def empty_requests_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Назад в админ-панель", callback_data="tariff:back_admin")],
        ],
    )


def pending_requests_keyboard(requests: list[PaymentRequestInfo]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"👁 #{item.id} · {item.user_full_name}", callback_data=f"{CB_OPEN_PREFIX}{item.id}")]
        for item in requests
    ]
    rows.append([InlineKeyboardButton(text="🏠 Назад в админ-панель", callback_data="tariff:back_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def new_payment_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👁 Открыть заявку",
                    callback_data=f"{CB_OPEN_PREFIX}{request_id}",
                ),
            ],
        ],
    )


def request_details_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{CB_APPROVE_PREFIX}{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"{CB_REJECT_PREFIX}{request_id}"),
            ],
            [InlineKeyboardButton(text="🏠 Назад к заявкам", callback_data=CB_LIST)],
        ],
    )
