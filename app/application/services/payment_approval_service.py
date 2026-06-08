from __future__ import annotations

import logging
from dataclasses import dataclass

from app.application.dto.provisioning import ProvisioningResult
from app.application.exceptions import (
    PaymentRequestAlreadyProcessedError,
    PaymentRequestNotFoundError,
    VpnProvisioningError,
)
from app.application.services.admin_log_service import AdminLogService
from app.application.services.vpn_provisioning_service import VpnProvisioningService
from app.domain.enums import AdminActionType, PaymentRequestStatus, ProvisionAction
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApprovalOutcome:
    provisioning: ProvisioningResult | None
    notify_customer: bool
    customer_message: str
    admin_message: str
    success: bool
    partial: bool
    failed: bool
    request_id: int
    telegram_id: int


class PaymentApprovalService:
    """Orchestrates payment approval and VPN provisioning."""

    def __init__(
        self,
        uow: UnitOfWork,
        provisioning_service: VpnProvisioningService,
        admin_log_service: AdminLogService,
    ) -> None:
        self._uow = uow
        self._provisioning = provisioning_service
        self._admin_log = admin_log_service

    async def approve_with_provisioning(
        self,
        request_id: int,
        *,
        admin_telegram_id: int,
    ) -> ApprovalOutcome:
        request = await self._uow.payment_requests.get_by_id_with_relations(request_id)
        if request is None:
            raise PaymentRequestNotFoundError("Заявка не найдена.")
        if request.status != PaymentRequestStatus.PENDING.value:
            raise PaymentRequestAlreadyProcessedError("Эта заявка уже обработана.")

        user = request.user
        if user is None:
            raise PaymentRequestNotFoundError("Пользователь заявки не найден.")

        await self._uow.payment_requests.approve(request, admin_telegram_id=admin_telegram_id)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.PAYMENT_APPROVED,
            details={"payment_request_id": request.id, "user_id": request.user_id},
        )

        try:
            result = await self._provisioning.provision_for_payment_request(request)
        except VpnProvisioningError as exc:
            await self._uow.payment_requests.mark_provisioning_failed(request, error_message=exc.message)
            await self._admin_log.log(
                admin_telegram_id=admin_telegram_id,
                action=AdminActionType.VPN_PROVISIONING_FAILED,
                details={
                    "payment_request_id": request.id,
                    "error": exc.message,
                },
            )
            logger.error(
                "VPN provisioning failed",
                extra={"request_id": request.id, "error": exc.message},
            )
            return ApprovalOutcome(
                provisioning=None,
                notify_customer=False,
                customer_message="",
                admin_message=(
                    f"⚠️ Заявка #{request.id} подтверждена, но VPN не выдан.\n"
                    f"Причина: {exc.message}"
                ),
                success=False,
                partial=False,
                failed=True,
                request_id=request.id,
                telegram_id=user.telegram_id,
            )

        if result.partial:
            error_summary = "; ".join(
                item.error or "ошибка"
                for item in result.panel_results
                if not item.success
            )
            await self._uow.payment_requests.mark_provisioning_partial(
                request,
                error_message=error_summary,
                vpn_account_id=result.vpn_account_id,
            )
            await self._admin_log.log(
                admin_telegram_id=admin_telegram_id,
                action=AdminActionType.VPN_PROVISIONING_PARTIAL,
                details={
                    "payment_request_id": request.id,
                    "vpn_account_id": result.vpn_account_id,
                    "errors": error_summary,
                    "panels": [item.panel for item in result.panel_results if item.success],
                },
            )
            admin_message = result.admin_message()
            return ApprovalOutcome(
                provisioning=result,
                notify_customer=False,
                customer_message="",
                admin_message=admin_message,
                success=False,
                partial=True,
                failed=False,
                request_id=request.id,
                telegram_id=user.telegram_id,
            )

        if result.vpn_account_id is not None:
            await self._uow.payment_requests.link_vpn_account(request, result.vpn_account_id)

        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.VPN_PROVISIONED,
            details={
                "payment_request_id": request.id,
                "vpn_account_id": result.vpn_account_id,
                "action": result.action.value,
                "expiry_at": result.expiry_at.isoformat(),
            },
        )
        if result.action in {
            ProvisionAction.RENEW_ACTIVE,
            ProvisionAction.RENEW_FROM_NOW,
            ProvisionAction.RENEW_REENABLE_DISABLED,
        }:
            await self._admin_log.log(
                admin_telegram_id=admin_telegram_id,
                action=AdminActionType.CLIENT_RENEWED,
                details={
                    "payment_request_id": request.id,
                    "vpn_account_id": result.vpn_account_id,
                },
            )

        return ApprovalOutcome(
            provisioning=result,
            notify_customer=True,
            customer_message=result.customer_message(),
            admin_message=result.admin_message(),
            success=True,
            partial=False,
            failed=False,
            request_id=request.id,
            telegram_id=user.telegram_id,
        )
