from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import BroadcastRecipientStatus, BroadcastStatus
from app.infrastructure.db.models.broadcast import Broadcast, BroadcastRecipient


class BroadcastRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, broadcast_id: int) -> Broadcast | None:
        stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        title: str,
        text: str,
        photo_file_id: str | None,
        target_type: str,
        created_by_admin_id: int,
        total_recipients: int,
        status: str = BroadcastStatus.DRAFT.value,
    ) -> Broadcast:
        broadcast = Broadcast(
            title=title,
            text=text,
            photo_file_id=photo_file_id,
            target_type=target_type,
            status=status,
            total_recipients=total_recipients,
            created_by_admin_id=created_by_admin_id,
        )
        self._session.add(broadcast)
        await self._session.flush()
        await self._session.refresh(broadcast)
        return broadcast

    async def list_recent(self, *, limit: int = 15) -> list[Broadcast]:
        stmt = select(Broadcast).order_by(Broadcast.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        broadcast: Broadcast,
        *,
        status: str,
        sent_at: datetime | None = None,
        sent_count: int | None = None,
        failed_count: int | None = None,
    ) -> Broadcast:
        broadcast.status = status
        if sent_at is not None:
            broadcast.sent_at = sent_at
        if sent_count is not None:
            broadcast.sent_count = sent_count
        if failed_count is not None:
            broadcast.failed_count = failed_count
        await self._session.flush()
        await self._session.refresh(broadcast)
        return broadcast

    async def increment_counts(
        self,
        broadcast_id: int,
        *,
        sent_delta: int = 0,
        failed_delta: int = 0,
    ) -> None:
        broadcast = await self.get_by_id(broadcast_id)
        if broadcast is None:
            return
        broadcast.sent_count += sent_delta
        broadcast.failed_count += failed_delta
        await self._session.flush()

    async def bulk_create_recipients(
        self,
        broadcast_id: int,
        recipients: list[tuple[int, int]],
    ) -> None:
        if not recipients:
            return
        objects = [
            BroadcastRecipient(
                broadcast_id=broadcast_id,
                user_id=user_id,
                telegram_id=telegram_id,
                status=BroadcastRecipientStatus.PENDING.value,
            )
            for user_id, telegram_id in recipients
        ]
        self._session.add_all(objects)
        await self._session.flush()

    async def list_pending_recipients(
        self,
        broadcast_id: int,
        *,
        limit: int = 25,
    ) -> list[BroadcastRecipient]:
        stmt = (
            select(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == BroadcastRecipientStatus.PENDING.value,
            )
            .order_by(BroadcastRecipient.id)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_recipient(
        self,
        recipient: BroadcastRecipient,
        *,
        status: str,
        error_message: str | None = None,
    ) -> None:
        recipient.status = status
        recipient.error_message = error_message[:512] if error_message else None
        if status == BroadcastRecipientStatus.SENT.value:
            recipient.sent_at = datetime.now(UTC)
        await self._session.flush()

    async def count_recipient_statuses(self, broadcast_id: int) -> dict[str, int]:
        stmt = select(BroadcastRecipient.status).where(BroadcastRecipient.broadcast_id == broadcast_id)
        result = await self._session.execute(stmt)
        counts: dict[str, int] = {}
        for (status,) in result.all():
            counts[status] = counts.get(status, 0) + 1
        return counts

    async def refresh_broadcast_counts(self, broadcast_id: int) -> None:
        counts = await self.count_recipient_statuses(broadcast_id)
        sent = counts.get(BroadcastRecipientStatus.SENT.value, 0)
        failed = counts.get(BroadcastRecipientStatus.FAILED.value, 0)
        blocked = counts.get(BroadcastRecipientStatus.BLOCKED.value, 0)
        stmt = (
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(sent_count=sent, failed_count=failed + blocked)
        )
        await self._session.execute(stmt)
