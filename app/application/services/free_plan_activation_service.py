from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from app.application.dto.provisioning import ProvisioningResult
from app.application.exceptions import (
    FreePlanNotEligibleError,
    PaymentRequestNotFoundError,
    VpnProvisioningError,
)
from app.application.services.admin_log_service import AdminLogService
from app.application.services.vpn_provisioning_service import VpnProvisioningService
from app.config.settings import Settings
from app.domain.enums import AdminActionType, ProvisionAction
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

ACTIVE_VPN_MESSAGE = "У вас уже есть активный VPN."
FREE_PLAN_USED_MESSAGE = "Вы уже использовали бесплатный период."
FREE_ACTIVATION_FAILED = "⚠️ Не удалось активировать бесплатный доступ. Свяжитесь с поддержкой."
FREE_ACTIVATION_PARTIAL = "⚠️ VPN выдан частично. Свяжитесь с поддержкой."


@dataclass(slots=True)
class FreePlanActivationOutcome:
    success: bool
    partial: bool
    failed: bool
    provisioning: ProvisioningResult | None
    customer_message: str
    request_id: int | None
    telegram_id: int
    notify_customer: bool


class FreePlanActivationService:
    """Automatic VPN provisioning for zero-price plans."""

    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        provisioning_service: VpnProvisioningService,
        admin_log_service: AdminLogService,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioning = provisioning_service
        self._admin_log = admin_log_service

    async def activate(self, telegram_id: int, plan_id: int) -> FreePlanActivationOutcome:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            raise PaymentRequestNotFoundError("Пользователь не найден. Отправьте /start.")

        plan = await self._uow.plans.get_by_id(plan_id)
        if plan is None or not plan.is_active:
            raise PaymentRequestNotFoundError("Тариф недоступен.")
        if plan.price != Decimal("0"):
            raise PaymentRequestNotFoundError("Этот тариф не является бесплатным.")

        await self._ensure_eligible(user.id)

        request = await self._uow.payment_requests.create_approved_free_purchase(
            user_id=user.id,
            plan_id=plan.id,
        )
        request = await self._uow.payment_requests.get_by_id_with_relations(request.id)
        if request is None:
            raise PaymentRequestNotFoundError("Не удалось создать заявку.")

        await self._admin_log.log(
            admin_telegram_id=self._resolve_log_admin_id(telegram_id),
            action=AdminActionType.FREE_PLAN_ACTIVATED,
            details={
                "payment_request_id": request.id,
                "user_id": user.id,
                "plan_id": plan.id,
                "telegram_id": telegram_id,
            },
        )
        logger.info(
            "Free plan activation started",
            extra={"request_id": request.id, "user_id": user.id, "plan_id": plan.id},
        )

        try:
            result = await self._provisioning.provision_for_payment_request(request)
        except VpnProvisioningError as exc:
            await self._uow.payment_requests.mark_provisioning_failed(request, error_message=exc.message)
            await self._admin_log.log(
                admin_telegram_id=self._resolve_log_admin_id(telegram_id),
                action=AdminActionType.VPN_PROVISIONING_FAILED,
                details={
                    "payment_request_id": request.id,
                    "error": exc.message,
                    "free_plan": True,
                },
            )
            logger.error(
                "Free plan provisioning failed",
                extra={"request_id": request.id, "error": exc.message},
            )
            return FreePlanActivationOutcome(
                success=False,
                partial=False,
                failed=True,
                provisioning=None,
                customer_message=FREE_ACTIVATION_FAILED,
                request_id=request.id,
                telegram_id=telegram_id,
                notify_customer=True,
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
                admin_telegram_id=self._resolve_log_admin_id(telegram_id),
                action=AdminActionType.VPN_PROVISIONING_PARTIAL,
                details={
                    "payment_request_id": request.id,
                    "vpn_account_id": result.vpn_account_id,
                    "errors": error_summary,
                    "free_plan": True,
                },
            )
            return FreePlanActivationOutcome(
                success=False,
                partial=True,
                failed=False,
                provisioning=result,
                customer_message=FREE_ACTIVATION_PARTIAL,
                request_id=request.id,
                telegram_id=telegram_id,
                notify_customer=False,
            )

        if result.vpn_account_id is not None:
            await self._uow.payment_requests.link_vpn_account(request, result.vpn_account_id)

        await self._admin_log.log(
            admin_telegram_id=self._resolve_log_admin_id(telegram_id),
            action=AdminActionType.VPN_PROVISIONED,
            details={
                "payment_request_id": request.id,
                "vpn_account_id": result.vpn_account_id,
                "action": result.action.value,
                "expiry_at": result.expiry_at.isoformat(),
                "free_plan": True,
            },
        )

        return FreePlanActivationOutcome(
            success=True,
            partial=False,
            failed=False,
            provisioning=result,
            customer_message=result.customer_message(free=True),
            request_id=request.id,
            telegram_id=telegram_id,
            notify_customer=True,
        )

    async def _ensure_eligible(self, user_id: int) -> None:
        if await self._uow.vpn_accounts.has_active_vpn(user_id):
            raise FreePlanNotEligibleError(ACTIVE_VPN_MESSAGE)
        if await self._uow.payment_requests.has_free_plan_activation(user_id):
            raise FreePlanNotEligibleError(FREE_PLAN_USED_MESSAGE)

    def _resolve_log_admin_id(self, telegram_id: int) -> int:
        if self._settings.admin_telegram_ids:
            return self._settings.admin_telegram_ids[0]
        return telegram_id
