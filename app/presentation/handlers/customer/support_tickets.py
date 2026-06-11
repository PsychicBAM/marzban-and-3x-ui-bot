from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.services.support_ticket_service import SupportTicketService
from app.application.services.user_service import UserService
from app.config.settings import Settings
from app.domain.enums import SupportTicketStatus
from app.presentation.filters.customer_menu import menu_text_filter
from app.presentation.i18n import t
from app.presentation.keyboards.customer import customer_main_keyboard
from app.presentation.keyboards.customer_support import (
    SUP_BACK_MENU,
    SUP_CREATE,
    SUP_LIST_PAGE_PREFIX,
    SUP_MENU,
    SUP_TICKET_BACK_LIST,
    SUP_TICKET_CLOSE_PREFIX,
    SUP_TICKET_PREFIX,
    SUP_TICKET_REPLY_PREFIX,
    SUP_TOPIC_PREFIX,
    support_menu_keyboard,
    support_ticket_detail_keyboard,
    support_ticket_list_keyboard,
    support_topic_keyboard,
)
from app.presentation.states.support_ticket import CustomerSupportStates
from app.presentation.utils.html_format import CUSTOMER_PARSE_MODE
from app.presentation.utils.telegram import safe_edit_message_text

logger = logging.getLogger(__name__)

router = Router(name="customer_support_tickets")


@router.message(menu_text_filter("menu.support"))
async def handle_support_menu(message: Message, support_ticket_service: SupportTicketService, lang: str) -> None:
    await message.answer(
        support_ticket_service.format_customer_menu(lang),
        reply_markup=support_menu_keyboard(lang),
        parse_mode=CUSTOMER_PARSE_MODE,
    )


