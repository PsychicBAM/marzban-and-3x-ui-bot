from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import VpnAccountStatus
from app.infrastructure.db.models.vpn_account import VpnAccount


class VpnAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, account_id: int) -> VpnAccount | None:
        stmt = select(VpnAccount).where(VpnAccount.id == account_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user_id(self, user_id: int, *, include_deleted: bool = False) -> list[VpnAccount]:
        stmt = select(VpnAccount).where(VpnAccount.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(VpnAccount.status != VpnAccountStatus.DELETED.value)
        stmt = stmt.order_by(VpnAccount.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_user(self, user_id: int) -> VpnAccount | None:
        stmt = (
            select(VpnAccount)
            .where(VpnAccount.user_id == user_id)
            .order_by(VpnAccount.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_active_vpn(self, user_id: int) -> bool:
        now = datetime.now(UTC)
        accounts = await self.list_by_user_id(user_id, include_deleted=False)
        for account in accounts:
            if account.status != VpnAccountStatus.ACTIVE.value:
                continue
            expiry = account.expiry_date
            if expiry is None:
                return True
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            if expiry > now:
                return True
        return False

    async def get_renewal_candidate(
        self,
        user_id: int,
        *,
        vpn_account_id: int | None = None,
    ) -> VpnAccount | None:
        if vpn_account_id is not None:
            account = await self.get_by_id(vpn_account_id)
            if account is None or account.user_id != user_id:
                return None
            if account.status == VpnAccountStatus.DELETED.value or account.deleted_at is not None:
                return None
            return account

        accounts = await self.list_by_user_id(user_id, include_deleted=False)
        return accounts[0] if accounts else None

    async def create(
        self,
        *,
        user_id: int,
        plan_id: int | None,
        vpn_account_name: str,
        expiry_date: datetime | None,
        traffic_limit_gb: int,
        ip_limit: int,
        status: str = VpnAccountStatus.ACTIVE.value,
    ) -> VpnAccount:
        account = VpnAccount(
            user_id=user_id,
            plan_id=plan_id,
            vpn_account_name=vpn_account_name,
            expiry_date=expiry_date,
            traffic_limit_gb=traffic_limit_gb,
            ip_limit=ip_limit,
            status=status,
        )
        self._session.add(account)
        await self._session.flush()
        await self._session.refresh(account)
        return account

    async def update_provision(
        self,
        account: VpnAccount,
        *,
        plan_id: int | None,
        expiry_date: datetime | None,
        traffic_limit_gb: int,
        ip_limit: int,
        status: str,
        marzban_username: str | None = None,
        marzban_subscription_url: str | None = None,
        marzban_status: str | None = None,
        xui_client_uuid: str | None = None,
        xui_email: str | None = None,
        xui_subscription_url: str | None = None,
        xui_status: str | None = None,
    ) -> VpnAccount:
        account.plan_id = plan_id
        account.expiry_date = expiry_date
        account.traffic_limit_gb = traffic_limit_gb
        account.ip_limit = ip_limit
        account.status = status
        if marzban_username is not None:
            account.marzban_username = marzban_username
        if marzban_subscription_url is not None:
            account.marzban_subscription_url = marzban_subscription_url
        if marzban_status is not None:
            account.marzban_status = marzban_status
        if xui_client_uuid is not None:
            account.xui_client_uuid = xui_client_uuid
        if xui_email is not None:
            account.xui_email = xui_email
        if xui_subscription_url is not None:
            account.xui_subscription_url = xui_subscription_url
        if xui_status is not None:
            account.xui_status = xui_status
        await self._session.flush()
        await self._session.refresh(account)
        return account

    async def list_active_for_expiry_notifications(self) -> list[VpnAccount]:
        stmt = (
            select(VpnAccount)
            .where(
                VpnAccount.status == VpnAccountStatus.ACTIVE.value,
                VpnAccount.deleted_at.is_(None),
                VpnAccount.expiry_date.is_not(None),
            )
            .options(selectinload(VpnAccount.user))
            .order_by(VpnAccount.expiry_date.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def soft_delete(self, account: VpnAccount, *, clear_customer_links: bool = True) -> VpnAccount:
        """Soft-delete VPN account and optionally clear customer-facing links."""
        account.status = VpnAccountStatus.DELETED.value
        account.deleted_at = datetime.now(UTC)
        if clear_customer_links:
            account.marzban_subscription_url = None
            account.xui_subscription_url = None
        await self._session.flush()
        await self._session.refresh(account)
        return account

    async def update_admin_state(
        self,
        account: VpnAccount,
        *,
        status: str | None = None,
        expiry_date: datetime | None = None,
        ip_limit: int | None = None,
        traffic_used_bytes: int | None = None,
        marzban_status: str | None = None,
        xui_status: str | None = None,
        marzban_subscription_url: str | None = None,
        xui_subscription_url: str | None = None,
    ) -> VpnAccount:
        if status is not None:
            account.status = status
        if expiry_date is not None:
            account.expiry_date = expiry_date
        if ip_limit is not None:
            account.ip_limit = ip_limit
        if traffic_used_bytes is not None:
            account.traffic_used_bytes = traffic_used_bytes
        if marzban_status is not None:
            account.marzban_status = marzban_status
        if xui_status is not None:
            account.xui_status = xui_status
        if marzban_subscription_url is not None:
            account.marzban_subscription_url = marzban_subscription_url
        if xui_subscription_url is not None:
            account.xui_subscription_url = xui_subscription_url
        await self._session.flush()
        await self._session.refresh(account)
        return account
