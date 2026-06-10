from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import PaymentRequestStatus
from app.infrastructure.db.models.payment_request import PaymentRequest
from app.infrastructure.db.models.promo_code import PromoCode, PromoCodeRedemption


class PromoCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, promo_code_id: int) -> PromoCode | None:
        stmt = select(PromoCode).where(PromoCode.id == promo_code_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> PromoCode | None:
        stmt = select(PromoCode).where(PromoCode.code == code)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_code(self, code: str) -> bool:
        stmt = select(PromoCode.id).where(PromoCode.code == code).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        *,
        code: str,
        discount_type: str,
        value: Decimal,
        is_active: bool = True,
        starts_at: datetime | None = None,
        expires_at: datetime | None = None,
        max_uses: int | None = None,
        max_uses_per_user: int = 1,
        min_amount: Decimal | None = None,
        applies_to_plan_id: int | None = None,
        applies_to_request_type: str | None = None,
        new_users_only: bool = False,
        created_by_admin_id: int | None = None,
    ) -> PromoCode:
        promo = PromoCode(
            code=code,
            discount_type=discount_type,
            value=value,
            is_active=is_active,
            starts_at=starts_at,
            expires_at=expires_at,
            max_uses=max_uses,
            max_uses_per_user=max_uses_per_user,
            min_amount=min_amount,
            applies_to_plan_id=applies_to_plan_id,
            applies_to_request_type=applies_to_request_type,
            new_users_only=new_users_only,
            created_by_admin_id=created_by_admin_id,
        )
        self._session.add(promo)
        await self._session.flush()
        await self._session.refresh(promo)
        return promo

    async def list_all(self, *, limit: int = 50) -> list[PromoCode]:
        stmt = select(PromoCode).order_by(PromoCode.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search(self, query: str, *, limit: int = 20) -> list[PromoCode]:
        q = query.strip().upper()
        if not q:
            return []
        stmt = (
            select(PromoCode)
            .where(PromoCode.code.ilike(f"%{q}%"))
            .order_by(PromoCode.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def set_active(self, promo: PromoCode, *, is_active: bool) -> PromoCode:
        promo.is_active = is_active
        await self._session.flush()
        await self._session.refresh(promo)
        return promo

    async def count_user_redemptions(self, promo_code_id: int, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(PromoCodeRedemption)
            .where(
                PromoCodeRedemption.promo_code_id == promo_code_id,
                PromoCodeRedemption.user_id == user_id,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def user_has_approved_payment(self, user_id: int) -> bool:
        stmt = (
            select(PaymentRequest.id)
            .where(
                PaymentRequest.user_id == user_id,
                PaymentRequest.status == PaymentRequestStatus.APPROVED.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create_redemption(
        self,
        *,
        promo_code_id: int,
        user_id: int,
        payment_request_id: int | None,
        original_amount: Decimal,
        discount_amount: Decimal,
        final_amount: Decimal,
        extra_days: int,
    ) -> PromoCodeRedemption:
        redemption = PromoCodeRedemption(
            promo_code_id=promo_code_id,
            user_id=user_id,
            payment_request_id=payment_request_id,
            original_amount=original_amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            extra_days=extra_days,
        )
        self._session.add(redemption)
        await self._session.flush()
        await self._session.refresh(redemption)
        return redemption

    async def increment_used_count(self, promo: PromoCode) -> None:
        promo.used_count += 1
        await self._session.flush()

    async def list_redemptions(self, promo_code_id: int, *, limit: int = 30) -> list[PromoCodeRedemption]:
        stmt = (
            select(PromoCodeRedemption)
            .where(PromoCodeRedemption.promo_code_id == promo_code_id)
            .order_by(PromoCodeRedemption.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(self) -> dict[str, int | Decimal]:
        total_codes = await self._session.scalar(select(func.count()).select_from(PromoCode))
        active_codes = await self._session.scalar(
            select(func.count()).select_from(PromoCode).where(PromoCode.is_active.is_(True))
        )
        total_redemptions = await self._session.scalar(select(func.count()).select_from(PromoCodeRedemption))
        total_discount = await self._session.scalar(
            select(func.coalesce(func.sum(PromoCodeRedemption.discount_amount), 0))
        )
        return {
            "total_codes": int(total_codes or 0),
            "active_codes": int(active_codes or 0),
            "total_redemptions": int(total_redemptions or 0),
            "total_discount": Decimal(str(total_discount or 0)),
        }

    async def get_with_plan(self, promo_code_id: int) -> PromoCode | None:
        stmt = (
            select(PromoCode)
            .where(PromoCode.id == promo_code_id)
            .options(selectinload(PromoCode.plan))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
