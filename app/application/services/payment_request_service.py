from __future__ import annotations

import html
import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.application.dto.payment_request import PaymentRequestInfo
from app.application.exceptions import (
    PaymentRequestAlreadyProcessedError,
    PaymentRequestDuplicateError,
    PaymentRequestNotFoundError,
)
from app.application.services.expiry_calculator import ExpiryCalculator
from app.application.services.settings_service import SettingsService
from app.config.settings import Settings
from app.domain.enums import PaymentRequestStatus, PaymentRequestType, ReceiptFileType
from app.infrastructure.db.models.payment_request import PaymentRequest
from app.application.services.plan_service import ISSUING_MODE_LABELS
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

REQUEST_TYPE_LABELS: dict[str, str] = {
    PaymentRequestType.PURCHASE.value: "новая",
    PaymentRequestType.RENEWAL.value: "продление",
}


def resolve_request_type_label(item: PaymentRequestInfo) -> str:
    if item.request_type == PaymentRequestType.RENEWAL.value:
        return "продление"
    if item.target_vpn_account_name:
        return "новая подписка"
    return "новая"

RECEIPT_TYPE_LABELS: dict[str, str] = {
    ReceiptFileType.PHOTO.value: "фото",
    ReceiptFileType.DOCUMENT.value: "документ",
    ReceiptFileType.TEXT.value: "текст",
}

STATUS_LABELS: dict[str, str] = {
    PaymentRequestStatus.PENDING.value: "⏳ На проверке",
    PaymentRequestStatus.APPROVED.value: "✅ Подтверждена",
    PaymentRequestStatus.REJECTED.value: "❌ Отклонена",
    PaymentRequestStatus.PROVISIONING_FAILED.value: "⚠️ Ошибка выдачи VPN",
    PaymentRequestStatus.PROVISIONING_PARTIAL.value: "⚠️ Частичная выдача VPN",
}

PAYMENT_DETAILS_MISSING = (
    "⚠️ Реквизиты оплаты пока не настроены. Свяжитесь с поддержкой."
)


