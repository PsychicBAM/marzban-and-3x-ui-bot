from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.enums import ProvisionAction, VpnAccountStatus
from app.infrastructure.db.models.vpn_account import VpnAccount


class ExpiryCalculator:
    """Calculate VPN expiry according to business rules."""

    @staticmethod
    def calculate(
        *,
        now: datetime,
        duration_days: int,
        account: VpnAccount | None,
    ) -> tuple[datetime, ProvisionAction]:
        delta = timedelta(days=duration_days)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        if account is None or ExpiryCalculator._is_deleted(account):
            return now + delta, ProvisionAction.CREATE_NEW

        expiry = account.expiry_date
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)

        if account.status == VpnAccountStatus.DISABLED.value:
            if expiry and expiry > now:
                return expiry + delta, ProvisionAction.RENEW_REENABLE_DISABLED
            return now + delta, ProvisionAction.RENEW_FROM_NOW

        if (
            account.status == VpnAccountStatus.ACTIVE.value
            and expiry is not None
            and expiry > now
        ):
            return expiry + delta, ProvisionAction.RENEW_ACTIVE

        return now + delta, ProvisionAction.RENEW_FROM_NOW

    @staticmethod
    def _is_deleted(account: VpnAccount) -> bool:
        return (
            account.status == VpnAccountStatus.DELETED.value
            or account.deleted_at is not None
        )

    @staticmethod
    def requires_new_db_record(account: VpnAccount | None) -> bool:
        if account is None:
            return True
        return ExpiryCalculator._is_deleted(account)
