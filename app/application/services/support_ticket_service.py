from __future__ import annotations

import logging
from html import escape

from app.application.services.admin_log_service import AdminLogService
from app.application.utils.admin_client_format import total_pages
from app.config.settings import Settings
from app.domain.enums import (
    AdminActionType,
    SupportMessageSenderType,
    SupportTicketStatus,
    SupportTicketTopic,
)
from app.infrastructure.db.models.support_ticket import SupportMessage, SupportTicket
from app.infrastructure.db.uow import UnitOfWork
from app.presentation.i18n import t

logger = logging.getLogger(__name__)

TICKET_PAGE_SIZE = 6


class SupportTicketService:
    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        admin_log_service: AdminLogService,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._admin_log = admin_log_service

    async def create_ticket(
        self,
        *,
        user_id: int,
        topic: str,
        text: str | None,
        photo_file_id: str | None = None,
        document_file_id: str | None = None,
    ) -> SupportTicket:
        ticket = await self._uow.support_tickets.create_ticket(user_id=user_id, topic=topic)
        await self._uow.support_tickets.add_message(
            ticket_id=ticket.id,
            sender_type=SupportMessageSenderType.CUSTOMER.value,
            sender_user_id=user_id,
            text=text,
            photo_file_id=photo_file_id,
            document_file_id=document_file_id,
        )
        await self._admin_log.log(
            admin_telegram_id=0,
            action=AdminActionType.SUPPORT_TICKET_CREATED,
            details={"ticket_id": ticket.id, "user_id": user_id, "topic": topic},
        )
        return ticket

    async def add_customer_reply(
        self,
        ticket: SupportTicket,
        *,
        user_id: int,
        text: str | None,
        photo_file_id: str | None = None,
        document_file_id: str | None = None,
    ) -> SupportMessage:
        message = await self._uow.support_tickets.add_message(
            ticket_id=ticket.id,
            sender_type=SupportMessageSenderType.CUSTOMER.value,
            sender_user_id=user_id,
            text=text,
            photo_file_id=photo_file_id,
            document_file_id=document_file_id,
        )
        await self._uow.support_tickets.update_status(ticket, status=SupportTicketStatus.OPEN.value)
        return message

    async def add_admin_reply(
        self,
        ticket: SupportTicket,
        *,
        admin_telegram_id: int,
        text: str,
    ) -> SupportMessage:
        message = await self._uow.support_tickets.add_message(
            ticket_id=ticket.id,
            sender_type=SupportMessageSenderType.ADMIN.value,
            admin_telegram_id=admin_telegram_id,
            text=text,
        )
        await self._uow.support_tickets.update_status(ticket, status=SupportTicketStatus.ANSWERED.value)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.SUPPORT_TICKET_REPLIED,
            details={"ticket_id": ticket.id, "user_id": ticket.user_id},
        )
        return message

    async def close_ticket(self, ticket: SupportTicket, *, admin_telegram_id: int | None = None) -> SupportTicket:
        await self._uow.support_tickets.update_status(ticket, status=SupportTicketStatus.CLOSED.value)
        if admin_telegram_id is not None:
            await self._admin_log.log(
                admin_telegram_id=admin_telegram_id,
                action=AdminActionType.SUPPORT_TICKET_CLOSED,
                details={"ticket_id": ticket.id, "user_id": ticket.user_id},
            )
        return ticket

    async def reopen_ticket(self, ticket: SupportTicket, *, admin_telegram_id: int) -> SupportTicket:
        await self._uow.support_tickets.update_status(ticket, status=SupportTicketStatus.OPEN.value)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.SUPPORT_TICKET_REOPENED,
            details={"ticket_id": ticket.id, "user_id": ticket.user_id},
        )
        return ticket

    async def get_ticket_for_user(self, ticket_id: int, user_id: int) -> SupportTicket | None:
        ticket = await self._uow.support_tickets.get_by_id_with_relations(ticket_id)
        if ticket is None or ticket.user_id != user_id:
            return None
        return ticket

    async def get_ticket_for_admin(self, ticket_id: int) -> SupportTicket | None:
        return await self._uow.support_tickets.get_by_id_with_relations(ticket_id)

    async def get_ticket_messages(self, ticket_id: int, *, limit: int = 8) -> list[SupportMessage]:
        return await self._uow.support_tickets.get_latest_messages(ticket_id, limit=limit)

    async def list_customer_tickets(
        self,
        user_id: int,
        *,
        page: int,
    ) -> tuple[list[SupportTicket], int, int]:
        offset = page * TICKET_PAGE_SIZE
        tickets, total = await self._uow.support_tickets.list_by_user_id(
            user_id,
            offset=offset,
            limit=TICKET_PAGE_SIZE,
        )
        pages = total_pages(total, TICKET_PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        return tickets, page, pages

    async def list_admin_tickets(
        self,
        status: str,
        *,
        page: int,
    ) -> tuple[list[SupportTicket], int, int]:
        offset = page * TICKET_PAGE_SIZE
        tickets, total = await self._uow.support_tickets.list_by_status(
            status,
            offset=offset,
            limit=TICKET_PAGE_SIZE,
        )
        pages = total_pages(total, TICKET_PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        return tickets, page, pages

    def format_customer_menu(self, lang: str) -> str:
        return f"{t(lang, 'support.title')}\n\n{t(lang, 'support.choose_action')}"

    def format_customer_ticket_list(self, tickets: list[SupportTicket], *, lang: str, page: int, pages: int) -> str:
        if not tickets:
            return t(lang, "support.no_tickets")
        lines = [t(lang, "support.my_tickets_title"), ""]
        for ticket in tickets:
            lines.append(
                t(
                    lang,
                    "support.ticket_list_item",
                    ticket_id=ticket.id,
                    topic=self.topic_label(ticket.topic, lang),
                    status=self.status_label(ticket.status, lang),
                    updated=ticket.updated_at.strftime("%d.%m.%Y %H:%M"),
                )
            )
        lines.append("")
        lines.append(t(lang, "history.page", current=page + 1, total=pages))
        return "\n".join(lines)

    def format_ticket_detail(
        self,
        ticket: SupportTicket,
        messages: list[SupportMessage],
        *,
        lang: str | None = None,
        admin_view: bool = False,
    ) -> str:
        user = ticket.user
        if admin_view:
            name = self._user_display(user)
            header = (
                f"<b>Обращение #{ticket.id}</b>\n"
                f"Клиент: {escape(name)}"
                f"{f' (@{escape(user.username)})' if user and user.username else ''}\n"
                f"Telegram ID: <code>{user.telegram_id if user else '—'}</code>\n"
                f"Тема: {self.topic_label(ticket.topic, 'ru')}\n"
                f"Статус: {self.status_label(ticket.status, 'ru')}\n"
                f"Создано: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
        else:
            header = (
                f"{t(lang or 'ru', 'support.ticket_detail_title', ticket_id=ticket.id)}\n"
                f"{t(lang or 'ru', 'support.ticket_topic', topic=self.topic_label(ticket.topic, lang or 'ru'))}\n"
                f"{t(lang or 'ru', 'support.ticket_status', status=self.status_label(ticket.status, lang or 'ru'))}\n\n"
            )
        body_lines = []
        for message in messages:
            sender = self._message_sender_label(message, lang=lang, admin_view=admin_view)
            text = escape((message.text or "").strip()) if message.text else ""
            if text:
                body_lines.append(f"{sender}: {text}")
            elif message.photo_file_id:
                label = "📷" if admin_view else t(lang or "ru", "support.photo_attached")
                body_lines.append(f"{sender}: {label}")
            elif message.document_file_id:
                label = "📎" if admin_view else t(lang or "ru", "support.file_attached")
                body_lines.append(f"{sender}: {label}")
        return header + "\n".join(body_lines)

    def format_admin_new_ticket(self, ticket: SupportTicket, user_name: str, username: str | None) -> str:
        username_part = f" (@{username})" if username else ""
        return (
            f"🆕 <b>Новое обращение #{ticket.id}</b>\n"
            f"Клиент: {escape(user_name)}{username_part}\n"
            f"Тема: {self.topic_label(ticket.topic, 'ru')}\n"
            f"Статус: {self.status_label(ticket.status, 'ru')}"
        )

    @staticmethod
    def topic_label(topic: str, lang: str) -> str:
        key = {
            SupportTicketTopic.PAYMENT.value: "support.topic_payment",
            SupportTicketTopic.CONNECTION.value: "support.topic_connection",
            SupportTicketTopic.RENEWAL.value: "support.topic_renewal",
            SupportTicketTopic.OTHER.value: "support.topic_other",
        }.get(topic, "support.topic_other")
        return t(lang, key)

    @staticmethod
    def status_label(status: str, lang: str) -> str:
        if lang != "ru" and lang != "en":
            lang = "ru"
        key = {
            SupportTicketStatus.OPEN.value: "support.status_open",
            SupportTicketStatus.ANSWERED.value: "support.status_answered",
            SupportTicketStatus.CLOSED.value: "support.status_closed",
        }.get(status, "support.status_open")
        return t(lang, key)

    @staticmethod
    def _user_display(user) -> str:
        if user is None:
            return "—"
        parts = [user.first_name, user.last_name]
        name = " ".join(part for part in parts if part)
        return name or f"ID {user.telegram_id}"

    def _message_sender_label(
        self,
        message: SupportMessage,
        *,
        lang: str | None,
        admin_view: bool,
    ) -> str:
        if message.sender_type == SupportMessageSenderType.ADMIN.value:
            return "Админ" if admin_view else t(lang or "ru", "support.sender_admin")
        if message.sender_type == SupportMessageSenderType.SYSTEM.value:
            return "Система" if admin_view else t(lang or "ru", "support.sender_system")
        return "Вы" if not admin_view else "Клиент"
