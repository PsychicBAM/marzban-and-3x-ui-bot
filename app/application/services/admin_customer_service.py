from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto.admin_customer import (
    AdminCustomerActionOutcome,
    ClientCardInfo,
    ClientListItem,
    PanelActionResult,
    PanelStatusInfo,
    VpnUserStats,
)
from app.application.exceptions import PaymentRequestNotFoundError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.customer_vpn_service import CustomerVpnService
from app.application.services.expiry_calculator import ExpiryCalculator
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.config.settings import Settings
from app.domain.enums import AdminActionType, PaymentRequestStatus, VpnAccountStatus
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.repositories.admin_customer_repo import (
    PAGE_SIZE,
    STATUS_ACTIVE,
    STATUS_DELETED,
    STATUS_DISABLED,
    STATUS_EXPIRED,
    AdminCustomerRepository,
)
from app.infrastructure.db.uow import UnitOfWork
from app.infrastructure.integrations.marzban.service import MarzbanService
from app.infrastructure.integrations.xui.service import XuiService

logger = logging.getLogger(__name__)

STATUS_LABELS: dict[str, str] = {
    STATUS_ACTIVE: "Активен",
    STATUS_EXPIRED: "Истёк",
    STATUS_DISABLED: "Отключён",
    STATUS_DELETED: "Удалён",
}

PAYMENT_STATUS_LABELS: dict[str, str] = {
    PaymentRequestStatus.PENDING.value: "⏳ На проверке",
    PaymentRequestStatus.APPROVED.value: "✅ Подтверждена",
    PaymentRequestStatus.REJECTED.value: "❌ Отклонена",
    PaymentRequestStatus.PROVISIONING_FAILED.value: "⚠️ Ошибка выдачи",
    PaymentRequestStatus.PROVISIONING_PARTIAL.value: "⚠️ Частичная выдача",
}


