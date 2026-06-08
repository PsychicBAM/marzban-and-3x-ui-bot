from __future__ import annotations

from app.application.services.admin_customer_service import AdminCustomerService
from app.application.services.admin_log_service import AdminLogService
from app.application.services.customer_vpn_service import CustomerVpnService
from app.application.services.manual_key_flow_service import ManualKeyFlowService
from app.application.services.manual_provisioning_service import ManualProvisioningService
from app.application.services.panel_provisioner import PanelProvisioner
from app.application.services.plan_service import PlanService
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.application.services.vpn_provisioning_service import VpnProvisioningService
from app.config.settings import Settings
from app.infrastructure.db.uow import UnitOfWork
from app.infrastructure.integrations.marzban.client import MarzbanApiClient
from app.infrastructure.integrations.marzban.service import MarzbanService
from app.infrastructure.integrations.xui.client import XuiApiClient
from app.infrastructure.integrations.xui.service import XuiService


def create_marzban_service(settings: Settings) -> MarzbanService | None:
    if not settings.marzban_enabled:
        return None
    client = MarzbanApiClient(settings)
    return MarzbanService(client, settings)


def create_xui_service(settings: Settings) -> XuiService | None:
    if not settings.xui_enabled:
        return None
    client = XuiApiClient(settings)
    return XuiService(client, settings)


def create_panel_provisioner(settings: Settings) -> PanelProvisioner:
    return PanelProvisioner(
        settings=settings,
        marzban=create_marzban_service(settings),
        xui=create_xui_service(settings),
    )


def create_manual_provisioning_service(
    uow: UnitOfWork,
    settings: Settings,
    admin_log_service: AdminLogService,
) -> ManualProvisioningService:
    return ManualProvisioningService(
        uow=uow,
        settings=settings,
        panel_provisioner=create_panel_provisioner(settings),
        admin_log_service=admin_log_service,
    )


def create_manual_key_flow_service(uow: UnitOfWork, plan_service: PlanService) -> ManualKeyFlowService:
    return ManualKeyFlowService(uow=uow, plan_service=plan_service)


def create_vpn_provisioning_service(uow: UnitOfWork, settings: Settings) -> VpnProvisioningService:
    return VpnProvisioningService(
        uow=uow,
        settings=settings,
        marzban=create_marzban_service(settings),
        xui=create_xui_service(settings),
    )


def create_customer_vpn_service(uow: UnitOfWork, settings: Settings) -> CustomerVpnService:
    return CustomerVpnService(
        uow=uow,
        settings=settings,
        marzban=create_marzban_service(settings),
        xui=create_xui_service(settings),
    )


def create_admin_customer_service(
    uow: UnitOfWork,
    settings: Settings,
    *,
    customer_vpn_service: CustomerVpnService,
    admin_log_service: AdminLogService,
    provisioning_notification_service: ProvisioningNotificationService,
) -> AdminCustomerService:
    return AdminCustomerService(
        uow=uow,
        settings=settings,
        customer_vpn_service=customer_vpn_service,
        admin_log_service=admin_log_service,
        notification_service=provisioning_notification_service,
        marzban=create_marzban_service(settings),
        xui=create_xui_service(settings),
    )
