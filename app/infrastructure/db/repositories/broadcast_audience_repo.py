from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import BroadcastTargetType
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.repositories.admin_customer_repo import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    AdminCustomerRepository,
)


class BroadcastAudienceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._customer_repo = AdminCustomerRepository(session)

    async def resolve_recipients(self, target_type: str) -> list[tuple[int, int]]:
        """Return (user_id, telegram_id) pairs eligible for promotional broadcast."""
        users = await self._load_promo_users()
        if not users:
            return []

        if target_type == BroadcastTargetType.ALL.value:
            return users

        if target_type == BroadcastTargetType.PROMO_ENABLED.value:
            return users

        accounts = await self._load_accounts_for_users([user_id for user_id, _ in users])
        by_user = self._group_accounts_by_user(accounts)
        now = datetime.now(UTC)

        matched: list[tuple[int, int]] = []
        for user_id, telegram_id in users:
            user_accounts = by_user.get(user_id, [])
            if self._matches_target(target_type, user_accounts, now=now):
                matched.append((user_id, telegram_id))
        return matched

    async def count_recipients(self, target_type: str) -> int:
        return len(await self.resolve_recipients(target_type))

    async def _load_promo_users(self) -> list[tuple[int, int]]:
        stmt = (
            select(User.id, User.telegram_id)
            .where(User.promo_enabled.is_(True), User.telegram_id > 0)
            .order_by(User.id)
        )
        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def _load_accounts_for_users(self, user_ids: list[int]) -> list[VpnAccount]:
        if not user_ids:
            return []
        stmt = (
            select(VpnAccount)
            .where(
                VpnAccount.user_id.in_(user_ids),
                VpnAccount.deleted_at.is_(None),
            )
            .order_by(VpnAccount.user_id, VpnAccount.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _group_accounts_by_user(accounts: list[VpnAccount]) -> dict[int, list[VpnAccount]]:
        grouped: dict[int, list[VpnAccount]] = {}
        for account in accounts:
            grouped.setdefault(account.user_id, []).append(account)
        return grouped

    def _matches_target(
        self,
        target_type: str,
        accounts: list[VpnAccount],
        *,
        now: datetime,
    ) -> bool:
        categories = [
            self._customer_repo.categorize_account(account, now=now) for account in accounts
        ]
        has_active = STATUS_ACTIVE in categories
        has_expired = STATUS_EXPIRED in categories
        has_expiring_soon = any(
            self._customer_repo.is_expiring_soon(account, now=now) for account in accounts
        )

        if target_type == BroadcastTargetType.ACTIVE_VPN.value:
            return has_active
        if target_type == BroadcastTargetType.EXPIRED_VPN.value:
            return has_expired and not has_active
        if target_type == BroadcastTargetType.NO_ACTIVE_VPN.value:
            return not has_active
        if target_type == BroadcastTargetType.EXPIRING_SOON.value:
            return has_expiring_soon
        return False
