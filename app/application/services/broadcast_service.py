from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.services.admin_log_service import AdminLogService
from app.domain.enums import AdminActionType, BroadcastStatus, BroadcastTargetType
from app.infrastructure.db.models.broadcast import Broadcast
from app.infrastructure.db.uow import UnitOfWork

TARGET_LABELS: dict[str, str] = {
    BroadcastTargetType.ALL.value: "Все пользователи",
    BroadcastTargetType.ACTIVE_VPN.value: "С активным VPN",
    BroadcastTargetType.EXPIRED_VPN.value: "С истёкшим VPN",
    BroadcastTargetType.NO_ACTIVE_VPN.value: "Без активного VPN",
    BroadcastTargetType.EXPIRING_SOON.value: "VPN истекает ≤7 дн.",
    BroadcastTargetType.PROMO_ENABLED.value: "Подписаны на акции",
}

STATUS_LABELS: dict[str, str] = {
    BroadcastStatus.DRAFT.value: "черновик",
    BroadcastStatus.SENDING.value: "отправляется",
    BroadcastStatus.SENT.value: "отправлена",
    BroadcastStatus.FAILED.value: "ошибка",
    BroadcastStatus.SCHEDULED.value: "запланирована",
}


@dataclass(slots=True)
class BroadcastDraft:
    title: str
    text: str
    photo_file_id: str | None
    target_type: str
    recipient_count: int


class BroadcastService:
    def __init__(self, uow: UnitOfWork, admin_log_service: AdminLogService) -> None:
        self._uow = uow
        self._admin_log = admin_log_service

    async def count_recipients(self, target_type: str) -> int:
        return await self._uow.broadcast_audience.count_recipients(target_type)

    async def build_draft(
        self,
        *,
        title: str,
        text: str,
        photo_file_id: str | None,
        target_type: str,
    ) -> BroadcastDraft:
        count = await self.count_recipients(target_type)
        return BroadcastDraft(
            title=title.strip(),
            text=text.strip(),
            photo_file_id=photo_file_id,
            target_type=target_type,
            recipient_count=count,
        )

    async def create_and_queue(
        self,
        draft: BroadcastDraft,
        *,
        admin_telegram_id: int,
    ) -> Broadcast:
        recipients = await self._uow.broadcast_audience.resolve_recipients(draft.target_type)
        broadcast = await self._uow.broadcasts.create(
            title=draft.title,
            text=draft.text,
            photo_file_id=draft.photo_file_id,
            target_type=draft.target_type,
            created_by_admin_id=admin_telegram_id,
            total_recipients=len(recipients),
            status=BroadcastStatus.SENDING.value,
        )
        await self._uow.broadcasts.bulk_create_recipients(broadcast.id, recipients)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.BROADCAST_CREATED,
            details={
                "broadcast_id": broadcast.id,
                "target_type": draft.target_type,
                "total_recipients": len(recipients),
                "has_photo": draft.photo_file_id is not None,
            },
        )
        return broadcast

    async def list_history(self, *, limit: int = 15) -> list[Broadcast]:
        return await self._uow.broadcasts.list_recent(limit=limit)

    @staticmethod
    def escape_text(text: str) -> str:
        return html.escape(text, quote=False)

    @staticmethod
    def format_message_html(text: str) -> str:
        return BroadcastService.escape_text(text)

    def format_preview(self, draft: BroadcastDraft) -> str:
        safe_title = self.escape_text(draft.title)
        safe_text = self.format_message_html(draft.text)
        audience = TARGET_LABELS.get(draft.target_type, draft.target_type)
        photo_line = "да" if draft.photo_file_id else "нет"
        return (
            "📣 <b>Предпросмотр рассылки</b>\n\n"
            f"<b>Название:</b> {safe_title}\n\n"
            f"{safe_text}\n\n"
            f"🖼 Фото: <b>{photo_line}</b>\n"
            f"👥 Аудитория: <b>{audience}</b>\n"
            f"📊 Получателей: <b>{draft.recipient_count}</b>"
        )

    def format_history(self, items: list[Broadcast]) -> str:
        if not items:
            return "📋 <b>История рассылок</b>\n\nПока нет рассылок."
        lines = ["📋 <b>История рассылок</b>", ""]
        for item in items:
            status = STATUS_LABELS.get(item.status, item.status)
            target = TARGET_LABELS.get(item.target_type, item.target_type)
            created = item.created_at.strftime("%d.%m.%Y %H:%M")
            sent = item.sent_at.strftime("%d.%m.%Y %H:%M") if item.sent_at else "—"
            title = self.escape_text(item.title)
            lines.append(
                f"• <b>{title}</b>\n"
                f"  {status} · {target}\n"
                f"  ✉️ {item.sent_count}/{item.total_recipients} · "
                f"создана {created} · отправлена {sent}"
            )
        return "\n".join(lines)

    @staticmethod
    def target_label(target_type: str) -> str:
        return TARGET_LABELS.get(target_type, target_type)

    async def finalize_broadcast(
        self,
        broadcast_id: int,
        *,
        admin_telegram_id: int,
        success: bool,
    ) -> None:
        broadcast = await self._uow.broadcasts.get_by_id(broadcast_id)
        if broadcast is None:
            return
        await self._uow.broadcasts.refresh_broadcast_counts(broadcast_id)
        broadcast = await self._uow.broadcasts.get_by_id(broadcast_id)
        if broadcast is None:
            return

        if broadcast.sent_count > 0:
            status = BroadcastStatus.SENT.value
            action = AdminActionType.BROADCAST_SENT
        else:
            status = BroadcastStatus.FAILED.value
            action = AdminActionType.BROADCAST_FAILED

        await self._uow.broadcasts.update_status(
            broadcast,
            status=status,
            sent_at=datetime.now(UTC),
            sent_count=broadcast.sent_count,
            failed_count=broadcast.failed_count,
        )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=action,
            details={
                "broadcast_id": broadcast_id,
                "sent_count": broadcast.sent_count,
                "failed_count": broadcast.failed_count,
                "total_recipients": broadcast.total_recipients,
            },
        )
