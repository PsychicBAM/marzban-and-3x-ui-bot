from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import PaymentRequestStatus, ReferralEventStatus, ReferralRewardStatus, ReferralRewardType
from app.infrastructure.db.models.payment_request import PaymentRequest
from app.infrastructure.db.models.referral import ReferralEvent, ReferralReward, ReferralSettings
from app.infrastructure.db.models.user import User


class ReferralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_settings(self) -> ReferralSettings:
        stmt = select(ReferralSettings).order_by(ReferralSettings.id).limit(1)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = ReferralSettings()
            self._session.add(row)
            await self._session.flush()
            await self._session.refresh(row)
        return row

    async def update_settings(self, settings: ReferralSettings) -> ReferralSettings:
        settings.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(settings)
        return settings

    async def get_event_by_referred(self, referred_user_id: int) -> ReferralEvent | None:
        stmt = select(ReferralEvent).where(ReferralEvent.referred_user_id == referred_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_event(
        self,
        *,
        referrer_user_id: int,
        referred_user_id: int,
        source: str = "link",
    ) -> ReferralEvent:
        event = ReferralEvent(
            referrer_user_id=referrer_user_id,
            referred_user_id=referred_user_id,
            source=source,
            status=ReferralEventStatus.REGISTERED.value,
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def mark_event_paid(self, event: ReferralEvent, *, payment_request_id: int) -> ReferralEvent:
        event.status = ReferralEventStatus.PAID.value
        event.payment_request_id = payment_request_id
        event.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def mark_event_rewarded(self, event: ReferralEvent) -> ReferralEvent:
        event.status = ReferralEventStatus.REWARDED.value
        event.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def count_invited(self, referrer_user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(ReferralEvent)
            .where(ReferralEvent.referrer_user_id == referrer_user_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_paid_referrals(self, referrer_user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(ReferralEvent)
            .where(
                ReferralEvent.referrer_user_id == referrer_user_id,
                ReferralEvent.status.in_(
                    [
                        ReferralEventStatus.PAID.value,
                        ReferralEventStatus.REWARDED.value,
                    ]
                ),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_approved_payments(self, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(PaymentRequest)
            .where(
                PaymentRequest.user_id == user_id,
                PaymentRequest.status == PaymentRequestStatus.APPROVED.value,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_per_referral_reward(self, referred_user_id: int) -> ReferralReward | None:
        stmt = select(ReferralReward).where(
            ReferralReward.referred_user_id == referred_user_id,
            ReferralReward.reward_type == ReferralRewardType.PER_REFERRAL.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_milestone_reward(self, referrer_user_id: int) -> ReferralReward | None:
        stmt = select(ReferralReward).where(
            ReferralReward.referrer_user_id == referrer_user_id,
            ReferralReward.reward_type == ReferralRewardType.MILESTONE.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_reward(
        self,
        *,
        referrer_user_id: int,
        referred_user_id: int | None,
        payment_request_id: int | None,
        reward_type: str,
        reward_days: int,
        status: str = ReferralRewardStatus.PENDING.value,
    ) -> ReferralReward:
        reward = ReferralReward(
            referrer_user_id=referrer_user_id,
            referred_user_id=referred_user_id,
            payment_request_id=payment_request_id,
            reward_type=reward_type,
            reward_days=reward_days,
            status=status,
        )
        self._session.add(reward)
        await self._session.flush()
        await self._session.refresh(reward)
        return reward

    async def mark_reward_applied(
        self,
        reward: ReferralReward,
        *,
        vpn_account_id: int,
    ) -> ReferralReward:
        reward.status = ReferralRewardStatus.APPLIED.value
        reward.applied_vpn_account_id = vpn_account_id
        reward.applied_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(reward)
        return reward

    async def sum_reward_days(self, referrer_user_id: int, *, status: str) -> int:
        stmt = (
            select(func.coalesce(func.sum(ReferralReward.reward_days), 0))
            .where(
                ReferralReward.referrer_user_id == referrer_user_id,
                ReferralReward.status == status,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_pending_rewards(self, referrer_user_id: int) -> list[ReferralReward]:
        stmt = (
            select(ReferralReward)
            .where(
                ReferralReward.referrer_user_id == referrer_user_id,
                ReferralReward.status == ReferralRewardStatus.PENDING.value,
            )
            .order_by(ReferralReward.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_rewards_for_user(self, referrer_user_id: int, *, limit: int = 30) -> list[ReferralReward]:
        stmt = (
            select(ReferralReward)
            .where(ReferralReward.referrer_user_id == referrer_user_id)
            .order_by(ReferralReward.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent_events(self, *, limit: int = 30) -> list[ReferralEvent]:
        stmt = (
            select(ReferralEvent)
            .options(
                selectinload(ReferralEvent.referrer),
                selectinload(ReferralEvent.referred),
            )
            .order_by(ReferralEvent.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent_rewards(self, *, limit: int = 30) -> list[ReferralReward]:
        stmt = (
            select(ReferralReward)
            .options(selectinload(ReferralReward.referrer))
            .order_by(ReferralReward.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_admin_stats(self) -> dict[str, int]:
        registrations = await self._session.scalar(select(func.count()).select_from(ReferralEvent))
        paid = await self._session.scalar(
            select(func.count())
            .select_from(ReferralEvent)
            .where(
                ReferralEvent.status.in_(
                    [ReferralEventStatus.PAID.value, ReferralEventStatus.REWARDED.value]
                )
            )
        )
        applied = await self._session.scalar(
            select(func.count())
            .select_from(ReferralReward)
            .where(ReferralReward.status == ReferralRewardStatus.APPLIED.value)
        )
        pending = await self._session.scalar(
            select(func.count())
            .select_from(ReferralReward)
            .where(ReferralReward.status == ReferralRewardStatus.PENDING.value)
        )
        return {
            "registrations": int(registrations or 0),
            "paid": int(paid or 0),
            "applied": int(applied or 0),
            "pending": int(pending or 0),
        }

    async def top_referrers(self, *, limit: int = 10) -> list[tuple[int, int, User | None]]:
        stmt = (
            select(
                ReferralEvent.referrer_user_id,
                func.count().label("paid_count"),
            )
            .where(
                ReferralEvent.status.in_(
                    [ReferralEventStatus.PAID.value, ReferralEventStatus.REWARDED.value]
                )
            )
            .group_by(ReferralEvent.referrer_user_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        output: list[tuple[int, int, User | None]] = []
        for referrer_id, paid_count in rows:
            user = await self._session.get(User, referrer_id)
            output.append((int(referrer_id), int(paid_count), user))
        return output

    async def get_reward_by_id(self, reward_id: int) -> ReferralReward | None:
        stmt = select(ReferralReward).where(ReferralReward.id == reward_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
