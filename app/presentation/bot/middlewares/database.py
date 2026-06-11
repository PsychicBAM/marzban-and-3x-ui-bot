from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.application.services.admin_log_service import AdminLogService
from app.application.services.broadcast_sender_service import BroadcastSenderService
from app.application.services.broadcast_service import BroadcastService
from app.application.services.expiry_notification_service import ExpiryNotificationService
from app.application.services.free_plan_activation_service import FreePlanActivationService
from app.application.services.payment_approval_service import PaymentApprovalService
from app.application.services.promo_activation_service import PromoActivationService
from app.application.services.promo_code_service import PromoCodeService
from app.application.services.payment_request_service import PaymentRequestService
from app.application.services.plan_service import PlanService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.application.services.qr_code_service import QrCodeService
from app.application.services.settings_service import SettingsService
from app.application.services.statistics_service import StatisticsService
from app.application.services.system_status_service import SystemStatusService
from app.application.services.customer_history_service import CustomerHistoryService
from app.application.services.daily_report_service import DailyReportService
from app.application.services.support_ticket_service import SupportTicketService
from app.application.services.referral_service import ReferralService
from app.application.services.subscription_purchase_service import SubscriptionPurchaseService
from app.application.services.user_service import UserService
from app.config.settings import Settings, get_settings
from app.infrastructure.db.session import session_scope
from app.infrastructure.db.uow import UnitOfWork
from app.infrastructure.integrations.factory import (
    create_admin_customer_service,
    create_customer_vpn_service,
    create_manual_key_flow_service,
    create_manual_provisioning_service,
    create_vpn_provisioning_service,
)


class DatabaseMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings: Settings = data.get("settings") or get_settings()
        async with session_scope() as session:
            uow = UnitOfWork(session)
            data["uow"] = uow
            settings_service = SettingsService(uow, settings)
            data["settings_service"] = settings_service
            data["plan_service"] = PlanService(uow, settings)
            data["payment_request_service"] = PaymentRequestService(uow, settings, settings_service)
            data["subscription_purchase_service"] = SubscriptionPurchaseService(uow)
            admin_log_service = AdminLogService(uow)
            data["admin_log_service"] = admin_log_service
            provisioning_service = create_vpn_provisioning_service(uow, settings)
            data["vpn_provisioning_service"] = provisioning_service
            data["free_plan_activation_service"] = FreePlanActivationService(
                uow,
                settings,
                provisioning_service,
                admin_log_service,
            )
            customer_vpn_service = create_customer_vpn_service(uow, settings)
            data["customer_vpn_service"] = customer_vpn_service
            promo_code_service = PromoCodeService(uow, admin_log_service)
            data["promo_code_service"] = promo_code_service
            qr_code_service = QrCodeService()
            data["qr_code_service"] = qr_code_service
            provisioning_notification_service = ProvisioningNotificationService(qr_code_service)
            data["provisioning_notification_service"] = provisioning_notification_service
            data["admin_customer_service"] = create_admin_customer_service(
                uow,
                settings,
                customer_vpn_service=customer_vpn_service,
                admin_log_service=admin_log_service,
                provisioning_notification_service=provisioning_notification_service,
            )
            referral_service = ReferralService(
                uow,
                settings,
                admin_log_service,
                data["admin_customer_service"],
            )
            data["referral_service"] = referral_service
            data["user_service"] = UserService(uow, settings, referral_service)
            data["payment_approval_service"] = PaymentApprovalService(
                uow,
                provisioning_service,
                admin_log_service,
                promo_code_service=promo_code_service,
                referral_service=referral_service,
            )
            data["promo_activation_service"] = PromoActivationService(
                uow,
                settings,
                provisioning_service,
                admin_log_service,
                promo_code_service,
                referral_service=referral_service,
            )
            data["expiry_notification_service"] = ExpiryNotificationService(
                uow=uow,
                settings=settings,
                settings_service=settings_service,
                admin_log_service=admin_log_service,
            )
            data["statistics_service"] = StatisticsService(uow, settings)
            data["system_status_service"] = SystemStatusService(uow, settings)
            data["customer_history_service"] = CustomerHistoryService(uow)
            data["support_ticket_service"] = SupportTicketService(uow, settings, admin_log_service)
            data["daily_report_service"] = DailyReportService(
                uow,
                settings,
                data["system_status_service"],
                admin_log_service,
            )
            data["manual_provisioning_service"] = create_manual_provisioning_service(
                uow,
                settings,
                admin_log_service,
            )
            data["manual_key_flow_service"] = create_manual_key_flow_service(uow, data["plan_service"])
            broadcast_service = BroadcastService(uow, admin_log_service)
            data["broadcast_service"] = broadcast_service
            data["broadcast_sender_service"] = BroadcastSenderService(broadcast_service)
            return await handler(event, data)
