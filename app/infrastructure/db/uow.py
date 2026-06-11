from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.repositories.admin_customer_repo import AdminCustomerRepository
from app.infrastructure.db.repositories.admin_log_repo import AdminLogRepository
from app.infrastructure.db.repositories.admin_report_settings_repo import AdminReportSettingsRepository
from app.infrastructure.db.repositories.broadcast_audience_repo import BroadcastAudienceRepository
from app.infrastructure.db.repositories.broadcast_repo import BroadcastRepository
from app.infrastructure.db.repositories.customer_event_repo import CustomerEventRepository
from app.infrastructure.db.repositories.promo_code_repo import PromoCodeRepository
from app.infrastructure.db.repositories.referral_repo import ReferralRepository
from app.infrastructure.db.repositories.notification_repo import NotificationRepository
from app.infrastructure.db.repositories.payment_request_repo import PaymentRequestRepository
from app.infrastructure.db.repositories.plan_repo import PlanRepository
from app.infrastructure.db.repositories.setting_repo import SettingRepository
from app.infrastructure.db.repositories.statistics_repo import StatisticsRepository
from app.infrastructure.db.repositories.support_ticket_repo import SupportTicketRepository
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.infrastructure.db.repositories.vpn_account_repo import VpnAccountRepository


class UnitOfWork:
    """Groups repositories around a single AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.admin_customers = AdminCustomerRepository(session)
        self.plans = PlanRepository(session)
        self.vpn_accounts = VpnAccountRepository(session)
        self.payment_requests = PaymentRequestRepository(session)
        self.notifications = NotificationRepository(session)
        self.settings = SettingRepository(session)
        self.admin_logs = AdminLogRepository(session)
        self.statistics = StatisticsRepository(session)
        self.broadcasts = BroadcastRepository(session)
        self.broadcast_audience = BroadcastAudienceRepository(session)
        self.promo_codes = PromoCodeRepository(session)
        self.referrals = ReferralRepository(session)
        self.customer_events = CustomerEventRepository(session)
        self.support_tickets = SupportTicketRepository(session)
        self.admin_report_settings = AdminReportSettingsRepository(session)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