class PaymentRequestService:
    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        settings_service: SettingsService,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._settings_service = settings_service

    async def get_payment_details_text(self) -> str:
        details = await self._settings_service.get_payment_details()
        if details:
            return details
        return PAYMENT_DETAILS_MISSING

    async def has_payment_details(self) -> bool:
        return await self._settings_service.get_payment_details() is not None

    async def has_pending_purchase(self, telegram_id: int) -> bool:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            return False
        existing = await self._uow.payment_requests.get_pending_purchase_by_user_id(user.id)
        return existing is not None

    async def has_pending_renewal(self, telegram_id: int) -> bool:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            return False
        existing = await self._uow.payment_requests.get_pending_renewal_by_user_id(user.id)
        return existing is not None

    async def create_purchase_request(
        self,
        *,
        telegram_id: int,
        plan_id: int,
        receipt_file_id: str | None,
        receipt_file_type: str,
        user_comment: str | None,
        receipt_message_id: int | None = None,
        target_vpn_account_name: str | None = None,
        target_display_name: str | None = None,
        promo_code_id: int | None = None,
        original_amount: Decimal | None = None,
        discount_amount: Decimal = Decimal("0"),
        final_amount: Decimal | None = None,
        extra_days_from_promo: int = 0,
    ) -> PaymentRequestInfo:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            raise PaymentRequestNotFoundError("Пользователь не найден. Отправьте /start.")

        existing = await self._uow.payment_requests.get_pending_purchase_by_user_id(user.id)
        if existing is not None:
            raise PaymentRequestDuplicateError(
                "⏳ У вас уже есть заявка на проверке. Дождитесь ответа администратора.",
            )

        plan = await self._uow.plans.get_by_id(plan_id)
        if plan is None or not plan.is_active:
            raise PaymentRequestNotFoundError("Тариф недоступен.")

        if target_vpn_account_name:
            if await self._uow.vpn_accounts.exists_by_name(target_vpn_account_name):
                raise PaymentRequestDuplicateError(
                    "Имя подписки уже занято. Выберите другое название.",
                )

        pay_amount = final_amount if final_amount is not None else plan.price
        request = await self._uow.payment_requests.create(
            user_id=user.id,
            plan_id=plan.id,
            request_type=PaymentRequestType.PURCHASE.value,
            amount=pay_amount,
            receipt_file_id=receipt_file_id,
            receipt_file_type=receipt_file_type,
            user_comment=user_comment,
            receipt_message_id=receipt_message_id,
            target_vpn_account_name=target_vpn_account_name,
            target_display_name=target_display_name,
            promo_code_id=promo_code_id,
            original_amount=original_amount if original_amount is not None else plan.price,
            discount_amount=discount_amount,
            final_amount=pay_amount,
            extra_days_from_promo=extra_days_from_promo,
        )
        request = await self._uow.payment_requests.get_by_id_with_relations(request.id)
        if request is None:
            raise PaymentRequestNotFoundError("Не удалось создать заявку.")

        logger.info(
            "Payment request created",
            extra={"request_id": request.id, "user_id": user.id, "plan_id": plan.id},
        )
        return self._to_info(request)

    async def create_renewal_request(
        self,
        *,
        telegram_id: int,
        plan_id: int,
        vpn_account_id: int | None,
        receipt_file_id: str | None,
        receipt_file_type: str,
        user_comment: str | None,
        receipt_message_id: int | None = None,
        promo_code_id: int | None = None,
        original_amount: Decimal | None = None,
        discount_amount: Decimal = Decimal("0"),
        final_amount: Decimal | None = None,
        extra_days_from_promo: int = 0,
    ) -> PaymentRequestInfo:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            raise PaymentRequestNotFoundError("Пользователь не найден. Отправьте /start.")

        existing = await self._uow.payment_requests.get_pending_renewal_by_user_id(user.id)
        if existing is not None:
            raise PaymentRequestDuplicateError(
                "⏳ У вас уже есть заявка на продление на проверке.",
            )

        plan = await self._uow.plans.get_by_id(plan_id)
        if plan is None or not plan.is_active:
            raise PaymentRequestNotFoundError("Тариф недоступен.")

        renewal_account: VpnAccount | None = None
        if vpn_account_id is not None:
            renewal_account = await self._uow.vpn_accounts.get_renewal_candidate(
                user.id,
                vpn_account_id=vpn_account_id,
            )
        else:
            renewal_account = await self._uow.vpn_accounts.get_renewal_candidate(user.id)

        resolved_account_id = renewal_account.id if renewal_account is not None else None

        pay_amount = final_amount if final_amount is not None else plan.price
        request = await self._uow.payment_requests.create(
            user_id=user.id,
            plan_id=plan.id,
            request_type=PaymentRequestType.RENEWAL.value,
            amount=pay_amount,
            receipt_file_id=receipt_file_id,
            receipt_file_type=receipt_file_type,
            user_comment=user_comment,
            receipt_message_id=receipt_message_id,
            vpn_account_id=resolved_account_id,
            promo_code_id=promo_code_id,
            original_amount=original_amount if original_amount is not None else plan.price,
            discount_amount=discount_amount,
            final_amount=pay_amount,
            extra_days_from_promo=extra_days_from_promo,
        )
        request = await self._uow.payment_requests.get_by_id_with_relations(request.id)
        if request is None:
            raise PaymentRequestNotFoundError("Не удалось создать заявку.")

        logger.info(
            "Renewal payment request created",
            extra={
                "request_id": request.id,
                "user_id": user.id,
                "plan_id": plan.id,
                "vpn_account_id": resolved_account_id,
            },
        )
        return self._to_info(request)

    async def preview_renewal_expiry(
        self,
        *,
        plan_duration_days: int,
        vpn_account: VpnAccount | None,
        extra_days: int = 0,
    ) -> tuple[datetime, datetime | None]:
        now = datetime.now(UTC)
        expected, _ = ExpiryCalculator.calculate(
            now=now,
            duration_days=plan_duration_days + extra_days,
            account=vpn_account,
        )
        current = vpn_account.expiry_date if vpn_account is not None else None
        return expected, current

    async def list_pending_requests(self) -> list[PaymentRequestInfo]:
        requests = await self._uow.payment_requests.list_pending_with_relations()
        return [self._to_info(item) for item in requests]

    async def list_partial_provisioning_requests(self) -> list[PaymentRequestInfo]:
        requests = await self._uow.payment_requests.list_partial_provisioning_with_relations()
        return [self._to_info(item) for item in requests]

    async def get_request(self, request_id: int) -> PaymentRequestInfo:
        request = await self._uow.payment_requests.get_by_id_with_relations(request_id)
        if request is None:
            raise PaymentRequestNotFoundError("Заявка не найдена.")
        return self._to_info(request)

    async def approve_request(self, request_id: int, *, admin_telegram_id: int) -> PaymentRequestInfo:
        request = await self._get_pending_or_raise(request_id)
        await self._uow.payment_requests.approve(request, admin_telegram_id=admin_telegram_id)
        refreshed = await self._uow.payment_requests.get_by_id_with_relations(request_id)
        if refreshed is None:
            raise PaymentRequestNotFoundError("Заявка не найдена.")
        logger.info("Payment request approved", extra={"request_id": request_id})
        return self._to_info(refreshed)

    async def reject_request(self, request_id: int, *, admin_telegram_id: int) -> PaymentRequestInfo:
        request = await self._get_pending_or_raise(request_id)
        await self._uow.payment_requests.reject(request, admin_telegram_id=admin_telegram_id)
        refreshed = await self._uow.payment_requests.get_by_id_with_relations(request_id)
        if refreshed is None:
            raise PaymentRequestNotFoundError("Заявка не найдена.")
        logger.info("Payment request rejected", extra={"request_id": request_id})
        return self._to_info(refreshed)

    async def _get_pending_or_raise(self, request_id: int) -> PaymentRequest:
        request = await self._uow.payment_requests.get_by_id(request_id)
        if request is None:
            raise PaymentRequestNotFoundError("Заявка не найдена.")
        if request.status != PaymentRequestStatus.PENDING.value:
            raise PaymentRequestAlreadyProcessedError("Эта заявка уже обработана.")
        return request

    def format_purchase_checkout(
        self,
        *,
        plan_details: str,
        payment_details: str,
        has_payment_details: bool,
        is_free: bool = False,
        promo_summary: str | None = None,
    ) -> str:
        if is_free:
            return plan_details
        lines = [plan_details, ""]
        if promo_summary:
            lines.append(promo_summary)
            lines.append("")
        if has_payment_details:
            lines.append("💳 <b>Реквизиты оплаты:</b>")
            lines.append(payment_details)
        else:
            lines.append(payment_details)
        lines.append("\nПосле оплаты нажмите «✅ Я оплатил» и отправьте чек.")
        return "\n".join(lines)

    def format_renewal_checkout(
        self,
        *,
        plan_details: str,
        payment_details: str,
        has_payment_details: bool,
        current_expiry: datetime | None,
        expected_expiry: datetime,
        has_account: bool,
        promo_summary: str | None = None,
    ) -> str:
        lines = ["🔄 <b>Продление VPN</b>", "", plan_details, ""]
        if promo_summary:
            lines.append(promo_summary)
            lines.append("")
        if has_account and current_expiry is not None:
            lines.append(
                f"📅 Текущая дата окончания: {self._format_datetime(current_expiry)}"
            )
        elif not has_account:
            lines.append("📅 Активный VPN не найден — срок будет рассчитан от текущей даты.")
        lines.append(f"📅 Ожидаемая дата после продления: {self._format_datetime(expected_expiry)}")
        lines.append("")
        if has_payment_details:
            lines.append("💳 <b>Реквизиты оплаты:</b>")
            lines.append(payment_details)
        else:
            lines.append(payment_details)
        lines.append("\nПосле оплаты нажмите «✅ Я оплатил продление» и отправьте чек.")
        return "\n".join(lines)

    def format_pending_list(self, requests: list[PaymentRequestInfo]) -> str:
        if not requests:
            return "📭 Новых заявок нет."

        lines = ["📥 <b>Заявки на проверке</b>", ""]
        for item in requests:
            request_type = resolve_request_type_label(item)
            username = f"@{item.username}" if item.username else "—"
            devices = self._format_devices(item.plan_ip_limit)
            created = self._format_datetime(item.created_at)
            duration = item.effective_duration_days or item.plan_duration_days
            amount_line = f"{item.amount:.0f} ₽"
            if item.promo_code and item.original_amount is not None:
                amount_line = f"{item.amount:.0f} ₽ (было {item.original_amount:.0f})"
            lines.append(
                f"<b>#{item.id}</b> · {request_type}\n"
                f"👤 {item.user_full_name} ({username})\n"
                f"🆔 <code>{item.telegram_id}</code>\n"
                f"📦 {item.plan_name} · {amount_line} · {duration} дн.\n"
                f"📱 {devices} · 🕐 {created}"
            )
            lines.append("")
        return "\n".join(lines).strip()

    def format_partial_provisioning_list(self, requests: list[PaymentRequestInfo]) -> str:
        if not requests:
            return "📭 Частичных выдач нет."

        lines = ["⚠️ <b>Частичная выдача VPN</b>", ""]
        for item in requests:
            username = f"@{item.username}" if item.username else "—"
            lines.append(
                f"<b>#{item.id}</b>\n"
                f"👤 {item.user_full_name} ({username})\n"
                f"📦 {item.plan_name} · VPN ID: {item.vpn_account_id or '—'}"
            )
            lines.append("")
        return "\n".join(lines).strip()

    def format_request_details(self, item: PaymentRequestInfo) -> str:
        traffic = self._format_traffic(item.plan_traffic_limit_gb)
        devices = self._format_devices(item.plan_ip_limit)
        request_type = resolve_request_type_label(item)
        status = STATUS_LABELS.get(item.status, item.status)
        username = f"@{item.username}" if item.username else "—"

        lines = [
            f"<b>Заявка #{item.id}</b>",
            f"📌 Статус: {status}",
            f"📋 Тип: {request_type}",
            "",
            f"👤 Клиент: {item.user_full_name}",
            f"🔗 Username: {username}",
            f"🆔 Telegram ID: <code>{item.telegram_id}</code>",
            "",
            f"📦 Тариф: {item.plan_name}",
            f"💰 Сумма: {item.amount:.0f} ₽",
        ]
        if item.promo_code:
            lines.extend(self._promo_detail_lines(item))
        lines.extend(
            [
            f"📅 Срок: {item.effective_duration_days or item.plan_duration_days} дн.",
            f"📶 Трафик: {traffic}",
            f"📱 Устройств: {devices}",
            f"🖥 Режим выдачи: {ISSUING_MODE_LABELS.get(item.plan_issuing_mode, item.plan_issuing_mode)}",
            "",
            f"🕐 Создана: {self._format_datetime(item.created_at)}",
            ]
        )
        if item.target_display_name:
            lines.append(f"🏷 Название подписки: {item.target_display_name}")
        if item.target_vpn_account_name:
            lines.append(f"👤 Имя VPN: <code>{item.target_vpn_account_name}</code>")
        if item.request_type == PaymentRequestType.RENEWAL.value:
            if item.renewal_display_name or item.renewal_vpn_account_name:
                title = item.renewal_display_name or item.renewal_vpn_account_name
                lines.append(f"🔄 Продление: {title}")
            if item.renewal_vpn_account_name:
                lines.append(f"👤 Текущий VPN: <code>{item.renewal_vpn_account_name}</code>")
            if item.current_expiry_at is not None:
                lines.append(
                    f"📅 Текущий срок VPN: {self._format_datetime(item.current_expiry_at)}"
                )
            if item.expected_expiry_at is not None:
                lines.append(
                    f"📅 Ожидаемый срок после продления: {self._format_datetime(item.expected_expiry_at)}"
                )
        if item.user_comment:
            lines.append(f"💬 Комментарий: {item.user_comment}")
        if item.receipt_file_type == ReceiptFileType.TEXT.value and item.user_comment:
            lines.append("🧾 Чек: текстовый комментарий выше.")
        return "\n".join(lines)

    def format_receipt_caption(self, item: PaymentRequestInfo) -> str:
        return f"🧾 Чек по заявке #{item.id} · {item.user_full_name} · {item.plan_name}"

    def format_admin_new_request_notification(self, item: PaymentRequestInfo) -> str:
        if item.request_type == PaymentRequestType.RENEWAL.value:
            header = "📥 Новая заявка на продление"
        elif item.target_vpn_account_name:
            header = "📥 Новая заявка: отдельная подписка"
        else:
            header = "📥 Новая заявка на оплату"
        client = self._format_admin_client_handle(item)
        receipt = RECEIPT_TYPE_LABELS.get(item.receipt_file_type or "", "—")
        return "\n".join(
            [
                header,
                f"👤 Клиент: {client}",
                f"🆔 User ID: <code>{item.telegram_id}</code>",
                f"💰 Тариф: {item.plan_name}",
                f"💵 Сумма: {item.amount:.0f} ₽"
                + (f" (было {item.original_amount:.0f} ₽)" if item.original_amount and item.discount_amount > 0 else ""),
                f"🧾 Чек: {receipt}",
                f"🕒 Время: {self._format_datetime(item.created_at)}",
            ],
        )

    @staticmethod
    def _format_admin_client_handle(item: PaymentRequestInfo) -> str:
        if item.username:
            return f"@{item.username}"
        name = (item.user_full_name or "").strip()
        if not name or name == "Пользователь":
            return "Пользователь"
        return name.split()[0]

    @staticmethod
    def _format_traffic(gb: int) -> str:
        return "Безлимит" if gb <= 0 else f"{gb} ГБ"

    @staticmethod
    def _format_devices(limit: int) -> str:
        return "безлимит" if limit <= 0 else f"{limit} устр."

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def _user_full_name(user: User) -> str:
        parts = [user.first_name, user.last_name]
        return " ".join(part for part in parts if part) or "Пользователь"

    def _to_info(self, request: PaymentRequest) -> PaymentRequestInfo:
        user = request.user
        plan = request.plan
        if user is None or plan is None:
            raise PaymentRequestNotFoundError("Данные заявки неполные.")

        renewal_account = request.vpn_account
        current_expiry_at: datetime | None = None
        expected_expiry_at: datetime | None = None
        extra_days = request.extra_days_from_promo or 0
        effective_duration = plan.duration_days + extra_days
        if request.request_type == PaymentRequestType.RENEWAL.value:
            if renewal_account is not None:
                current_expiry_at = renewal_account.expiry_date
            expected_expiry_at, _ = ExpiryCalculator.calculate(
                now=datetime.now(UTC),
                duration_days=effective_duration,
                account=renewal_account,
            )

        renewal_vpn_account_name: str | None = None
        renewal_display_name: str | None = None
        if renewal_account is not None:
            renewal_vpn_account_name = renewal_account.vpn_account_name
            renewal_display_name = renewal_account.display_name

        promo_code_str = request.promo_code.code if request.promo_code is not None else None

        return PaymentRequestInfo(
            id=request.id,
            user_id=request.user_id,
            plan_id=request.plan_id,
            request_type=request.request_type,
            status=request.status,
            amount=request.amount,
            promo_code_id=request.promo_code_id,
            promo_code=promo_code_str,
            original_amount=request.original_amount,
            discount_amount=request.discount_amount,
            final_amount=request.final_amount,
            extra_days_from_promo=extra_days,
            effective_duration_days=effective_duration,
            receipt_file_id=request.receipt_file_id,
            receipt_file_type=request.receipt_file_type,
            user_comment=request.user_comment,
            created_at=request.created_at,
            approved_at=request.approved_at,
            rejected_at=request.rejected_at,
            processed_by_telegram_id=request.processed_by_telegram_id,
            user_full_name=self._user_full_name(user),
            username=user.username,
            telegram_id=user.telegram_id,
            plan_name=plan.name,
            plan_duration_days=plan.duration_days,
            plan_traffic_limit_gb=plan.traffic_limit_gb,
            plan_ip_limit=plan.ip_limit,
            plan_issuing_mode=plan.issuing_mode,
            vpn_account_id=request.vpn_account_id,
            target_vpn_account_name=request.target_vpn_account_name,
            target_display_name=request.target_display_name,
            renewal_vpn_account_name=renewal_vpn_account_name,
            renewal_display_name=renewal_display_name,
            current_expiry_at=current_expiry_at,
            expected_expiry_at=expected_expiry_at,
        )

    @staticmethod
    def _promo_detail_lines(item: PaymentRequestInfo) -> list[str]:
        lines = [
            f"🎁 Промокод: <code>{item.promo_code}</code>",
        ]
        if item.original_amount is not None:
            lines.append(f"💵 Было: {item.original_amount:.0f} ₽")
        if item.discount_amount > 0:
            lines.append(f"🏷 Скидка: {item.discount_amount:.0f} ₽")
        if item.final_amount is not None:
            lines.append(f"✅ К оплате: {item.final_amount:.0f} ₽")
        if item.extra_days_from_promo > 0:
            lines.append(f"➕ Доп. дни: {item.extra_days_from_promo}")
        return lines

    def format_separate_checkout(
        self,
        *,
        plan_details: str,
        payment_details: str,
        has_payment_details: bool,
        display_name: str,
        vpn_account_name: str,
        promo_summary: str | None = None,
    ) -> str:
        lines = [
            "➕ <b>Отдельная подписка</b>",
            "",
            plan_details,
            "",
            f"🏷 Название: <b>{html.escape(display_name, quote=False)}</b>",
            f"👤 Имя в панели: <code>{html.escape(vpn_account_name, quote=False)}</code>",
            "",
        ]
        if promo_summary:
            lines.append(promo_summary)
            lines.append("")
        if has_payment_details:
            lines.append("💳 <b>Реквизиты оплаты:</b>")
            lines.append(payment_details)
        else:
            lines.append(payment_details)
        lines.append("\nПосле оплаты нажмите «✅ Я оплатил» и отправьте чек.")
        return "\n".join(lines)
