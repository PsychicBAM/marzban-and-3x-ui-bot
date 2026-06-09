from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import PaymentRequestStatus, PaymentRequestType
from app.infrastructure.db.models.payment_request import PaymentRequest


class PaymentRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, request_id: int) -> PaymentRequest | None:
        stmt = select(PaymentRequest).where(PaymentRequest.id == request_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, request_id: int) -> PaymentRequest | None:
        stmt = (
            select(PaymentRequest)
            .where(PaymentRequest.id == request_id)
            .options(
                selectinload(PaymentRequest.user),
                selectinload(PaymentRequest.plan),
                selectinload(PaymentRequest.vpn_account),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_renewal_by_user_id(self, user_id: int) -> PaymentRequest | None:
        stmt = (
            select(PaymentRequest)
            .where(
                PaymentRequest.user_id == user_id,
                PaymentRequest.request_type == PaymentRequestType.RENEWAL.value,
                PaymentRequest.status == PaymentRequestStatus.PENDING.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pending_with_relations(self) -> list[PaymentRequest]:
        stmt = (
            select(PaymentRequest)
            .where(PaymentRequest.status == PaymentRequestStatus.PENDING.value)
            .options(
                selectinload(PaymentRequest.user),
                selectinload(PaymentRequest.plan),
                selectinload(PaymentRequest.vpn_account),
            )
            .order_by(PaymentRequest.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_user_id(self, user_id: int) -> PaymentRequest | None:
        stmt = (
            select(PaymentRequest)
            .where(PaymentRequest.user_id == user_id)
            .order_by(PaymentRequest.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_free_plan_activation(self, user_id: int) -> bool:
        stmt = (
            select(PaymentRequest.id)
            .where(
                PaymentRequest.user_id == user_id,
                PaymentRequest.request_type == PaymentRequestType.PURCHASE.value,
                PaymentRequest.amount == 0,
                PaymentRequest.status.notin_(
                    (
                        PaymentRequestStatus.PENDING.value,
                        PaymentRequestStatus.REJECTED.value,
                    ),
                ),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create_approved_free_purchase(
        self,
        *,
        user_id: int,
        plan_id: int,
    ) -> PaymentRequest:
        now = datetime.now(UTC)
        request = PaymentRequest(
            user_id=user_id,
            plan_id=plan_id,
            request_type=PaymentRequestType.PURCHASE.value,
            amount=Decimal("0"),
            receipt_file_id=None,
            receipt_file_type=None,
            user_comment=None,
            status=PaymentRequestStatus.APPROVED.value,
            approved_at=now,
            processed_at=now,
        )
        self._session.add(request)
        await self._session.flush()
        await self._session.refresh(request)
        return request

    async def get_pending_purchase_by_user_id(self, user_id: int) -> PaymentRequest | None:
        stmt = (
            select(PaymentRequest)
            .where(
                PaymentRequest.user_id == user_id,
                PaymentRequest.request_type == PaymentRequestType.PURCHASE.value,
                PaymentRequest.status == PaymentRequestStatus.PENDING.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: int,
        plan_id: int,
        request_type: str,
        amount: Decimal,
        receipt_file_id: str | None,
        receipt_file_type: str | None,
        user_comment: str | None,
        receipt_message_id: int | None = None,
        vpn_account_id: int | None = None,
    ) -> PaymentRequest:
        request = PaymentRequest(
            user_id=user_id,
            plan_id=plan_id,
            vpn_account_id=vpn_account_id,
            request_type=request_type,
            amount=amount,
            receipt_file_id=receipt_file_id,
            receipt_file_type=receipt_file_type,
            user_comment=user_comment,
            receipt_message_id=receipt_message_id,
            status=PaymentRequestStatus.PENDING.value,
        )
        self._session.add(request)
        await self._session.flush()
        await self._session.refresh(request)
        return request

    async def approve(self, request: PaymentRequest, *, admin_telegram_id: int) -> PaymentRequest:
        now = datetime.now(UTC)
        request.status = PaymentRequestStatus.APPROVED.value
        request.processed_by_telegram_id = admin_telegram_id
        request.processed_at = now
        request.approved_at = now
        request.provisioning_error = None
        await self._session.flush()
        await self._session.refresh(request)
        return request

    async def reject(self, request: PaymentRequest, *, admin_telegram_id: int) -> PaymentRequest:
        now = datetime.now(UTC)
        request.status = PaymentRequestStatus.REJECTED.value
        request.processed_by_telegram_id = admin_telegram_id
        request.processed_at = now
        request.rejected_at = now
        await self._session.flush()
        await self._session.refresh(request)
        return request

    async def mark_provisioning_failed(
        self,
        request: PaymentRequest,
        *,
        error_message: str,
    ) -> PaymentRequest:
        request.status = PaymentRequestStatus.PROVISIONING_FAILED.value
        request.provisioning_error = error_message[:2000]
        await self._session.flush()
        await self._session.refresh(request)
        return request

    async def mark_provisioning_partial(
        self,
        request: PaymentRequest,
        *,
        error_message: str,
        vpn_account_id: int | None,
    ) -> PaymentRequest:
        request.status = PaymentRequestStatus.PROVISIONING_PARTIAL.value
        request.provisioning_error = error_message[:2000]
        request.vpn_account_id = vpn_account_id
        await self._session.flush()
        await self._session.refresh(request)
        return request

    async def link_vpn_account(self, request: PaymentRequest, vpn_account_id: int) -> PaymentRequest:
        request.vpn_account_id = vpn_account_id
        request.provisioning_error = None
        await self._session.flush()
        await self._session.refresh(request)
        return request
