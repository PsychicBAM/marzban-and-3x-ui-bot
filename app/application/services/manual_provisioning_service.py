from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.application.dto.manual_provision import ManualProvisionRequest, ManualProvisionResult, ProvisionProfile
from app.application.dto.provisioning import PanelProvisionResult
from app.application.exceptions import VpnPanelConflictError, VpnPanelError, VpnProvisioningError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.expiry_calculator import ExpiryCalculator
from app.application.services.panel_provisioner import PanelProvisioner
from app.config.settings import Settings
from app.domain.enums import AdminActionType, IssuingMode, PanelType, ProvisionAction, VpnAccountStatus
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

MANUAL_SYSTEM_TELEGRAM_ID = 0
MANUAL_SYSTEM_USERNAME = "manual_vpn_system"


class ManualProvisioningService:
    """Admin-initiated VPN key creation without payment request."""

    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        panel_provisioner: PanelProvisioner,
        admin_log_service: AdminLogService,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._panels = panel_provisioner
        self._admin_log = admin_log_service

    async def resolve_standalone_user_id(self) -> int:
        user = await self._uow.users.get_by_telegram_id(MANUAL_SYSTEM_TELEGRAM_ID)
        if user is not None:
            return user.id
        created = await self._uow.users.create(
            telegram_id=MANUAL_SYSTEM_TELEGRAM_ID,
            username=MANUAL_SYSTEM_USERNAME,
            first_name="Manual",
            last_name="VPN",
            is_admin=False,
        )
        return created.id

    async def check_name_conflicts(self, account_name: str, issuing_mode: str) -> list[str]:
        return await self._panels.check_name_conflicts(account_name, issuing_mode)

    async def create_manual_vpn(
        self,
        request: ManualProvisionRequest,
        *,
        admin_telegram_id: int,
    ) -> ManualProvisionResult:
        user = await self._uow.users.get_by_id(request.user_id)
        if user is None:
            raise VpnProvisioningError("Пользователь не найден.")

        panel_list = self._panels_for_mode(request.profile.issuing_mode)
        if not panel_list:
            raise VpnProvisioningError("Выбранный режим выдачи недоступен в настройках панелей.")

        now = datetime.now(UTC)
        renewal_candidate = await self._uow.vpn_accounts.get_renewal_candidate(user.id)
        create_new_db_record = True
        existing_for_panels: VpnAccount | None = None

        if request.extend_existing and renewal_candidate is not None:
            if (
                renewal_candidate.status == VpnAccountStatus.DELETED.value
                or renewal_candidate.deleted_at is not None
            ):
                expiry_at, action = ExpiryCalculator.calculate(
                    now=now,
                    duration_days=request.profile.duration_days,
                    account=None,
                )
                create_new_db_record = True
                existing_for_panels = None
            else:
                expiry_at, action = ExpiryCalculator.calculate(
                    now=now,
                    duration_days=request.profile.duration_days,
                    account=renewal_candidate,
                )
                create_new_db_record = False
                existing_for_panels = renewal_candidate
        else:
            expiry_at = now + timedelta(days=request.profile.duration_days)
            action = ProvisionAction.CREATE_NEW
            existing_for_panels = None
            create_new_db_record = True

        panel_results: list[PanelProvisionResult] = []
        marzban_data: dict[str, str | None] = {}
        xui_data: dict[str, str | None] = {}
        create_new_panel = create_new_db_record or existing_for_panels is None
        reenable = action == ProvisionAction.RENEW_REENABLE_DISABLED

        for panel in panel_list:
            try:
                if panel == PanelType.MARZBAN.value:
                    result = await self._panels.provision_marzban(
                        account_name=request.account_name,
                        expiry_at=expiry_at,
                        profile=request.profile,
                        existing=existing_for_panels,
                        create_new_panel_account=create_new_panel,
                        reenable=reenable,
                    )
                    marzban_data = {
                        "username": request.account_name,
                        "subscription_url": result.subscription_url,
                        "status": "active",
                    }
                elif panel == PanelType.XUI.value:
                    result = await self._panels.provision_xui(
                        account_name=request.account_name,
                        expiry_at=expiry_at,
                        profile=request.profile,
                        existing=existing_for_panels,
                        create_new_panel_account=create_new_panel,
                        reenable=reenable,
                    )
                    xui_data = {
                        "client_uuid": result.external_id,
                        "email": request.account_name,
                        "subscription_url": result.subscription_url,
                        "status": "active",
                    }
                else:
                    continue
                panel_results.append(result)
            except VpnPanelConflictError as exc:
                panel_results.append(
                    PanelProvisionResult(
                        panel=panel,
                        success=False,
                        created=False,
                        error=f"Конфликт имени: {exc.message}",
                    ),
                )
            except VpnPanelError as exc:
                logger.warning("Manual panel provisioning failed", extra={"panel": panel, "error": exc.message})
                panel_results.append(
                    PanelProvisionResult(
                        panel=panel,
                        success=False,
                        created=False,
                        error=exc.message,
                    ),
                )

        successes = [item for item in panel_results if item.success]
        failures = [item for item in panel_results if not item.success]
        if not successes:
            errors = "; ".join(item.error or "ошибка" for item in failures)
            raise VpnProvisioningError(f"Не удалось создать VPN: {errors}")

        status = VpnAccountStatus.ACTIVE.value
        if create_new_db_record or existing_for_panels is None:
            vpn_account = await self._uow.vpn_accounts.create(
                user_id=user.id,
                plan_id=request.profile.plan_id,
                vpn_account_name=request.account_name,
                expiry_date=expiry_at,
                traffic_limit_gb=request.profile.traffic_limit_gb,
                ip_limit=request.profile.ip_limit,
                status=status,
            )
        else:
            vpn_account = existing_for_panels

        vpn_account = await self._uow.vpn_accounts.update_provision(
            vpn_account,
            plan_id=request.profile.plan_id,
            expiry_date=expiry_at,
            traffic_limit_gb=request.profile.traffic_limit_gb,
            ip_limit=request.profile.ip_limit,
            status=status,
            marzban_username=marzban_data.get("username"),
            marzban_subscription_url=marzban_data.get("subscription_url"),
            marzban_status=marzban_data.get("status"),
            xui_client_uuid=xui_data.get("client_uuid"),
            xui_email=xui_data.get("email"),
            xui_subscription_url=xui_data.get("subscription_url"),
            xui_status=xui_data.get("status"),
        )

        if request.mode == "existing" and user.vpn_account_name != request.account_name:
            user.vpn_account_name = request.account_name

        subscription_links = {
            "Marzban": marzban_data.get("subscription_url") or "",
            "3x-ui": xui_data.get("subscription_url") or "",
        }
        subscription_links = {key: value for key, value in subscription_links.items() if value}

        partial = bool(failures)
        result = ManualProvisionResult(
            success=not partial,
            partial=partial,
            vpn_account_id=vpn_account.id,
            vpn_account_name=request.account_name,
            expiry_at=expiry_at,
            action=action,
            panel_results=panel_results,
            subscription_links=subscription_links,
            profile=request.profile,
            target_telegram_id=request.target_telegram_id,
        )

        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.MANUAL_VPN_CREATED,
            details={
                "mode": request.mode,
                "user_id": user.id,
                "vpn_account_id": vpn_account.id,
                "account_name": request.account_name,
                "partial": partial,
                "panels": [item.panel for item in successes],
                "failures": [item.panel for item in failures],
            },
        )
        return result

    def _panels_for_mode(self, issuing_mode: str) -> list[str]:
        if issuing_mode == IssuingMode.MARZBAN.value:
            return [PanelType.MARZBAN.value] if self._settings.marzban_enabled else []
        if issuing_mode == IssuingMode.XUI.value:
            return [PanelType.XUI.value] if self._settings.xui_enabled else []
        panels: list[str] = []
        if self._settings.marzban_enabled:
            panels.append(PanelType.MARZBAN.value)
        if self._settings.xui_enabled:
            panels.append(PanelType.XUI.value)
        return panels
