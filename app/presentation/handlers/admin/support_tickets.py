from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.services.admin_customer_service import AdminCustomerService
from app.application.services.support_ticket_service import SupportTicketService
from app.domain.enums import SupportTicketStatus
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_support_tickets import (
    AST_BACK,
    AST_CLIENT_PREFIX,
    AST_CLOSE_PREFIX,
    AST_LIST_PREFIX,
    AST_MENU,
    AST_PAGE_INFO,
    AST_REOPEN_PREFIX,
    AST_REPLY_PREFIX,
    AST_SEARCH,
    AST_TICKET_PREFIX,
    admin_support_list_keyboard,
    admin_support_menu_keyboard,
    admin_support_ticket_keyboard,
)
from app.presentation.states.support_ticket import AdminSupportStates
from app.presentation.utils.telegram import safe_edit_message_text

logger = logging.getLogger(__name__)

router = Router(name="admin_support_tickets")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.message(F.text == "🆘 Обращения")
async def handle_admin_support_menu(message: Message) -> None:
    await message.answer(
        "🆘 <b>Обращения</b>\n\nВыберите раздел:",
        reply_markup=admin_support_menu_keyboard(),
    )


@router.callback_query(F.data == AST_MENU)
async def handle_admin_support_menu_callback(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await safe_edit_message_text(
        callback.message,
        "🆘 <b>Обращения</b>\n\nВыберите раздел:",
        reply_markup=admin_support_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == AST_BACK)
async def handle_admin_support_back(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer("🔐 Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith(AST_LIST_PREFIX))
async def handle_admin_support_list(
    callback: CallbackQuery,
    support_ticket_service: SupportTicketService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    payload = callback.data.removeprefix(AST_LIST_PREFIX)
    try:
        status, page_str = payload.split(":", 1)
        page = int(page_str)
    except ValueError:
        await callback.answer()
        return
    tickets, page, pages = await support_ticket_service.list_admin_tickets(status, page=page)
    title = _status_title(status)
    lines = [f"<b>{title}</b>", f"Стр. {page + 1}/{pages}", ""]
    if not tickets:
        lines.append("Список пуст.")
    else:
        for ticket in tickets:
            user = ticket.user
            name = support_ticket_service._user_display(user)
            lines.append(
                f"#{ticket.id} · {name} · {support_ticket_service.topic_label(ticket.topic, 'ru')} · "
                f"{support_ticket_service.status_label(ticket.status, 'ru')}"
            )
    await safe_edit_message_text(
        callback.message,
        "\n".join(lines),
        reply_markup=admin_support_list_keyboard(status, tickets, page=page, pages=pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(AST_TICKET_PREFIX))
async def handle_admin_ticket_detail(
    callback: CallbackQuery,
    support_ticket_service: SupportTicketService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        ticket_id = int(callback.data.removeprefix(AST_TICKET_PREFIX))
    except ValueError:
        await callback.answer()
        return
    ticket = await support_ticket_service.get_ticket_for_admin(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return
    messages = await support_ticket_service.get_ticket_messages(ticket_id, limit=10)
    text = support_ticket_service.format_ticket_detail(ticket, messages, admin_view=True)
    user = ticket.user
    await safe_edit_message_text(
        callback.message,
        text,
        reply_markup=admin_support_ticket_keyboard(
            ticket_id,
            user_telegram_id=user.telegram_id if user else None,
            status=ticket.status,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(AST_REPLY_PREFIX))
async def handle_admin_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
        return
    try:
        ticket_id = int(callback.data.removeprefix(AST_REPLY_PREFIX))
    except ValueError:
        await callback.answer()
        return
    await state.set_state(AdminSupportStates.waiting_reply)
    await state.update_data(ticket_id=ticket_id)
    if callback.message:
        await callback.message.answer("Введите ответ клиенту. /cancel — отмена")
    await callback.answer()


@router.message(StateFilter(AdminSupportStates.waiting_reply))
async def handle_admin_reply_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    support_ticket_service: SupportTicketService,
) -> None:
    if message.from_user is None or not message.text:
        await message.answer("Отправьте текстовый ответ.")
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await state.clear()
        return
    ticket = await support_ticket_service.get_ticket_for_admin(int(ticket_id))
    if ticket is None:
        await state.clear()
        return
    await support_ticket_service.add_admin_reply(
        ticket,
        admin_telegram_id=message.from_user.id,
        text=message.text.strip(),
    )
    await state.clear()
    user = ticket.user
    if user:
        try:
            from app.presentation.i18n import t, normalize_lang

            lang = normalize_lang(user.language_code)
            await bot.send_message(
                user.telegram_id,
                t(lang, "support.admin_replied_notify", ticket_id=ticket.id),
            )
        except Exception as exc:
            logger.warning("Failed to notify customer about support reply", extra={"error": str(exc)[:200]})
    await message.answer("✅ Ответ отправлен.", reply_markup=admin_main_keyboard())


@router.callback_query(F.data.startswith(AST_CLOSE_PREFIX))
async def handle_admin_close(callback: CallbackQuery, support_ticket_service: SupportTicketService) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    try:
        ticket_id = int(callback.data.removeprefix(AST_CLOSE_PREFIX))
    except ValueError:
        await callback.answer()
        return
    ticket = await support_ticket_service.get_ticket_for_admin(ticket_id)
    if ticket is None:
        await callback.answer()
        return
    await support_ticket_service.close_ticket(ticket, admin_telegram_id=callback.from_user.id)
    await callback.answer("✅ Обращение закрыто.", show_alert=True)


@router.callback_query(F.data.startswith(AST_REOPEN_PREFIX))
async def handle_admin_reopen(callback: CallbackQuery, support_ticket_service: SupportTicketService) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    try:
        ticket_id = int(callback.data.removeprefix(AST_REOPEN_PREFIX))
    except ValueError:
        await callback.answer()
        return
    ticket = await support_ticket_service.get_ticket_for_admin(ticket_id)
    if ticket is None:
        await callback.answer()
        return
    await support_ticket_service.reopen_ticket(ticket, admin_telegram_id=callback.from_user.id)
    await callback.answer("🔓 Обращение открыто снова.", show_alert=True)


@router.callback_query(F.data.startswith(AST_CLIENT_PREFIX))
async def handle_admin_open_client(
    callback: CallbackQuery,
    admin_customer_service: AdminCustomerService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        telegram_id = int(callback.data.removeprefix(AST_CLIENT_PREFIX))
    except ValueError:
        await callback.answer()
        return
    items, total, page = await admin_customer_service.search_clients(str(telegram_id), page=0)
    if not items:
        await callback.answer("Клиент не найден.", show_alert=True)
        return
    text = admin_customer_service.format_search_results(str(telegram_id), items, page=page, total=total)
    from app.presentation.keyboards.admin_clients import search_results_keyboard

    await callback.message.answer(text, reply_markup=search_results_keyboard(items, page=page, total=total))
    await callback.answer()


@router.callback_query(F.data == AST_SEARCH)
async def handle_admin_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSupportStates.waiting_search_id)
    if callback.message:
        await callback.message.answer("Введите номер обращения (ID). /cancel — отмена")
    await callback.answer()


@router.message(StateFilter(AdminSupportStates.waiting_search_id))
async def handle_admin_search_id(
    message: Message,
    state: FSMContext,
    support_ticket_service: SupportTicketService,
) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Введите числовой ID обращения.")
        return
    ticket_id = int(message.text.strip())
    ticket = await support_ticket_service.get_ticket_for_admin(ticket_id)
    await state.clear()
    if ticket is None:
        await message.answer("Обращение не найдено.", reply_markup=admin_main_keyboard())
        return
    messages = await support_ticket_service.get_ticket_messages(ticket_id, limit=10)
    text = support_ticket_service.format_ticket_detail(ticket, messages, admin_view=True)
    user = ticket.user
    await message.answer(
        text,
        reply_markup=admin_support_ticket_keyboard(
            ticket_id,
            user_telegram_id=user.telegram_id if user else None,
            status=ticket.status,
        ),
    )


@router.callback_query(F.data == AST_PAGE_INFO)
async def handle_page_info(callback: CallbackQuery) -> None:
    await callback.answer()


def _status_title(status: str) -> str:
    return {
        SupportTicketStatus.OPEN.value: "🆕 Открытые обращения",
        SupportTicketStatus.ANSWERED.value: "💬 Ожидают ответа",
        SupportTicketStatus.CLOSED.value: "✅ Закрытые обращения",
    }.get(status, "Обращения")