class AdminCustomerService:
    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        customer_vpn_service: CustomerVpnService,
        admin_log_service: AdminLogService,
        notification_service: ProvisioningNotificationService,
        marzban: MarzbanService | None,
        xui: XuiService | None,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._customer_vpn = customer_vpn_service
        self._admin_log = admin_log_service
        self._notification = notification_service
        self._marzban = marzban if settings.marzban_enabled else None
        self._xui = xui if settings.xui_enabled else None
        self._repo: AdminCustomerRepository = uow.admin_customers

    async def get_stats(self) -> VpnUserStats:
        now = datetime.now(UTC)
        total = await self._repo.count_all_users()
        latest = await self._repo.list_latest_non_deleted_accounts()
        counts = {STATUS_ACTIVE: 0, STATUS_EXPIRED: 0, STATUS_DISABLED: 0}
        for account in latest:
            category = self._repo.categorize_account(account, now=now)
            if category in counts:
                counts[category] += 1
        deleted_ids = await self._repo.list_latest_deleted_only_user_ids()
        return VpnUserStats(
            total_users=total,
            active_vpn=counts[STATUS_ACTIVE],
            expired_vpn=counts[STATUS_EXPIRED],
            disabled_vpn=counts[STATUS_DISABLED],
            deleted_vpn=len(deleted_ids),
        )

    async def list_clients(self, status_filter: str, *, page: int) -> tuple[list[ClientListItem], int]:
        now = datetime.now(UTC)
        items: list[tuple[User, VpnAccount | None]] = []

        if status_filter == STATUS_DELETED:
            deleted_user_ids = await self._repo.list_latest_deleted_only_user_ids()
            users_map = await self._repo.get_users_by_ids(deleted_user_ids)
            for user_id in deleted_user_ids:
                user = users_map.get(user_id)
                if user is None:
                    continue
                account = await self._repo.get_latest_deleted_account_for_user(user_id)
                items.append((user, account))
        else:
            latest = await self._repo.list_latest_non_deleted_accounts()
            user_ids = [account.user_id for account in latest]
            users_map = await self._repo.get_users_by_ids(user_ids)
            for account in latest:
                category = self._repo.categorize_account(account, now=now)
                if category != status_filter:
                    continue
                user = users_map.get(account.user_id)
                if user is None:
                    continue
                items.append((user, account))

        total = len(items)
        start = page * PAGE_SIZE
        page_items = items[start : start + PAGE_SIZE]
        return [self._to_list_item(user, account, now=now) for user, account in page_items], total

    async def search_clients(self, query: str) -> list[ClientListItem]:
        now = datetime.now(UTC)
        users = await self._repo.search_users(query)
        results: list[ClientListItem] = []
        for user in users:
            account = await self._uow.vpn_accounts.get_renewal_candidate(user.id)
            if account is None:
                account = await self._repo.get_latest_deleted_account_for_user(user.id)
            results.append(self._to_list_item(user, account, now=now))
        return results

    async def get_client_card(self, user_id: int) -> ClientCardInfo:
        user = await self._uow.users.get_by_id(user_id)
        if user is None:
            raise PaymentRequestNotFoundError("Клиент не найден.")

        account = await self._uow.vpn_accounts.get_renewal_candidate(user.id)
        is_deleted = False
        if account is None:
            account = await self._repo.get_latest_deleted_account_for_user(user.id)
            is_deleted = account is not None

        now = datetime.now(UTC)
        latest_payment = await self._uow.payment_requests.get_latest_by_user_id(user.id)
        payment_label = None
        if latest_payment is not None:
            payment_label = PAYMENT_STATUS_LABELS.get(latest_payment.status, latest_payment.status)

        plan_name = None
        traffic_display = "—"
        traffic_limit_display = "—"
        ip_limit_display = "—"
        traffic_refresh_failed = False
        expiry_at = None
        days_left = None
        status_label = "Нет VPN"
        vpn_account_name = None
        vpn_account_id = None
        panel_statuses: list[PanelStatusInfo] = []

        if account is not None:
            vpn_account_id = account.id
            vpn_account_name = account.vpn_account_name
            category = self._repo.categorize_account(account, now=now)
            status_label = STATUS_LABELS.get(category, category)
            expiry_at = account.expiry_date
            days_left = self._days_left(expiry_at, now)
            traffic_limit_display = self._format_traffic_limit(account.traffic_limit_gb)
            ip_limit_display = self._format_ip_limit(account.ip_limit)
            panel_statuses = self._panel_statuses(account)

            if not is_deleted:
                overview = await self._customer_vpn.build_overview(user.telegram_id)
                if overview is not None and overview.account_id == account.id:
                    traffic_display = overview.traffic_display
                    traffic_refresh_failed = overview.traffic_refresh_failed
                else:
                    traffic_display = CustomerVpnService._format_used_traffic(account.traffic_used_bytes)
            else:
                traffic_display = CustomerVpnService._format_used_traffic(account.traffic_used_bytes)

            if account.plan_id is not None:
                plan = await self._uow.plans.get_by_id(account.plan_id)
                if plan is not None:
                    plan_name = plan.name

        return ClientCardInfo(
            user_id=user.id,
            telegram_id=user.telegram_id,
            full_name=self._full_name(user),
            username=user.username,
            registered_at=user.created_at,
            latest_payment_status=payment_label,
            vpn_account_id=vpn_account_id,
            vpn_account_name=vpn_account_name,
            plan_name=plan_name,
            status_label=status_label,
            expiry_at=expiry_at,
            days_left=days_left,
            traffic_display=traffic_display,
            traffic_limit_display=traffic_limit_display,
            ip_limit_display=ip_limit_display,
            panel_statuses=panel_statuses,
            traffic_refresh_failed=traffic_refresh_failed,
            is_deleted=is_deleted,
        )

    async def send_links_to_customer(
        self,
        user_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_active_account(user_id)
        links = await self._customer_vpn.resolve_subscription_links(account)
        if not links:
            return AdminCustomerActionOutcome(
                success=False,
                admin_message="❌ Не удалось получить ссылки для клиента.",
            )

        lines = ["🔗 <b>Ваши ссылки для подключения:</b>", ""]
        for panel, url in links.items():
            lines.append(f"<b>{panel}</b>:\n{url}\n")
        customer_message = "\n".join(lines).strip()

        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.ADMIN_SENT_VPN_LINK,
            details={"user_id": user_id, "vpn_account_id": account.id, "panels": list(links)},
        )
        return AdminCustomerActionOutcome(
            success=True,
            admin_message=f"✅ Ссылки отправлены клиенту ({user.telegram_id}).",
            customer_message=customer_message,
            customer_telegram_id=user.telegram_id,
        )

    async def send_qr_to_customer(
        self,
        user_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_active_account(user_id)
        links = await self._customer_vpn.resolve_subscription_links(account)
        if not links:
            return AdminCustomerActionOutcome(
                success=False,
                admin_message="❌ Не удалось получить ссылки для QR.",
            )

        deliveries = self._notification.build_panel_qr_deliveries_from_links(links)
        failed = [item.panel for item in deliveries if not item.succeeded]
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.ADMIN_SENT_VPN_QR,
            details={
                "user_id": user_id,
                "vpn_account_id": account.id,
                "panels": list(links),
                "qr_failed": failed,
            },
        )
        admin_msg = "✅ QR отправлен клиенту." if not failed else f"⚠️ QR частично: ошибки — {', '.join(failed)}"
        return AdminCustomerActionOutcome(
            success=bool(deliveries),
            admin_message=admin_msg,
            panel_results=[
                PanelActionResult(
                    panel=item.panel,
                    success=item.succeeded,
                    detail=item.error or "отправлен",
                )
                for item in deliveries
            ],
            customer_telegram_id=user.telegram_id,
            qr_deliveries=deliveries,
        )

    async def disable_client(
        self,
        user_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(user_id)
        results = await self._disable_panels(account)
        await self._uow.vpn_accounts.update_admin_state(
            account,
            status=VpnAccountStatus.DISABLED.value,
            marzban_status="disabled" if account.marzban_username else None,
            xui_status="disabled" if account.xui_email else None,
        )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.CLIENT_DISABLED,
            details={"user_id": user_id, "vpn_account_id": account.id},
        )
        return AdminCustomerActionOutcome(
            success=any(item.success for item in results) or not results,
            admin_message=self._format_panel_outcome("Отключение", results),
            panel_results=results,
            customer_message="🚫 Ваш VPN временно отключён. Свяжитесь с поддержкой.",
            customer_telegram_id=user.telegram_id,
        )

    async def enable_client(
        self,
        user_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(user_id)
        now = datetime.now(UTC)
        expiry = account.expiry_date
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry is not None and expiry <= now:
            return AdminCustomerActionOutcome(
                success=False,
                admin_message="⚠️ Срок действия уже истёк. Сначала продлите клиента.",
            )

        results = await self._enable_panels(account)
        await self._uow.vpn_accounts.update_admin_state(
            account,
            status=VpnAccountStatus.ACTIVE.value,
            marzban_status="active" if account.marzban_username else None,
            xui_status="active" if account.xui_email else None,
        )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.CLIENT_ENABLED,
            details={"user_id": user_id, "vpn_account_id": account.id},
        )
        return AdminCustomerActionOutcome(
            success=any(item.success for item in results) or not results,
            admin_message=self._format_panel_outcome("Активация", results),
            panel_results=results,
            customer_message="✅ Ваш VPN снова активен.",
            customer_telegram_id=user.telegram_id,
        )

    async def delete_client(
        self,
        user_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(user_id)
        results = await self._delete_panels(account)
        await self._uow.vpn_accounts.soft_delete(account, clear_customer_links=True)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.CLIENT_DELETED,
            details={"user_id": user_id, "vpn_account_id": account.id},
        )
        return AdminCustomerActionOutcome(
            success=True,
            admin_message=self._format_panel_outcome("Удаление", results),
            panel_results=results,
            customer_message="🗑 Ваш VPN был удалён администратором.",
            customer_telegram_id=user.telegram_id,
        )

    async def change_ip_limit(
        self,
        user_id: int,
        *,
        new_limit: int,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(user_id)
        old_limit = account.ip_limit
        results = await self._update_ip_limit_panels(account, new_limit)
        await self._uow.vpn_accounts.update_admin_state(account, ip_limit=new_limit)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.IP_LIMIT_CHANGED,
            details={
                "user_id": user_id,
                "vpn_account_id": account.id,
                "old": old_limit,
                "new": new_limit,
            },
        )
        return AdminCustomerActionOutcome(
            success=any(item.success for item in results) or not results,
            admin_message=self._format_panel_outcome(
                f"IP limit: {old_limit} → {new_limit}",
                results,
            ),
            panel_results=results,
        )

    async def clear_ips(
        self,
        user_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(user_id)
        results = await self._clear_ips_panels(account)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.VPN_ACCOUNT_IPS_CLEARED,
            details={"user_id": user_id, "vpn_account_id": account.id},
        )
        return AdminCustomerActionOutcome(
            success=any(item.success for item in results) or not results,
            admin_message=self._format_panel_outcome("Очистка IP", results),
            panel_results=results,
        )

    async def manual_extend(
        self,
        user_id: int,
        *,
        days: int,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        if days <= 0:
            return AdminCustomerActionOutcome(success=False, admin_message="Количество дней должно быть > 0.")

        user, account = await self._require_manageable_account(user_id)
        if account.status == VpnAccountStatus.DELETED.value or account.deleted_at is not None:
            return AdminCustomerActionOutcome(
                success=False,
                admin_message=(
                    "⚠️ Аккаунт удалён. Продление невозможно — "
                    "клиенту нужна новая покупка/выдача."
                ),
            )

        now = datetime.now(UTC)
        old_expiry = account.expiry_date
        new_expiry, _ = ExpiryCalculator.calculate(now=now, duration_days=days, account=account)
        results = await self._extend_panels(account, new_expiry)
        status = VpnAccountStatus.ACTIVE.value
        if new_expiry > now:
            status = VpnAccountStatus.ACTIVE.value
        await self._uow.vpn_accounts.update_admin_state(
            account,
            expiry_date=new_expiry,
            status=status,
        )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.VPN_ACCOUNT_MANUALLY_EXTENDED,
            details={
                "user_id": user_id,
                "vpn_account_id": account.id,
                "days": days,
                "old_expiry": old_expiry.isoformat() if old_expiry else None,
                "new_expiry": new_expiry.isoformat(),
            },
        )
        old_text = old_expiry.strftime("%d.%m.%Y %H:%M") if old_expiry else "—"
        new_text = new_expiry.strftime("%d.%m.%Y %H:%M")
        return AdminCustomerActionOutcome(
            success=any(item.success for item in results) or not results,
            admin_message=(
                f"{self._format_panel_outcome('Продление', results)}\n"
                f"📅 Было: {old_text}\n📅 Стало: {new_text}"
            ),
            panel_results=results,
            customer_message="✅ Ваш VPN продлён администратором.",
            customer_telegram_id=user.telegram_id,
        )

    def format_dashboard(self, stats: VpnUserStats) -> str:
        return (
            "👥 <b>Клиенты</b>\n\n"
            f"Всего пользователей: <b>{stats.total_users}</b>\n"
            f"✅ С активным VPN: <b>{stats.active_vpn}</b>\n"
            f"⛔ С истёкшим VPN: <b>{stats.expired_vpn}</b>\n"
            f"🚫 С отключённым VPN: <b>{stats.disabled_vpn}</b>\n"
            f"🗑 С удалённым VPN: <b>{stats.deleted_vpn}</b>"
        )

    def format_client_list(
        self,
        status_filter: str,
        items: list[ClientListItem],
        *,
        page: int,
        total: int,
    ) -> str:
        title = {
            STATUS_ACTIVE: "✅ Активные клиенты",
            STATUS_EXPIRED: "⛔ Истёкшие клиенты",
            STATUS_DISABLED: "🚫 Отключённые клиенты",
            STATUS_DELETED: "🗑 Удалённые клиенты",
        }.get(status_filter, "Клиенты")
        if not items:
            return f"{title}\n\nСписок пуст."
        lines = [f"<b>{title}</b>", f"Страница {page + 1}", ""]
        for item in items:
            expiry = item.expiry_at.strftime("%d.%m.%Y") if item.expiry_at else "—"
            username = f"@{item.username}" if item.username else "—"
            panels = self._panel_badges(item.has_marzban, item.has_xui)
            lines.append(
                f"• {item.display_name} ({username})\n"
                f"  {item.vpn_status_label} · до {expiry} · {panels}"
            )
        lines.append(f"\nПоказано {len(items)} из {total}")
        return "\n".join(lines)

    def format_client_card(self, card: ClientCardInfo) -> str:
        username = f"@{card.username}" if card.username else "—"
        expiry = card.expiry_at.strftime("%d.%m.%Y %H:%M") if card.expiry_at else "—"
        days = f"{card.days_left} дн." if card.days_left is not None else "—"
        panels = "\n".join(f"  • {p.panel}: {p.state}" for p in card.panel_statuses) or "  • —"

        lines = [
            f"<b>Карточка клиента</b>",
            "",
            f"👤 {card.full_name}",
            f"🔗 Username: {username}",
            f"🆔 Telegram ID: <code>{card.telegram_id}</code>",
            f"📅 Регистрация: {card.registered_at.strftime('%d.%m.%Y %H:%M')}",
        ]
        if card.latest_payment_status:
            lines.append(f"💳 Последняя заявка: {card.latest_payment_status}")
        lines.extend(
            [
                "",
                f"🔑 VPN: <code>{card.vpn_account_name or '—'}</code>",
                f"📦 Тариф: {card.plan_name or '—'}",
                f"📌 Статус: {card.status_label}",
                f"📅 Истекает: {expiry}",
                f"⏳ Осталось: {days}",
                f"📶 Трафик: {card.traffic_display} / {card.traffic_limit_display}",
                f"📱 Устройств: {card.ip_limit_display}",
                f"🖥 Панели:\n{panels}",
            ]
        )
        if card.traffic_refresh_failed:
            lines.append("\n⚠️ Не удалось обновить трафик, показаны сохранённые данные.")
        return "\n".join(lines)

    async def _require_active_account(self, user_id: int) -> tuple[User, VpnAccount]:
        user = await self._uow.users.get_by_id(user_id)
        if user is None:
            raise PaymentRequestNotFoundError("Клиент не найден.")
        account = await self._uow.vpn_accounts.get_renewal_candidate(user.id)
        if account is None:
            raise PaymentRequestNotFoundError("У клиента нет активного VPN-аккаунта.")
        return user, account

    async def _require_manageable_account(self, user_id: int) -> tuple[User, VpnAccount]:
        user = await self._uow.users.get_by_id(user_id)
        if user is None:
            raise PaymentRequestNotFoundError("Клиент не найден.")
        account = await self._uow.vpn_accounts.get_renewal_candidate(user.id)
        if account is None:
            raise PaymentRequestNotFoundError("У клиента нет VPN-аккаунта для управления.")
        return user, account

    async def _disable_panels(self, account: VpnAccount) -> list[PanelActionResult]:
        results: list[PanelActionResult] = []
        if account.marzban_username and self._marzban:
            try:
                await self._marzban.disable_user(account.marzban_username)
                results.append(PanelActionResult("Marzban", True, "отключён"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, str(exc)[:200]))
        elif account.marzban_username:
            results.append(PanelActionResult("Marzban", False, "панель не настроена"))
        if account.xui_email and self._xui:
            try:
                await self._xui.disable_client(account.xui_email)
                results.append(PanelActionResult("3x-ui", True, "отключён"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, str(exc)[:200]))
        elif account.xui_email:
            results.append(PanelActionResult("3x-ui", False, "панель не настроена"))
        return results

    async def _enable_panels(self, account: VpnAccount) -> list[PanelActionResult]:
        results: list[PanelActionResult] = []
        if account.marzban_username and self._marzban:
            try:
                await self._marzban.enable_user(account.marzban_username)
                results.append(PanelActionResult("Marzban", True, "активирован"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, str(exc)[:200]))
        elif account.marzban_username:
            results.append(PanelActionResult("Marzban", False, "панель не настроена"))
        if account.xui_email and self._xui:
            try:
                await self._xui.enable_client(account.xui_email)
                results.append(PanelActionResult("3x-ui", True, "активирован"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, str(exc)[:200]))
        elif account.xui_email:
            results.append(PanelActionResult("3x-ui", False, "панель не настроена"))
        return results

    async def _delete_panels(self, account: VpnAccount) -> list[PanelActionResult]:
        results: list[PanelActionResult] = []
        if account.marzban_username and self._marzban:
            try:
                await self._marzban.delete_user(account.marzban_username)
                results.append(PanelActionResult("Marzban", True, "удалён"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, str(exc)[:200]))
        elif account.marzban_username:
            results.append(PanelActionResult("Marzban", False, "панель не настроена"))
        if account.xui_email and self._xui:
            try:
                await self._xui.delete_client(account.xui_email)
                results.append(PanelActionResult("3x-ui", True, "удалён"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, str(exc)[:200]))
        elif account.xui_email:
            results.append(PanelActionResult("3x-ui", False, "панель не настроена"))
        return results

    async def _update_ip_limit_panels(self, account: VpnAccount, new_limit: int) -> list[PanelActionResult]:
        results: list[PanelActionResult] = []
        expiry = account.expiry_date or datetime.now(UTC)
        if account.marzban_username and self._marzban:
            try:
                await self._marzban.update_user(
                    username=account.marzban_username,
                    expire_at=expiry,
                    data_limit_gb=account.traffic_limit_gb,
                    ip_limit=new_limit,
                    enable=account.status == VpnAccountStatus.ACTIVE.value,
                )
                results.append(PanelActionResult("Marzban", True, f"limit={new_limit}"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, str(exc)[:200]))
        if account.xui_email and self._xui:
            try:
                await self._xui.update_client(
                    email=account.xui_email,
                    expiry_time=expiry,
                    total_gb=account.traffic_limit_gb,
                    limit_ip=new_limit,
                    enable=account.status == VpnAccountStatus.ACTIVE.value,
                )
                results.append(PanelActionResult("3x-ui", True, f"limit={new_limit}"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, str(exc)[:200]))
        return results

    async def _clear_ips_panels(self, account: VpnAccount) -> list[PanelActionResult]:
        results: list[PanelActionResult] = []
        if account.marzban_username and self._marzban:
            try:
                ok = await self._marzban.reset_user_ips(account.marzban_username)
                results.append(PanelActionResult("Marzban", ok, "очищено" if ok else "не удалось"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, str(exc)[:200]))
        if account.xui_email and self._xui:
            try:
                ok = await self._xui.reset_client_ips(account.xui_email)
                results.append(PanelActionResult("3x-ui", ok, "очищено" if ok else "не удалось"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, str(exc)[:200]))
        return results

    async def _extend_panels(self, account: VpnAccount, new_expiry: datetime) -> list[PanelActionResult]:
        results: list[PanelActionResult] = []
        enable = account.status != VpnAccountStatus.DISABLED.value
        if account.marzban_username and self._marzban:
            try:
                await self._marzban.update_user(
                    username=account.marzban_username,
                    expire_at=new_expiry,
                    data_limit_gb=account.traffic_limit_gb,
                    ip_limit=account.ip_limit,
                    enable=enable,
                )
                results.append(PanelActionResult("Marzban", True, "обновлён"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, str(exc)[:200]))
        if account.xui_email and self._xui:
            try:
                await self._xui.update_client(
                    email=account.xui_email,
                    expiry_time=new_expiry,
                    total_gb=account.traffic_limit_gb,
                    limit_ip=account.ip_limit,
                    enable=enable,
                )
                results.append(PanelActionResult("3x-ui", True, "обновлён"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, str(exc)[:200]))
        return results

    def _to_list_item(
        self,
        user: User,
        account: VpnAccount | None,
        *,
        now: datetime,
    ) -> ClientListItem:
        if account is None:
            return ClientListItem(
                user_id=user.id,
                telegram_id=user.telegram_id,
                display_name=self._full_name(user),
                username=user.username,
                vpn_account_id=None,
                vpn_status_label="Нет VPN",
                expiry_at=None,
                has_marzban=False,
                has_xui=False,
            )
        category = self._repo.categorize_account(account, now=now)
        return ClientListItem(
            user_id=user.id,
            telegram_id=user.telegram_id,
            display_name=self._full_name(user),
            username=user.username,
            vpn_account_id=account.id,
            vpn_status_label=STATUS_LABELS.get(category, category),
            expiry_at=account.expiry_date,
            has_marzban=bool(account.marzban_username),
            has_xui=bool(account.xui_email),
        )

    @staticmethod
    def _panel_statuses(account: VpnAccount) -> list[PanelStatusInfo]:
        panels: list[PanelStatusInfo] = []
        if account.marzban_username:
            state = account.marzban_status or "настроен"
            if account.status == VpnAccountStatus.DELETED.value:
                state = "deleted"
            panels.append(PanelStatusInfo("Marzban", state))
        else:
            panels.append(PanelStatusInfo("Marzban", "missing"))
        if account.xui_email:
            state = account.xui_status or "настроен"
            if account.status == VpnAccountStatus.DELETED.value:
                state = "deleted"
            panels.append(PanelStatusInfo("3x-ui", state))
        else:
            panels.append(PanelStatusInfo("3x-ui", "missing"))
        return panels

    @staticmethod
    def _full_name(user: User) -> str:
        parts = [user.first_name, user.last_name]
        return " ".join(part for part in parts if part) or "Пользователь"

    @staticmethod
    def _days_left(expiry: datetime | None, now: datetime) -> int | None:
        if expiry is None:
            return None
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry <= now:
            return 0
        return max(0, (expiry - now).days)

    @staticmethod
    def _format_traffic_limit(limit_gb: int) -> str:
        return "Безлимит" if limit_gb <= 0 else f"{limit_gb} ГБ"

    @staticmethod
    def _format_ip_limit(ip_limit: int) -> str:
        return "Безлимит" if ip_limit <= 0 else str(ip_limit)

    @staticmethod
    def _panel_badges(has_marzban: bool, has_xui: bool) -> str:
        parts = []
        if has_marzban:
            parts.append("M")
        if has_xui:
            parts.append("XUI")
        return "/".join(parts) if parts else "—"

    @staticmethod
    def _format_panel_outcome(title: str, results: list[PanelActionResult]) -> str:
        if not results:
            return f"✅ {title}: обновлено в БД (панели не настроены)."
        lines = [f"<b>{title}</b>"]
        for item in results:
            mark = "✅" if item.success else "❌"
            lines.append(f"{mark} {item.panel}: {item.detail}")
        return "\n".join(lines)
