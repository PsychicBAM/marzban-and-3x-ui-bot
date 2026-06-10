from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto.provisioning import PanelProvisionResult, ProvisioningResult
from app.application.exceptions import (
    VpnPanelConflictError,
    VpnPanelError,
    VpnProvisioningError,
)
from app.application.services.expiry_calculator import ExpiryCalculator
from app.application.utils.vpn_username import normalize_from_telegram_username, normalize_vpn_account_name
from app.config.settings import Settings
from app.domain.enums import IssuingMode, PanelType, PaymentRequestType, ProvisionAction, VpnAccountStatus
from app.infrastructure.db.models.payment_request import PaymentRequest
from app.infrastructure.db.models.plan import Plan
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.uow import UnitOfWork
from app.infrastructure.integrations.marzban.service import MarzbanService
from app.infrastructure.integrations.xui.service import XuiService

logger = logging.getLogger(__name__)

MISSING_USERNAME_ERROR = (
    "У клиента нет username. Нужно добавить ручной ввод имени VPN на следующем этапе."
)


class VpnProvisioningService:
    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        marzban: MarzbanService | None,
        xui: XuiService | None,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._marzban = marzban
        self._xui = xui

    async def provision_for_payment_request(self, request: PaymentRequest) -> ProvisioningResult:
        user = request.user
        plan = request.plan
        if user is None or plan is None:
            raise VpnProvisioningError("Данные заявки неполные.")

        now = datetime.now(UTC)
        is_renewal = request.request_type == PaymentRequestType.RENEWAL.value
        is_separate_purchase = (
            request.request_type == PaymentRequestType.PURCHASE.value
            and bool(request.target_vpn_account_name)
            and request.vpn_account_id is None
        )

        if is_renewal or request.vpn_account_id is not None:
            renewal_candidate = await self._uow.vpn_accounts.get_renewal_candidate(
                user.id,
                vpn_account_id=request.vpn_account_id,
            )
            if renewal_candidate is None:
                raise VpnProvisioningError("VPN для продления не найден.")
            account_name = renewal_candidate.vpn_account_name
            new_db_record = False
        elif is_separate_purchase:
            renewal_candidate = None
            account_name = normalize_vpn_account_name(request.target_vpn_account_name or "")
            if await self._uow.vpn_accounts.exists_by_name(account_name):
                raise VpnProvisioningError(f"Имя VPN '{account_name}' уже занято.")
            new_db_record = True
        else:
            renewal_candidate = await self._uow.vpn_accounts.get_renewal_candidate(user.id)
            if renewal_candidate is not None and await self._uow.vpn_accounts.has_active_vpn(user.id):
                raise VpnProvisioningError(
                    "У клиента уже есть активный VPN. Нужна заявка на продление или отдельную подписку.",
                )
            account_name = (
                renewal_candidate.vpn_account_name
                if renewal_candidate is not None
                else self._resolve_account_name(user)
            )
            new_db_record = ExpiryCalculator.requires_new_db_record(renewal_candidate)

        duration_days = plan.duration_days + (request.extra_days_from_promo or 0)
        expiry_at, action = ExpiryCalculator.calculate(
            now=now,
            duration_days=duration_days,
            account=renewal_candidate,
        )

        panels = self._panels_for_plan(plan)
        if not panels:
            raise VpnProvisioningError("Тариф не настроен для выдачи VPN.")

        panel_results: list[PanelProvisionResult] = []
        marzban_data: dict[str, str | None] = {}
        xui_data: dict[str, str | None] = {}

        for panel in panels:
            try:
                if panel == PanelType.MARZBAN.value:
                    result = await self._provision_marzban(
                        account_name=account_name,
                        expiry_at=expiry_at,
                        plan=plan,
                        existing=renewal_candidate,
                        create_new_panel_account=new_db_record or not renewal_candidate,
                        reenable=action == ProvisionAction.RENEW_REENABLE_DISABLED,
                    )
                    marzban_data = {
                        "username": account_name,
                        "subscription_url": result.subscription_url,
                        "status": "active",
                    }
                elif panel == PanelType.XUI.value:
                    result = await self._provision_xui(
                        account_name=account_name,
                        expiry_at=expiry_at,
                        plan=plan,
                        existing=renewal_candidate,
                        create_new_panel_account=new_db_record or not renewal_candidate,
                        reenable=action == ProvisionAction.RENEW_REENABLE_DISABLED,
                    )
                    xui_data = {
                        "client_uuid": result.external_id,
                        "email": account_name,
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
                logger.warning("Panel provisioning failed", extra={"panel": panel, "error": exc.message})
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
            raise VpnProvisioningError(f"Не удалось выдать VPN: {errors}")

        status = VpnAccountStatus.ACTIVE.value
        if action == ProvisionAction.RENEW_REENABLE_DISABLED:
            logger.info(
                "Disabled VPN account re-enabled during approval",
                extra={"user_id": user.id, "account_name": account_name},
            )

        if new_db_record or renewal_candidate is None:
            existing_count = await self._uow.vpn_accounts.count_non_deleted_for_user(user.id)
            vpn_account = await self._uow.vpn_accounts.create(
                user_id=user.id,
                plan_id=plan.id,
                vpn_account_name=account_name,
                expiry_date=expiry_at,
                traffic_limit_gb=plan.traffic_limit_gb,
                ip_limit=plan.ip_limit,
                status=status,
                display_name=request.target_display_name if is_separate_purchase else None,
                is_primary=existing_count == 0,
            )
        else:
            vpn_account = renewal_candidate

        vpn_account = await self._uow.vpn_accounts.update_provision(
            vpn_account,
            plan_id=plan.id,
            expiry_date=expiry_at,
            traffic_limit_gb=plan.traffic_limit_gb,
            ip_limit=plan.ip_limit,
            status=status,
            marzban_username=marzban_data.get("username"),
            marzban_subscription_url=marzban_data.get("subscription_url"),
            marzban_status=marzban_data.get("status"),
            xui_client_uuid=xui_data.get("client_uuid"),
            xui_email=xui_data.get("email"),
            xui_subscription_url=xui_data.get("subscription_url"),
            xui_status=xui_data.get("status"),
        )

        if not user.vpn_account_name:
            user.vpn_account_name = account_name

        subscription_links = {
            "Marzban": marzban_data.get("subscription_url") or "",
            "3x-ui": xui_data.get("subscription_url") or "",
        }
        subscription_links = {key: value for key, value in subscription_links.items() if value}

        partial = bool(failures)
        return ProvisioningResult(
            success=not partial,
            partial=partial,
            failed=False,
            vpn_account_id=vpn_account.id,
            vpn_account_name=account_name,
            plan_name=plan.name,
            expiry_at=expiry_at,
            traffic_limit_gb=plan.traffic_limit_gb,
            ip_limit=plan.ip_limit,
            action=action,
            panel_results=panel_results,
            subscription_links=subscription_links,
        )

    async def _provision_marzban(
        self,
        *,
        account_name: str,
        expiry_at: datetime,
        plan: Plan,
        existing: VpnAccount | None,
        create_new_panel_account: bool,
        reenable: bool,
    ) -> PanelProvisionResult:
        if self._marzban is None:
            raise VpnProvisioningError("Marzban не включён в настройках.")

        has_existing = (
            existing is not None
            and not create_new_panel_account
            and existing.marzban_username
            and existing.status != VpnAccountStatus.DELETED.value
        )

        if has_existing and existing is not None:
            username = existing.marzban_username or account_name
            await self._marzban.update_user(
                username=username,
                expire_at=expiry_at,
                data_limit_gb=plan.traffic_limit_gb,
                ip_limit=plan.ip_limit,
                enable=True,
            )
            link = await self._marzban.get_subscription_link(username)
            return PanelProvisionResult(
                panel="Marzban",
                success=True,
                created=False,
                subscription_url=link,
                external_id=username,
            )

        try:
            info = await self._marzban.create_user(
                username=account_name,
                expire_at=expiry_at,
                data_limit_gb=plan.traffic_limit_gb,
                ip_limit=plan.ip_limit,
            )
        except VpnPanelConflictError:
            panel_user = await self._marzban.get_user(account_name)
            if panel_user and existing and existing.marzban_username == account_name:
                info = await self._marzban.update_user(
                    username=account_name,
                    expire_at=expiry_at,
                    data_limit_gb=plan.traffic_limit_gb,
                    ip_limit=plan.ip_limit,
                    enable=True,
                )
                return PanelProvisionResult(
                    panel="Marzban",
                    success=True,
                    created=False,
                    subscription_url=info.subscription_url,
                    external_id=info.username,
                )
            raise

        if reenable:
            logger.info("Marzban account enabled after disabled renewal", extra={"username": account_name})

        return PanelProvisionResult(
            panel="Marzban",
            success=True,
            created=True,
            subscription_url=info.subscription_url,
            external_id=info.username,
        )

    async def _provision_xui(
        self,
        *,
        account_name: str,
        expiry_at: datetime,
        plan: Plan,
        existing: VpnAccount | None,
        create_new_panel_account: bool,
        reenable: bool,
    ) -> PanelProvisionResult:
        if self._xui is None:
            raise VpnProvisioningError("3x-ui не включён в настройках.")

        has_existing = (
            existing is not None
            and not create_new_panel_account
            and existing.xui_email
            and existing.status != VpnAccountStatus.DELETED.value
        )

        email = existing.xui_email if has_existing and existing else account_name

        if has_existing and existing is not None:
            info = await self._xui.update_client(
                email=email,
                expiry_time=expiry_at,
                total_gb=plan.traffic_limit_gb,
                limit_ip=plan.ip_limit,
                enable=True,
            )
            return PanelProvisionResult(
                panel="3x-ui",
                success=True,
                created=False,
                subscription_url=info.subscription_url,
                external_id=info.client_uuid,
            )

        try:
            info = await self._xui.create_client(
                email=account_name,
                expiry_time=expiry_at,
                total_gb=plan.traffic_limit_gb,
                limit_ip=plan.ip_limit,
            )
        except VpnPanelConflictError:
            panel_client = await self._xui.get_client(account_name)
            if panel_client and existing and existing.xui_email == account_name:
                info = await self._xui.update_client(
                    email=account_name,
                    expiry_time=expiry_at,
                    total_gb=plan.traffic_limit_gb,
                    limit_ip=plan.ip_limit,
                    enable=True,
                )
                return PanelProvisionResult(
                    panel="3x-ui",
                    success=True,
                    created=False,
                    subscription_url=info.subscription_url,
                    external_id=info.client_uuid,
                )
            raise

        if reenable:
            logger.info("3x-ui client enabled after disabled renewal", extra={"email": account_name})

        return PanelProvisionResult(
            panel="3x-ui",
            success=True,
            created=True,
            subscription_url=info.subscription_url,
            external_id=info.client_uuid,
        )

    def _resolve_account_name(self, user: User) -> str:
        if user.vpn_account_name:
            return normalize_vpn_account_name(user.vpn_account_name)
        normalized = normalize_from_telegram_username(user.username)
        if normalized is None:
            raise VpnProvisioningError(MISSING_USERNAME_ERROR)
        return normalized

    def _panels_for_plan(self, plan: Plan) -> list[str]:
        mode = plan.issuing_mode
        if mode == IssuingMode.MARZBAN.value:
            return [PanelType.MARZBAN.value] if self._settings.marzban_enabled else []
        if mode == IssuingMode.XUI.value:
            return [PanelType.XUI.value] if self._settings.xui_enabled else []
        panels: list[str] = []
        if self._settings.marzban_enabled:
            panels.append(PanelType.MARZBAN.value)
        if self._settings.xui_enabled:
            panels.append(PanelType.XUI.value)
        return panels