@router.callback_query(F.data == SUP_MENU)
async def handle_support_menu_callback(
    callback: CallbackQuery,
    support_ticket_service: SupportTicketService,
    lang: str,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await safe_edit_message_text(
        callback.message,
        support_ticket_service.format_customer_menu(lang),
        reply_markup=support_menu_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == SUP_BACK_MENU)
async def handle_support_back_menu(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer(
        t(lang, "common.main_menu"),
        reply_markup=customer_main_keyboard(lang),
        parse_mode=CUSTOMER_PARSE_MODE,
    )
    await callback.answer()


@router.callback_query(F.data == SUP_CREATE)
async def handle_support_create(callback: CallbackQuery, lang: str) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await safe_edit_message_text(
        callback.message,
        t(lang, "support.choose_topic"),
        reply_markup=support_topic_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(SUP_TOPIC_PREFIX))
async def handle_support_topic(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    topic = callback.data.removeprefix(SUP_TOPIC_PREFIX)
    await state.set_state(CustomerSupportStates.waiting_message)
    await state.update_data(topic=topic)
    await callback.message.answer(t(lang, "support.enter_message"), parse_mode=CUSTOMER_PARSE_MODE)
    await callback.answer()


@router.message(StateFilter(CustomerSupportStates.waiting_message))
async def handle_support_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    settings: Settings,
    user_service: UserService,
    support_ticket_service: SupportTicketService,
    lang: str,
) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    topic = data.get("topic")
    if not topic:
        await state.clear()
        await message.answer(t(lang, "common.session_expired"), reply_markup=customer_main_keyboard(lang))
        return

    user = await user_service.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await state.clear()
        await message.answer(t(lang, "common.start_first"), reply_markup=customer_main_keyboard(lang))
        return

    text = message.text or message.caption
    photo_id = message.photo[-1].file_id if message.photo else None
    document_id = message.document.file_id if message.document else None
    if not text and not photo_id and not document_id:
        await message.answer(t(lang, "support.enter_message"), parse_mode=CUSTOMER_PARSE_MODE)
        return

    ticket = await support_ticket_service.create_ticket(
        user_id=user.id,
        topic=topic,
        text=text,
        photo_file_id=photo_id,
        document_file_id=document_id,
    )
    await state.clear()
    await message.answer(
        t(lang, "support.ticket_created", ticket_id=ticket.id),
        reply_markup=customer_main_keyboard(lang),
        parse_mode=CUSTOMER_PARSE_MODE,
    )
    await _notify_admins_new_ticket(bot, settings, support_ticket_service, ticket, user)


@router.callback_query(F.data.startswith(SUP_LIST_PAGE_PREFIX))
async def handle_support_list(
    callback: CallbackQuery,
    user_service: UserService,
    support_ticket_service: SupportTicketService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        page = int(callback.data.removeprefix(SUP_LIST_PAGE_PREFIX))
    except ValueError:
        await callback.answer()
        return
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    tickets, page, pages = await support_ticket_service.list_customer_tickets(user.id, page=page)
    text = support_ticket_service.format_customer_ticket_list(tickets, lang=lang, page=page, pages=pages)
    await safe_edit_message_text(
        callback.message,
        text,
        reply_markup=support_ticket_list_keyboard(lang, tickets, page=page, pages=pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(SUP_TICKET_PREFIX))
async def handle_support_ticket_detail(
    callback: CallbackQuery,
    user_service: UserService,
    support_ticket_service: SupportTicketService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        ticket_id = int(callback.data.removeprefix(SUP_TICKET_PREFIX))
    except ValueError:
        await callback.answer()
        return
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(t(lang, "common.start_first"), show_alert=True)
        return
    ticket = await support_ticket_service.get_ticket_for_user(ticket_id, user.id)
    if ticket is None:
        await callback.answer(t(lang, "common.invalid_request"), show_alert=True)
        return
    messages = await support_ticket_service.get_ticket_messages(ticket_id, limit=8)
    text = support_ticket_service.format_ticket_detail(ticket, messages, lang=lang)
    can_reply = ticket.status != SupportTicketStatus.CLOSED.value
    await safe_edit_message_text(
        callback.message,
        text,
        reply_markup=support_ticket_detail_keyboard(lang, ticket_id, can_reply=can_reply, can_close=can_reply),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(SUP_TICKET_REPLY_PREFIX))
async def handle_support_reply_start(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str,
) -> None:
    if callback.data is None:
        await callback.answer()
        return
    try:
        ticket_id = int(callback.data.removeprefix(SUP_TICKET_REPLY_PREFIX))
    except ValueError:
        await callback.answer()
        return
    await state.set_state(CustomerSupportStates.waiting_reply)
    await state.update_data(ticket_id=ticket_id)
    if callback.message:
        await callback.message.answer(t(lang, "support.enter_reply"), parse_mode=CUSTOMER_PARSE_MODE)
    await callback.answer()


@router.message(StateFilter(CustomerSupportStates.waiting_reply))
async def handle_support_reply_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    settings: Settings,
    user_service: UserService,
    support_ticket_service: SupportTicketService,
    lang: str,
) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await state.clear()
        return
    user = await user_service.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await state.clear()
        return
    ticket = await support_ticket_service.get_ticket_for_user(int(ticket_id), user.id)
    if ticket is None:
        await state.clear()
        return
    text = message.text or message.caption
    photo_id = message.photo[-1].file_id if message.photo else None
    document_id = message.document.file_id if message.document else None
    if not text and not photo_id and not document_id:
        await message.answer(t(lang, "support.enter_reply"), parse_mode=CUSTOMER_PARSE_MODE)
        return
    await support_ticket_service.add_customer_reply(
        ticket,
        user_id=user.id,
        text=text,
        photo_file_id=photo_id,
        document_file_id=document_id,
    )
    await state.clear()
    await message.answer(t(lang, "common.done"), reply_markup=customer_main_keyboard(lang))
    await _notify_admins_customer_reply(bot, settings, ticket.id, user.telegram_id)


@router.callback_query(F.data.startswith(SUP_TICKET_CLOSE_PREFIX))
async def handle_support_close(
    callback: CallbackQuery,
    user_service: UserService,
    support_ticket_service: SupportTicketService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return
    try:
        ticket_id = int(callback.data.removeprefix(SUP_TICKET_CLOSE_PREFIX))
    except ValueError:
        await callback.answer()
        return
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer()
        return
    ticket = await support_ticket_service.get_ticket_for_user(ticket_id, user.id)
    if ticket is None:
        await callback.answer()
        return
    await support_ticket_service.close_ticket(ticket)
    await callback.answer(t(lang, "support.ticket_closed", ticket_id=ticket_id), show_alert=True)


@router.callback_query(F.data == SUP_TICKET_BACK_LIST)
async def handle_support_back_list(
    callback: CallbackQuery,
    user_service: UserService,
    support_ticket_service: SupportTicketService,
    lang: str,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer()
        return
    tickets, page, pages = await support_ticket_service.list_customer_tickets(user.id, page=0)
    text = support_ticket_service.format_customer_ticket_list(tickets, lang=lang, page=page, pages=pages)
    await safe_edit_message_text(
        callback.message,
        text,
        reply_markup=support_ticket_list_keyboard(lang, tickets, page=page, pages=pages),
    )
    await callback.answer()


async def _notify_admins_new_ticket(bot, settings, service, ticket, user) -> None:
    admin_ids = settings.admin_telegram_ids
    if not admin_ids:
        return
    name = service._user_display(user)
    text = service.format_admin_new_ticket(ticket, name, user.username)
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as exc:
            logger.warning("Failed to notify admin about support ticket", extra={"error": str(exc)[:200]})


async def _notify_admins_customer_reply(bot, settings, ticket_id: int, customer_telegram_id: int) -> None:
    text = f"💬 Клиент ответил в обращении #{ticket_id} (ID {customer_telegram_id})"
    for admin_id in settings.admin_telegram_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass
