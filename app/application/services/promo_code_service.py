from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from app.application.dto.promo_code import PromoApplyResult, PromoCodeInfo
from app.application.exceptions import PromoCodeError
from app.application.services.admin_log_service import AdminLogService
from app.domain.enums import (
    AdminActionType,
    PaymentRequestType,
    PromoDiscountType,
    PromoRequestScope,
)
from app.infrastructure.db.models.payment_request import PaymentRequest
from app.infrastructure.db.models.promo_code import PromoCode
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

INVALID_PROMO_MESSAGE = "Промокод не найден или уже не действует."
USED_PROMO_MESSAGE = "Вы уже использовали этот промокод."

DISCOUNT_TYPE_LABELS = {
    PromoDiscountType.PERCENT.value: "процент",
    PromoDiscountType.FIXED_AMOUNT.value: "фикс. сумма",
    PromoDiscountType.EXTRA_DAYS.value: "доп. дни",
}

SCOPE_LABELS = {
    PromoRequestScope.ANY.value: "покупка и продление",
    PromoRequestScope.PURCHASE.value: "только покупка",
    PromoRequestScope.RENEWAL.value: "только продление",
}


@dataclass(slots=True)
class PromoCodeDraft:
    code: str
    discount_type: str
    value: Decimal
    starts_at: datetime | None
    expires_at: datetime | None
    max_uses: int | None
    max_uses_per_user: int
    min_amount: Decimal | None
    applies_to_plan_id: int | None
    applies_to_request_type: str | None
    new_users_only: bool


class PromoCodeService:
    def __init__(self, uow: UnitOfWork, admin_log_service: AdminLogService) -> None:
        self._uow = uow
        self._admin_log = admin_log_service

    @staticmethod
    def normalize_code(raw: str) -> str:
        return raw.strip().upper()

    async def validate_and_apply(
        self,
        *,
        user_id: int,
        code: str,
        plan_id: int,
        request_type: str,
        original_amount: Decimal,
    ) -> PromoApplyResult:
        normalized = self.normalize_code(code)
        promo = await self._uow.promo_codes.get_by_code(normalized)
        if promo is None:
            raise PromoCodeError(INVALID_PROMO_MESSAGE)

        await self._ensure_eligible(
            promo,
            user_id=user_id,
            plan_id=plan_id,
            request_type=request_type,
            original_amount=original_amount,
        )

        discount_amount, final_amount, extra_days = self.calculate_discount(
            promo,
            original_amount=original_amount,
        )

        await self._admin_log.log(
            admin_telegram_id=0,
            action=AdminActionType.PROMO_CODE_APPLIED,
            details={
                "promo_code_id": promo.id,
                "user_id": user_id,
                "plan_id": plan_id,
                "request_type": request_type,
                "discount_amount": str(discount_amount),
                "final_amount": str(final_amount),
            },
        )

        return PromoApplyResult(
            promo_code_id=promo.id,
            code=promo.code,
            discount_type=promo.discount_type,
            original_amount=original_amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            extra_days=extra_days,
        )

    async def redeem_for_payment_request(self, request: PaymentRequest) -> None:
        if request.promo_code_id is None:
            return
        promo = await self._uow.promo_codes.get_by_id(request.promo_code_id)
        if promo is None:
            return

        original = request.original_amount if request.original_amount is not None else request.amount
        discount = request.discount_amount
        final = request.final_amount if request.final_amount is not None else request.amount

        await self._uow.promo_codes.create_redemption(
            promo_code_id=promo.id,
            user_id=request.user_id,
            payment_request_id=request.id,
            original_amount=original,
            discount_amount=discount,
            final_amount=final,
            extra_days=request.extra_days_from_promo,
        )
        await self._uow.promo_codes.increment_used_count(promo)
        await self._admin_log.log(
            admin_telegram_id=request.processed_by_telegram_id or 0,
            action=AdminActionType.PROMO_CODE_REDEEMED,
            details={
                "promo_code_id": promo.id,
                "payment_request_id": request.id,
                "user_id": request.user_id,
            },
        )

    async def create_promo(
        self,
        draft: PromoCodeDraft,
        *,
        admin_telegram_id: int,
    ) -> PromoCode:
        code = self.normalize_code(draft.code)
        if await self._uow.promo_codes.exists_code(code):
            raise PromoCodeError("Промокод с таким кодом уже существует.")

        promo = await self._uow.promo_codes.create(
            code=code,
            discount_type=draft.discount_type,
            value=draft.value,
            starts_at=draft.starts_at,
            expires_at=draft.expires_at,
            max_uses=draft.max_uses,
            max_uses_per_user=draft.max_uses_per_user,
            min_amount=draft.min_amount,
            applies_to_plan_id=draft.applies_to_plan_id,
            applies_to_request_type=draft.applies_to_request_type,
            new_users_only=draft.new_users_only,
            created_by_admin_id=admin_telegram_id,
        )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.PROMO_CODE_CREATED,
            details={"promo_code_id": promo.id, "code": promo.code},
        )
        return promo

    async def set_active(self, promo_code_id: int, *, is_active: bool, admin_telegram_id: int) -> PromoCode:
        promo = await self._uow.promo_codes.get_by_id(promo_code_id)
        if promo is None:
            raise PromoCodeError("Промокод не найден.")
        promo = await self._uow.promo_codes.set_active(promo, is_active=is_active)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.PROMO_CODE_ENABLED if is_active else AdminActionType.PROMO_CODE_DISABLED,
            details={"promo_code_id": promo.id, "code": promo.code},
        )
        return promo

    async def list_promos(self, *, limit: int = 50) -> list[PromoCodeInfo]:
        items = await self._uow.promo_codes.list_all(limit=limit)
        return [self._to_info(item) for item in items]

    async def search_promos(self, query: str) -> list[PromoCodeInfo]:
        items = await self._uow.promo_codes.search(query)
        return [self._to_info(item) for item in items]

    async def get_redemptions_text(self, promo_code_id: int) -> str:
        promo = await self._uow.promo_codes.get_by_id(promo_code_id)
        if promo is None:
            raise PromoCodeError("Промокод не найден.")
        redemptions = await self._uow.promo_codes.list_redemptions(promo_code_id)
        return self.format_redemptions(promo, redemptions)

    async def get_stats_text(self) -> str:
        stats = await self._uow.promo_codes.get_stats()
        return (
            "📊 Статистика промокодов\n\n"
            f"Всего кодов: {stats['total_codes']}\n"
            f"Активных: {stats['active_codes']}\n"
            f"Использований: {stats['total_redemptions']}\n"
            f"Сумма скидок: {stats['total_discount']:.0f} ₽"
        )

    def format_applied_message(self, result: PromoApplyResult) -> str:
        lines = [
            "🎁 <b>Промокод применён</b>",
            f"Код: <code>{result.code}</code>",
            f"Было: <b>{result.original_amount:.0f} ₽</b>",
        ]
        if result.discount_type != PromoDiscountType.EXTRA_DAYS.value:
            lines.append(f"Скидка: <b>{result.discount_amount:.0f} ₽</b>")
            lines.append(f"К оплате: <b>{result.final_amount:.0f} ₽</b>")
        else:
            lines.append(f"К оплате: <b>{result.final_amount:.0f} ₽</b>")
            lines.append(f"➕ Дополнительно: <b>{result.extra_days} дн.</b>")
        return "\n".join(lines)

    def format_preview(self, draft: PromoCodeDraft) -> str:
        plan_line = "любой тариф"
        if draft.applies_to_plan_id is not None:
            plan_line = f"тариф ID {draft.applies_to_plan_id}"
        scope = SCOPE_LABELS.get(draft.applies_to_request_type or PromoRequestScope.ANY.value, "любой")
        uses = str(draft.max_uses) if draft.max_uses is not None else "безлимит"
        dates = "без ограничений"
        if draft.starts_at or draft.expires_at:
            start = draft.starts_at.strftime("%d.%m.%Y") if draft.starts_at else "—"
            end = draft.expires_at.strftime("%d.%m.%Y") if draft.expires_at else "—"
            dates = f"{start} — {end}"
        value_text = self._format_value(draft.discount_type, draft.value)
        return (
            "🎁 Предпросмотр промокода\n\n"
            f"Код: {self.normalize_code(draft.code)}\n"
            f"Тип: {DISCOUNT_TYPE_LABELS.get(draft.discount_type, draft.discount_type)}\n"
            f"Значение: {value_text}\n"
            f"Период: {dates}\n"
            f"Лимит: {uses} · на пользователя: {draft.max_uses_per_user}\n"
            f"Область: {scope} · {plan_line}\n"
            f"Только новые: {'да' if draft.new_users_only else 'нет'}"
        )

    def format_list(self, items: list[PromoCodeInfo]) -> str:
        if not items:
            return "📋 Промокоды\n\nСписок пуст."
        lines = ["📋 Промокоды", ""]
        for item in items:
            status = "✅" if item.is_active else "🚫"
            max_uses = str(item.max_uses) if item.max_uses is not None else "∞"
            expiry = item.expires_at.strftime("%d.%m.%Y") if item.expires_at else "—"
            value = self._format_value(item.discount_type, item.value)
            lines.append(f"{status} {item.code} · {value}")
            lines.append(f"{item.used_count}/{max_uses} · до {expiry}")
        return "\n".join(lines)

    def format_redemptions(self, promo: PromoCode, redemptions: list) -> str:
        lines = [
            f"📜 Использования: {promo.code}",
            f"Всего: {promo.used_count}",
            "",
        ]
        if not redemptions:
            lines.append("Пока нет использований.")
            return "\n".join(lines)
        for item in redemptions:
            created = item.created_at.strftime("%d.%m.%Y %H:%M")
            lines.append(
                f"• user #{item.user_id} · "
                f"{item.original_amount:.0f} → {item.final_amount:.0f} ₽ "
                f"(-{item.discount_amount:.0f}) · {created}"
            )
        return "\n".join(lines)

    @staticmethod
    def calculate_discount(
        promo: PromoCode,
        *,
        original_amount: Decimal,
    ) -> tuple[Decimal, Decimal, int]:
        extra_days = 0
        if promo.discount_type == PromoDiscountType.PERCENT.value:
            discount = (original_amount * promo.value / Decimal("100")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        elif promo.discount_type == PromoDiscountType.FIXED_AMOUNT.value:
            discount = min(promo.value, original_amount)
        elif promo.discount_type == PromoDiscountType.EXTRA_DAYS.value:
            discount = Decimal("0")
            extra_days = int(promo.value)
        else:
            discount = Decimal("0")

        final_amount = max(Decimal("0"), original_amount - discount)
        return discount, final_amount, extra_days

    async def _ensure_eligible(
        self,
        promo: PromoCode,
        *,
        user_id: int,
        plan_id: int,
        request_type: str,
        original_amount: Decimal,
    ) -> None:
        if not promo.is_active:
            raise PromoCodeError(INVALID_PROMO_MESSAGE)

        now = datetime.now(UTC)
        if promo.starts_at is not None:
            starts = promo.starts_at if promo.starts_at.tzinfo else promo.starts_at.replace(tzinfo=UTC)
            if now < starts:
                raise PromoCodeError(INVALID_PROMO_MESSAGE)
        if promo.expires_at is not None:
            expires = promo.expires_at if promo.expires_at.tzinfo else promo.expires_at.replace(tzinfo=UTC)
            if now > expires:
                raise PromoCodeError(INVALID_PROMO_MESSAGE)

        if promo.max_uses is not None and promo.used_count >= promo.max_uses:
            raise PromoCodeError(INVALID_PROMO_MESSAGE)

        user_uses = await self._uow.promo_codes.count_user_redemptions(promo.id, user_id)
        if user_uses >= promo.max_uses_per_user:
            raise PromoCodeError(USED_PROMO_MESSAGE)

        if promo.min_amount is not None and original_amount < promo.min_amount:
            raise PromoCodeError(INVALID_PROMO_MESSAGE)

        if promo.applies_to_plan_id is not None and promo.applies_to_plan_id != plan_id:
            raise PromoCodeError(INVALID_PROMO_MESSAGE)

        scope = promo.applies_to_request_type or PromoRequestScope.ANY.value
        if scope != PromoRequestScope.ANY.value and scope != request_type:
            raise PromoCodeError(INVALID_PROMO_MESSAGE)

        if promo.new_users_only and await self._uow.promo_codes.user_has_approved_payment(user_id):
            raise PromoCodeError(INVALID_PROMO_MESSAGE)

    @staticmethod
    def _format_value(discount_type: str, value: Decimal) -> str:
        if discount_type == PromoDiscountType.PERCENT.value:
            return f"{value:.0f}%"
        if discount_type == PromoDiscountType.EXTRA_DAYS.value:
            return f"+{int(value)} дн."
        return f"{value:.0f} ₽"

    @staticmethod
    def _to_info(promo: PromoCode) -> PromoCodeInfo:
        return PromoCodeInfo(
            id=promo.id,
            code=promo.code,
            discount_type=promo.discount_type,
            value=promo.value,
            is_active=promo.is_active,
            starts_at=promo.starts_at,
            expires_at=promo.expires_at,
            max_uses=promo.max_uses,
            max_uses_per_user=promo.max_uses_per_user,
            used_count=promo.used_count,
            min_amount=promo.min_amount,
            applies_to_plan_id=promo.applies_to_plan_id,
            applies_to_request_type=promo.applies_to_request_type,
            new_users_only=promo.new_users_only,
            created_at=promo.created_at,
        )
