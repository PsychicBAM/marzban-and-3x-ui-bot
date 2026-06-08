from __future__ import annotations

import logging
from datetime import datetime

from app.application.dto.manual_provision import ProvisionProfile
from app.application.dto.provisioning import PanelProvisionResult
from app.application.exceptions import VpnPanelConflictError, VpnPanelError, VpnProvisioningError
from app.config.settings import Settings
from app.domain.enums import VpnAccountStatus
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.integrations.marzban.service import MarzbanService
from app.infrastructure.integrations.xui.service import XuiService

logger = logging.getLogger(__name__)


class PanelProvisioner:
    """Shared Marzban/3x-ui create-or-update operations."""

    def __init__(
        self,
        settings: Settings,
        marzban: MarzbanService | None,
        xui: XuiService | None,
    ) -> None:
        self._settings = settings
        self._marzban = marzban
        self._xui = xui

    async def check_name_conflicts(self, account_name: str, issuing_mode: str) -> list[str]:
        conflicts: list[str] = []
        if issuing_mode in {"marzban", "both"} and self._marzban is not None:
            if await self._marzban.get_user(account_name) is not None:
                conflicts.append("Marzban")
        if issuing_mode in {"xui", "both"} and self._xui is not None:
            if await self._xui.get_client(account_name) is not None:
                conflicts.append("3x-ui")
        return conflicts

    async def provision_marzban(
        self,
        *,
        account_name: str,
        expiry_at: datetime,
        profile: ProvisionProfile,
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
                data_limit_gb=profile.traffic_limit_gb,
                ip_limit=profile.ip_limit,
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
                data_limit_gb=profile.traffic_limit_gb,
                ip_limit=profile.ip_limit,
            )
        except VpnPanelConflictError:
            panel_user = await self._marzban.get_user(account_name)
            if panel_user and existing and existing.marzban_username == account_name:
                info = await self._marzban.update_user(
                    username=account_name,
                    expire_at=expiry_at,
                    data_limit_gb=profile.traffic_limit_gb,
                    ip_limit=profile.ip_limit,
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
            logger.info("Marzban account enabled", extra={"username": account_name})

        return PanelProvisionResult(
            panel="Marzban",
            success=True,
            created=True,
            subscription_url=info.subscription_url,
            external_id=info.username,
        )

    async def provision_xui(
        self,
        *,
        account_name: str,
        expiry_at: datetime,
        profile: ProvisionProfile,
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
                total_gb=profile.traffic_limit_gb,
                limit_ip=profile.ip_limit,
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
                total_gb=profile.traffic_limit_gb,
                limit_ip=profile.ip_limit,
            )
        except VpnPanelConflictError:
            panel_client = await self._xui.get_client(account_name)
            if panel_client and existing and existing.xui_email == account_name:
                info = await self._xui.update_client(
                    email=account_name,
                    expiry_time=expiry_at,
                    total_gb=profile.traffic_limit_gb,
                    limit_ip=profile.ip_limit,
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
            logger.info("3x-ui client enabled", extra={"email": account_name})

        return PanelProvisionResult(
            panel="3x-ui",
            success=True,
            created=True,
            subscription_url=info.subscription_url,
            external_id=info.client_uuid,
        )
