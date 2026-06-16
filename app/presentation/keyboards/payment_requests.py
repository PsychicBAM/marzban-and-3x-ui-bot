from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.dto.payment_request import PaymentRequestInfo
from app.domain.enums import PaymentRequestStatus

CB_LIST = "preq:list"
CB_PARTIAL_LIST = "preq:partial_list"
CB_OPEN_PREFIX = "preq:open:"
CB_APPROVE_PREFIX = "preq:approve:"
CB_REJECT_PREFIX = "preq:reject:"
CB_RETRY_PREFIX = "preq:retry:"


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
    rows.append([InlineKeyboardButton(text="⚠️ Частичные выдачи", callback_data=CB_PARTIAL_LIST)])
    rows.append([InlineKeyboardButton(text="🏠 Назад в админ-панель", callback_data="tariff:back_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def partial_requests_keyboard(requests: list[PaymentRequestInfo]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"👁 #{item.id} · {item.user_full_name}", callback_data=f"{CB_OPEN_PREFIX}{item.id}")]
        for item in requests
    ]
    rows.append([InlineKeyboardButton(text="📥 К заявкам на проверке", callback_data=CB_LIST)])
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


def request_details_keyboard(request_id: int, *, status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status == PaymentRequestStatus.PENDING.value:
        rows.append(
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{CB_APPROVE_PREFIX}{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"{CB_REJECT_PREFIX}{request_id}"),
            ],
        )
    elif status == PaymentRequestStatus.PROVISIONING_PARTIAL.value:
        rows.append(
            [InlineKeyboardButton(text="🔁 Повторить выдачу VPN", callback_data=f"{CB_RETRY_PREFIX}{request_id}")],
        )
    back_target = CB_PARTIAL_LIST if status == PaymentRequestStatus.PROVISIONING_PARTIAL.value else CB_LIST
    rows.append([InlineKeyboardButton(text="🏠 Назад к заявкам", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
