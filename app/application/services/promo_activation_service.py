from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from app.application.dto.provisioning import ProvisioningResult
from app.application.exceptions import PaymentRequestNotFoundError, VpnProvisioningError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.promo_code_service import PromoCodeService
from app.application.services.vpn_provisioning_service import VpnProvisioningService
from app.config.settings import Settings
from app.domain.enums import AdminActionType, PaymentRequestType
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

ACTIVATION_FAILED = "⚠️ Не удалось активировать VPN по промокоду. Свяжитесь с поддержкой."
ACTIVATION_PARTIAL = "⚠️ VPN выдан частично. Свяжитесь с поддержкой."


@dataclass(slots=True)
class PromoActivationOutcome:
    success: bool
    partial: bool
    failed: bool
    provisioning: ProvisioningResult | None
    customer_message: str
    request_id: int | None
    telegram_id: int
    notify_customer: bool


class PromoActivationService:
    """Auto-approve and provision when promo reduces final amount to zero."""

    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        provisioning_service: VpnProvisioningService,
        admin_log_service: AdminLogService,
        promo_code_service: PromoCodeService,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._provisioning = provisioning_service
        self._admin_log = admin_log_service
        self._promo = promo_code_service

    async def activate(
        self,
        *,
        telegram_id: int,
        plan_id: int,
        request_type: str,
        promo_code_id: int,
        original_amount: Decimal,
        discount_amount: Decimal,
        final_amount: Decimal,
        extra_days_from_promo: int,
        vpn_account_id: int | None = None,
        target_vpn_account_name: str | None = None,
        target_display_name: str | None = None,
    ) -> PromoActivationOutcome:
        if final_amount != Decimal("0"):
            raise PaymentRequestNotFoundError("Промокод не даёт бесплатную активацию.")

        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            raise PaymentRequestNotFoundError("Пользователь не найден. Отправьте /start.")

        plan = await self._uow.plans.get_by_id(plan_id)
        if plan is None or not plan.is_active:
            raise PaymentRequestNotFoundError("Тариф недоступен.")

        request = await self._uow.payment_requests.create_approved_promo_request(
            user_id=user.id,
            plan_id=plan.id,
            request_type=request_type,
            amount=final_amount,
            promo_code_id=promo_code_id,
            original_amount=original_amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            extra_days_from_promo=extra_days_from_promo,
            vpn_account_id=vpn_account_id,
            target_vpn_account_name=target_vpn_account_name,
            target_display_name=target_display_name,
        )
        request = await self._uow.payment_requests.get_by_id_with_relations(request.id)
        if request is None:
            raise PaymentRequestNotFoundError("Не удалось создать заявку.")

        await self._promo.redeem_for_payment_request(request)

        admin_id = self._resolve_log_admin_id(telegram_id)
        await self._admin_log.log(
            admin_telegram_id=admin_id,
            action=AdminActionType.PAYMENT_APPROVED,
            details={"payment_request_id": request.id, "promo_zero_amount": True},
        )

        try:
            result = await self._provisioning.provision_for_payment_request(request)
        except VpnProvisioningError as exc:
            await self._uow.payment_requests.mark_provisioning_failed(request, error_message=exc.message)
            await self._admin_log.log(
                admin_telegram_id=admin_id,
                action=AdminActionType.VPN_PROVISIONING_FAILED,
                details={"payment_request_id": request.id, "error": exc.message, "promo": True},
            )
            return PromoActivationOutcome(
                success=False,
                partial=False,
                failed=True,
                provisioning=None,
                customer_message=ACTIVATION_FAILED,
                request_id=request.id,
                telegram_id=telegram_id,
                notify_customer=True,
            )

        if result.partial:
            error_summary = "; ".join(
                item.error or "ошибка" for item in result.panel_results if not item.success
            )
            await self._uow.payment_requests.mark_provisioning_partial(
                request,
                error_message=error_summary,
                vpn_account_id=result.vpn_account_id,
            )
            return PromoActivationOutcome(
                success=False,
                partial=True,
                failed=False,
                provisioning=result,
                customer_message=ACTIVATION_PARTIAL,
                request_id=request.id,
                telegram_id=telegram_id,
                notify_customer=False,
            )

        if result.vpn_account_id is not None:
            await self._uow.payment_requests.link_vpn_account(request, result.vpn_account_id)

        await self._admin_log.log(
            admin_telegram_id=admin_id,
            action=AdminActionType.VPN_PROVISIONED,
            details={
                "payment_request_id": request.id,
                "vpn_account_id": result.vpn_account_id,
                "promo": True,
            },
        )

        free_msg = request_type == PaymentRequestType.PURCHASE.value
        return PromoActivationOutcome(
            success=True,
            partial=False,
            failed=False,
            provisioning=result,
            customer_message=result.customer_message(free=free_msg),
            request_id=request.id,
            telegram_id=telegram_id,
            notify_customer=True,
        )

    def _resolve_log_admin_id(self, telegram_id: int) -> int:
        if self._settings.admin_telegram_ids:
            return self._settings.admin_telegram_ids[0]
        return telegram_id
