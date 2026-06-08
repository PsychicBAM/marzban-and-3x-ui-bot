from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import VpnAccountStatus
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount

PAGE_SIZE = 10

STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_DISABLED = "disabled"
STATUS_DELETED = "deleted"


class AdminCustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_all_users(self) -> int:
        stmt = select(func.count()).select_from(User)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_latest_non_deleted_accounts(self) -> list[VpnAccount]:
        stmt = (
            select(VpnAccount)
            .where(
                VpnAccount.status != VpnAccountStatus.DELETED.value,
                VpnAccount.deleted_at.is_(None),
            )
            .order_by(VpnAccount.user_id, VpnAccount.created_at.desc())
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        seen: set[int] = set()
        latest: list[VpnAccount] = []
        for account in rows:
            if account.user_id in seen:
                continue
            seen.add(account.user_id)
            latest.append(account)
        return latest

    async def list_latest_deleted_only_user_ids(self) -> list[int]:
        non_deleted = await self.list_latest_non_deleted_accounts()
        users_with_active = {account.user_id for account in non_deleted}
        stmt = (
            select(VpnAccount.user_id)
            .where(
                or_(
                    VpnAccount.status == VpnAccountStatus.DELETED.value,
                    VpnAccount.deleted_at.is_not(None),
                )
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        deleted_user_ids = [row[0] for row in result.all()]
        return [user_id for user_id in deleted_user_ids if user_id not in users_with_active]

    async def get_latest_deleted_account_for_user(self, user_id: int) -> VpnAccount | None:
        stmt = (
            select(VpnAccount)
            .where(
                VpnAccount.user_id == user_id,
                or_(
                    VpnAccount.status == VpnAccountStatus.DELETED.value,
                    VpnAccount.deleted_at.is_not(None),
                ),
            )
            .order_by(VpnAccount.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_users_by_ids(self, user_ids: list[int]) -> dict[int, User]:
        if not user_ids:
            return {}
        stmt = select(User).where(User.id.in_(user_ids))
        result = await self._session.execute(stmt)
        return {user.id: user for user in result.scalars().all()}

    async def search_users(self, query: str, *, limit: int = 20) -> list[User]:
        q = query.strip()
        if not q:
            return []

        conditions = [
            User.username.ilike(f"%{q}%"),
            User.first_name.ilike(f"%{q}%"),
            User.last_name.ilike(f"%{q}%"),
            User.vpn_account_name.ilike(f"%{q}%"),
        ]
        if q.isdigit():
            conditions.append(User.telegram_id == int(q))

        stmt: Select[tuple[User]] = (
            select(User)
            .where(or_(*conditions))
            .options(selectinload(User.vpn_accounts))
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        users = list(result.scalars().unique().all())

        if not users:
            stmt = (
                select(User)
                .join(VpnAccount, VpnAccount.user_id == User.id)
                .where(VpnAccount.vpn_account_name.ilike(f"%{q}%"))
                .options(selectinload(User.vpn_accounts))
                .order_by(User.created_at.desc())
                .limit(limit)
            )
            result = await self._session.execute(stmt)
            users = list(result.scalars().unique().all())

        return users

    @staticmethod
    def categorize_account(account: VpnAccount, *, now: datetime) -> str:
        if account.status == VpnAccountStatus.DELETED.value or account.deleted_at is not None:
            return STATUS_DELETED
        if account.status == VpnAccountStatus.DISABLED.value:
            return STATUS_DISABLED
        expiry = account.expiry_date
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if account.status == VpnAccountStatus.EXPIRED.value:
            return STATUS_EXPIRED
        if expiry is not None and expiry <= now:
            return STATUS_EXPIRED
        return STATUS_ACTIVE
