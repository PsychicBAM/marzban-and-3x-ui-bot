from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.statistics import (
    ExpiringSoonCounts,
    PaymentStatusCounts,
    RevenueSummary,
    UserVpnCounts,
    VpnAccountCounts,
)
from app.domain.enums import PaymentRequestStatus, VpnAccountStatus
from app.infrastructure.db.models.payment_request import PaymentRequest
from app.infrastructure.db.models.plan import Plan
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.repositories.admin_customer_repo import AdminCustomerRepository


class StatisticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._customer_repo = AdminCustomerRepository(session)

    async def count_users(self) -> int:
        stmt = select(func.count()).select_from(User)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_user_vpn_counts(self, *, now: datetime) -> UserVpnCounts:
        total = await self.count_users()
        latest = await self._customer_repo.list_latest_non_deleted_accounts()
        counts = {"active": 0, "expired": 0, "disabled": 0}
        for account in latest:
            category = self._customer_repo.categorize_account(account, now=now)
            if category in counts:
                counts[category] += 1
        deleted_ids = await self._customer_repo.list_latest_deleted_only_user_ids()
        return UserVpnCounts(
            total_users=total,
            active_vpn=counts["active"],
            expired_vpn=counts["expired"],
            disabled_vpn=counts["disabled"],
            deleted_vpn=len(deleted_ids),
        )

    async def get_payment_status_counts(self) -> PaymentStatusCounts:
        stmt = (
            select(PaymentRequest.status, func.count())
            .group_by(PaymentRequest.status)
        )
        result = await self._session.execute(stmt)
        raw = {row[0]: int(row[1]) for row in result.all()}
        return PaymentStatusCounts(
            pending=raw.get(PaymentRequestStatus.PENDING.value, 0),
            approved=raw.get(PaymentRequestStatus.APPROVED.value, 0),
            rejected=raw.get(PaymentRequestStatus.REJECTED.value, 0),
            provisioning_failed=raw.get(PaymentRequestStatus.PROVISIONING_FAILED.value, 0),
            provisioning_partial=raw.get(PaymentRequestStatus.PROVISIONING_PARTIAL.value, 0),
        )

    async def get_revenue_summary(
        self,
        *,
        start_today_utc: datetime,
        start_month_utc: datetime,
    ) -> RevenueSummary:
        approved_status = PaymentRequestStatus.APPROVED.value

        total_stmt = (
            select(func.coalesce(func.sum(PaymentRequest.amount), 0))
            .where(PaymentRequest.status == approved_status)
        )
        today_stmt = (
            select(func.coalesce(func.sum(PaymentRequest.amount), 0))
            .where(
                PaymentRequest.status == approved_status,
                PaymentRequest.approved_at.is_not(None),
                PaymentRequest.approved_at >= start_today_utc,
            )
        )
        month_stmt = (
            select(func.coalesce(func.sum(PaymentRequest.amount), 0))
            .where(
                PaymentRequest.status == approved_status,
                PaymentRequest.approved_at.is_not(None),
                PaymentRequest.approved_at >= start_month_utc,
            )
        )

        total = Decimal(str((await self._session.execute(total_stmt)).scalar_one()))
        today = Decimal(str((await self._session.execute(today_stmt)).scalar_one()))
        month = Decimal(str((await self._session.execute(month_stmt)).scalar_one()))

        by_plan_stmt = (
            select(Plan.name, func.coalesce(func.sum(PaymentRequest.amount), 0))
            .join(Plan, Plan.id == PaymentRequest.plan_id)
            .where(PaymentRequest.status == approved_status)
            .group_by(Plan.name)
            .order_by(func.sum(PaymentRequest.amount).desc())
        )
        plan_result = await self._session.execute(by_plan_stmt)
        by_plan = [(row[0], Decimal(str(row[1]))) for row in plan_result.all()]

        return RevenueSummary(total=total, today=today, month=month, by_plan=by_plan)

    async def get_revenue_for_period(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime | None = None,
    ) -> tuple[Decimal, list[tuple[str, Decimal]], int]:
        approved_status = PaymentRequestStatus.APPROVED.value
        conditions = [
            PaymentRequest.status == approved_status,
            PaymentRequest.approved_at.is_not(None),
            PaymentRequest.approved_at >= start_utc,
        ]
        if end_utc is not None:
            conditions.append(PaymentRequest.approved_at < end_utc)

        sum_stmt = select(func.coalesce(func.sum(PaymentRequest.amount), 0)).where(*conditions)
        count_stmt = select(func.count()).select_from(PaymentRequest).where(*conditions)
        by_plan_stmt = (
            select(Plan.name, func.coalesce(func.sum(PaymentRequest.amount), 0))
            .join(Plan, Plan.id == PaymentRequest.plan_id)
            .where(*conditions)
            .group_by(Plan.name)
            .order_by(func.sum(PaymentRequest.amount).desc())
        )

        total = Decimal(str((await self._session.execute(sum_stmt)).scalar_one()))
        count = int((await self._session.execute(count_stmt)).scalar_one())
        plan_result = await self._session.execute(by_plan_stmt)
        by_plan = [(row[0], Decimal(str(row[1]))) for row in plan_result.all()]
        return total, by_plan, count

    async def get_vpn_account_counts(self) -> VpnAccountCounts:
        status_stmt = (
            select(VpnAccount.status, func.count())
            .group_by(VpnAccount.status)
        )
        result = await self._session.execute(status_stmt)
        raw = {row[0]: int(row[1]) for row in result.all()}

        total_stmt = select(func.count()).select_from(VpnAccount)
        marzban_stmt = select(func.count()).select_from(VpnAccount).where(
            VpnAccount.marzban_username.is_not(None),
            VpnAccount.marzban_username != "",
        )
        xui_stmt = select(func.count()).select_from(VpnAccount).where(
            VpnAccount.xui_email.is_not(None),
            VpnAccount.xui_email != "",
        )

        total = int((await self._session.execute(total_stmt)).scalar_one())
        marzban = int((await self._session.execute(marzban_stmt)).scalar_one())
        xui = int((await self._session.execute(xui_stmt)).scalar_one())

        return VpnAccountCounts(
            total=total,
            active=raw.get(VpnAccountStatus.ACTIVE.value, 0),
            expired=raw.get(VpnAccountStatus.EXPIRED.value, 0),
            disabled=raw.get(VpnAccountStatus.DISABLED.value, 0),
            deleted=raw.get(VpnAccountStatus.DELETED.value, 0),
            marzban=marzban,
            xui=xui,
        )

    async def count_expiring_soon(self, *, now: datetime) -> ExpiringSoonCounts:
        accounts = await self._session.execute(
            select(VpnAccount).where(
                VpnAccount.status == VpnAccountStatus.ACTIVE.value,
                VpnAccount.deleted_at.is_(None),
                VpnAccount.expiry_date.is_not(None),
            )
        )
        counts = {1: 0, 3: 0, 7: 0}
        for account in accounts.scalars().all():
            expiry = account.expiry_date
            if expiry is None:
                continue
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            days_left = (expiry.date() - now.date()).days
            if days_left in counts:
                counts[days_left] += 1
        return ExpiringSoonCounts(
            in_1_day=counts[1],
            in_3_days=counts[3],
            in_7_days=counts[7],
        )
