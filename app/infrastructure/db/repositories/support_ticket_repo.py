from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import SupportMessageSenderType, SupportTicketStatus
from app.infrastructure.db.models.support_ticket import SupportMessage, SupportTicket


class SupportTicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_ticket(
        self,
        *,
        user_id: int,
        topic: str,
        subject: str | None = None,
    ) -> SupportTicket:
        ticket = SupportTicket(user_id=user_id, topic=topic, subject=subject)
        self._session.add(ticket)
        await self._session.flush()
        await self._session.refresh(ticket)
        return ticket

    async def add_message(
        self,
        *,
        ticket_id: int,
        sender_type: str,
        text: str | None = None,
        sender_user_id: int | None = None,
        admin_telegram_id: int | None = None,
        photo_file_id: str | None = None,
        document_file_id: str | None = None,
    ) -> SupportMessage:
        message = SupportMessage(
            ticket_id=ticket_id,
            sender_type=sender_type,
            sender_user_id=sender_user_id,
            admin_telegram_id=admin_telegram_id,
            text=text,
            photo_file_id=photo_file_id,
            document_file_id=document_file_id,
        )
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def get_by_id(self, ticket_id: int) -> SupportTicket | None:
        stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, ticket_id: int) -> SupportTicket | None:
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .options(
                selectinload(SupportTicket.user),
                selectinload(SupportTicket.messages),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SupportTicket], int]:
        count_stmt = select(func.count()).select_from(SupportTicket).where(SupportTicket.user_id == user_id)
        total = int((await self._session.execute(count_stmt)).scalar_one())
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.user_id == user_id)
            .order_by(
                case((SupportTicket.status == SupportTicketStatus.CLOSED.value, 1), else_=0),
                SupportTicket.updated_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_by_status(
        self,
        status: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SupportTicket], int]:
        count_stmt = select(func.count()).select_from(SupportTicket).where(SupportTicket.status == status)
        total = int((await self._session.execute(count_stmt)).scalar_one())
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.status == status)
            .options(selectinload(SupportTicket.user))
            .order_by(SupportTicket.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def count_by_status(self, status: str) -> int:
        stmt = select(func.count()).select_from(SupportTicket).where(SupportTicket.status == status)
        return int((await self._session.execute(stmt)).scalar_one())

    async def count_open(self) -> int:
        return await self.count_by_status(SupportTicketStatus.OPEN.value)

    async def update_status(self, ticket: SupportTicket, *, status: str) -> SupportTicket:
        now = datetime.now(UTC)
        ticket.status = status
        ticket.updated_at = now
        if status == SupportTicketStatus.CLOSED.value:
            ticket.closed_at = now
        elif status in (SupportTicketStatus.OPEN.value, SupportTicketStatus.ANSWERED.value):
            ticket.closed_at = None
        await self._session.flush()
        await self._session.refresh(ticket)
        return ticket

    async def touch(self, ticket: SupportTicket) -> SupportTicket:
        ticket.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(ticket)
        return ticket

    async def get_latest_messages(self, ticket_id: int, *, limit: int = 10) -> list[SupportMessage]:
        stmt = (
            select(SupportMessage)
            .where(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(reversed(result.scalars().all()))

    async def count_customer_messages(self, ticket_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(SupportMessage)
            .where(
                SupportMessage.ticket_id == ticket_id,
                SupportMessage.sender_type == SupportMessageSenderType.CUSTOMER.value,
            )
        )
        return int((await self._session.execute(stmt)).scalar_one())
