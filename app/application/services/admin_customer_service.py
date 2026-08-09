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
from app.application.exceptions import PaymentRequestNotFoundError, VpnPanelError
from app.application.services.admin_log_service import AdminLogService
from app.application.services.customer_vpn_service import CustomerVpnService
from app.application.services.expiry_calculator import ExpiryCalculator
from app.application.services.provisioning_notification_service import ProvisioningNotificationService
from app.config.settings import Settings
from app.domain.enums import AdminActionType, VpnAccountStatus
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.application.utils.admin_client_format import (
    format_compact_list_row,
    normalize_page,
    total_pages,
)
from app.infrastructure.db.repositories.admin_customer_repo import (
    PAGE_SIZE,
    STATUS_ACTIVE,
    STATUS_DELETED,
    STATUS_DISABLED,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
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
        counts = {STATUS_ACTIVE: 0, STATUS_EXPIRED: 0, STATUS_DISABLED: 0, STATUS_DELETED: 0}
        for account in await self._repo.list_all_accounts():
            category = self._repo.categorize_account(account, now=now)
            if category in counts:
                counts[category] += 1
        return VpnUserStats(
            total_users=total,
            active_vpn=counts[STATUS_ACTIVE],
            expired_vpn=counts[STATUS_EXPIRED],
            disabled_vpn=counts[STATUS_DISABLED],
            deleted_vpn=counts[STATUS_DELETED],
        )

    async def list_clients(self, status_filter: str, *, page: int) -> tuple[list[ClientListItem], int, int]:
        now = datetime.now(UTC)
        accounts = await self._repo.list_all_accounts()
        if status_filter == STATUS_EXPIRING_SOON:
            matched = [account for account in accounts if self._repo.is_expiring_soon(account, now=now)]
            matched.sort(
                key=lambda account: account.expiry_date or datetime.max.replace(tzinfo=UTC),
            )
        else:
            matched = [
                account
                for account in accounts
                if self._repo.categorize_account(account, now=now) == status_filter
            ]
        user_ids = list({account.user_id for account in matched})
        users_map = await self._repo.get_users_by_ids(user_ids)
        items: list[tuple[User, VpnAccount]] = []
        for account in matched:
            user = users_map.get(account.user_id)
            if user is None:
                continue
            items.append((user, account))

        total = len(items)
        page = normalize_page(page, total, PAGE_SIZE)
        start = page * PAGE_SIZE
        page_items = items[start : start + PAGE_SIZE]
        return [self._to_list_item(user, account, now=now) for user, account in page_items], total, page

    async def search_clients(self, query: str, *, page: int = 0) -> tuple[list[ClientListItem], int, int]:
        now = datetime.now(UTC)
        requested_page = page
        offset = requested_page * PAGE_SIZE
        pairs, total = await self._repo.search_accounts(query, offset=offset, limit=PAGE_SIZE)
        page = normalize_page(requested_page, total, PAGE_SIZE)
        if page != requested_page:
            offset = page * PAGE_SIZE
            pairs, total = await self._repo.search_accounts(query, offset=offset, limit=PAGE_SIZE)
        items = [self._to_list_item(user, account, now=now) for user, account in pairs]
        return items, total, page

    async def get_client_card(self, vpn_account_id: int) -> ClientCardInfo:
        account = await self._uow.vpn_accounts.get_by_id(vpn_account_id)
        if account is None:
            raise PaymentRequestNotFoundError("Подписка не найдена.")

        user = await self._uow.users.get_by_id(account.user_id)
        if user is None:
            raise PaymentRequestNotFoundError("Клиент не найден.")

        now = datetime.now(UTC)
        is_deleted = (
            account.status == VpnAccountStatus.DELETED.value or account.deleted_at is not None
        )
        category = self._repo.categorize_account(account, now=now)
        status_label = STATUS_LABELS.get(category, category)
        expiry_at = account.expiry_date
        days_left = self._days_left(expiry_at, now)
        traffic_limit_display = self._format_traffic_limit(account.traffic_limit_gb)
        ip_limit_display = self._format_ip_limit(account.ip_limit)
        panel_statuses = self._panel_statuses(account)

        plan_name = None
        if account.plan_id is not None:
            plan = await self._uow.plans.get_by_id(account.plan_id)
            if plan is not None:
                plan_name = plan.name

        traffic_display = CustomerVpnService._format_used_traffic(account.traffic_used_bytes, lang="ru")
        traffic_refresh_failed = False
        if not is_deleted:
            overview = await self._customer_vpn.build_overview(
                user.telegram_id,
                account_id=account.id,
                lang="ru",
            )
            if overview is not None:
                traffic_display = overview.traffic_display
                traffic_refresh_failed = overview.traffic_refresh_failed

        return ClientCardInfo(
            user_id=user.id,
            telegram_id=user.telegram_id,
            full_name=self._full_name(user),
            username=user.username,
            vpn_account_id=account.id,
            subscription_display_name=account.display_name,
            vpn_account_name=account.vpn_account_name,
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
        vpn_account_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_active_account(vpn_account_id)
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
            details={"user_id": user.id, "vpn_account_id": account.id, "panels": list(links)},
        )
        return AdminCustomerActionOutcome(
            success=True,
            admin_message=f"✅ Ссылки отправлены клиенту ({user.telegram_id}).",
            customer_message=customer_message,
            customer_telegram_id=user.telegram_id,
        )

    async def send_qr_to_customer(
        self,
        vpn_account_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_active_account(vpn_account_id)
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
                "user_id": user.id,
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
        vpn_account_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(vpn_account_id)
        results = await self._disable_panels(account)
        panels_configured = bool(results)
        panels_ok = self._panels_succeeded(results)
        db_updated = panels_ok or not panels_configured
        if db_updated:
            await self._uow.vpn_accounts.update_admin_state(
                account,
                status=VpnAccountStatus.DISABLED.value,
                marzban_status="disabled" if account.marzban_username else None,
                xui_status="disabled" if account.xui_email else None,
            )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.CLIENT_DISABLED,
            details={"user_id": user.id, "vpn_account_id": account.id},
        )
        admin_message = self._append_db_panel_warning(
            self._format_panel_outcome("Отключение", results),
            results,
            db_updated=db_updated,
        )
        return AdminCustomerActionOutcome(
            success=panels_ok or not panels_configured,
            admin_message=admin_message,
            panel_results=results,
            customer_message="🚫 Ваш VPN временно отключён. Свяжитесь с поддержкой." if db_updated else None,
            customer_telegram_id=user.telegram_id if db_updated else None,
        )

    async def enable_client(
        self,
        vpn_account_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(vpn_account_id)
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
        panels_configured = bool(results)
        panels_ok = self._panels_succeeded(results)
        db_updated = panels_ok or not panels_configured
        if db_updated:
            await self._uow.vpn_accounts.update_admin_state(
                account,
                status=VpnAccountStatus.ACTIVE.value,
                marzban_status="active" if account.marzban_username else None,
                xui_status="active" if account.xui_email else None,
            )
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.CLIENT_ENABLED,
            details={"user_id": user.id, "vpn_account_id": account.id},
        )
        admin_message = self._append_db_panel_warning(
            self._format_panel_outcome("Активация", results),
            results,
            db_updated=db_updated,
        )
        return AdminCustomerActionOutcome(
            success=panels_ok or not panels_configured,
            admin_message=admin_message,
            panel_results=results,
            customer_message="✅ Ваш VPN снова активен." if db_updated else None,
            customer_telegram_id=user.telegram_id if db_updated else None,
        )

    async def delete_client(
        self,
        vpn_account_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(vpn_account_id)
        results = await self._delete_panels(account)
        await self._uow.vpn_accounts.soft_delete(account, clear_customer_links=True)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.CLIENT_DELETED,
            details={"user_id": user.id, "vpn_account_id": account.id},
        )
        panels_ok = all(item.success for item in results) if results else True
        return AdminCustomerActionOutcome(
            success=panels_ok,
            admin_message=self._format_panel_outcome("Удаление", results),
            panel_results=results,
            customer_message="🗑 Ваш VPN был удалён администратором.",
            customer_telegram_id=user.telegram_id,
        )

    async def change_ip_limit(
        self,
        vpn_account_id: int,
        *,
        new_limit: int,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(vpn_account_id)
        old_limit = account.ip_limit
        results = await self._update_ip_limit_panels(account, new_limit)
        panels_configured = bool(results)
        panels_ok = self._panels_succeeded(results)
        db_updated = panels_ok or not panels_configured
        if db_updated:
            await self._uow.vpn_accounts.update_admin_state(account, ip_limit=new_limit)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.IP_LIMIT_CHANGED,
            details={
                "user_id": user.id,
                "vpn_account_id": account.id,
                "old": old_limit,
                "new": new_limit,
            },
        )
        admin_message = self._append_db_panel_warning(
            self._format_panel_outcome(
                f"IP limit: {old_limit} → {new_limit}",
                results,
            ),
            results,
            db_updated=db_updated,
        )
        if panels_configured and not panels_ok:
            admin_message = (
                f"{admin_message}\n⚠️ БД не обновлена: ни одна панель не применила изменение"
            )
        return AdminCustomerActionOutcome(
            success=panels_ok or not panels_configured,
            admin_message=admin_message,
            panel_results=results,
        )

    async def clear_ips(
        self,
        vpn_account_id: int,
        *,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        user, account = await self._require_manageable_account(vpn_account_id)
        results = await self._clear_ips_panels(account)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.VPN_ACCOUNT_IPS_CLEARED,
            details={"user_id": user.id, "vpn_account_id": account.id},
        )
        return AdminCustomerActionOutcome(
            success=any(item.success for item in results) or not results,
            admin_message=self._format_panel_outcome("Очистка IP", results),
            panel_results=results,
        )

    async def manual_extend(
        self,
        vpn_account_id: int,
        *,
        days: int,
        admin_telegram_id: int,
    ) -> AdminCustomerActionOutcome:
        if days <= 0:
            return AdminCustomerActionOutcome(success=False, admin_message="Количество дней должно быть > 0.")

        user, account = await self._require_manageable_account(vpn_account_id)
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
                "user_id": user.id,
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
            f"✅ Активных подписок VPN: <b>{stats.active_vpn}</b>\n"
            f"⛔ Истёкших подписок VPN: <b>{stats.expired_vpn}</b>\n"
            f"🚫 Отключённых подписок VPN: <b>{stats.disabled_vpn}</b>\n"
            f"🗑 Удалённых подписок VPN: <b>{stats.deleted_vpn}</b>"
        )

    def format_client_list(
        self,
        status_filter: str,
        items: list[ClientListItem],
        *,
        page: int,
        total: int,
    ) -> str:
        return self._format_compact_list(
            self._list_title(status_filter),
            items,
            page=page,
            total=total,
        )

    def format_search_results(
        self,
        query: str,
        items: list[ClientListItem],
        *,
        page: int,
        total: int,
    ) -> str:
        title = f"🔎 Поиск: <code>{query}</code>"
        return self._format_compact_list(title, items, page=page, total=total)

    @staticmethod
    def _list_title(status_filter: str) -> str:
        return {
            STATUS_ACTIVE: "✅ Активные подписки",
            STATUS_EXPIRED: "⛔ Истёкшие подписки",
            STATUS_DISABLED: "🚫 Отключённые подписки",
            STATUS_DELETED: "🗑 Удалённые подписки",
            STATUS_EXPIRING_SOON: "⏳ Истекают скоро (≤7 дн.)",
        }.get(status_filter, "Подписки")

    @staticmethod
    def _format_compact_list(
        title: str,
        items: list[ClientListItem],
        *,
        page: int,
        total: int,
    ) -> str:
        pages = total_pages(total, PAGE_SIZE)
        if not items:
            return f"<b>{title}</b>\n\nСписок пуст."
        lines = [f"<b>{title}</b>", f"Стр. {page + 1}/{pages} · всего {total}", ""]
        start_index = page * PAGE_SIZE
        for offset, item in enumerate(items, start=1):
            lines.append(format_compact_list_row(start_index + offset, item))
        return "\n".join(lines)

    def format_client_card(self, card: ClientCardInfo) -> str:
        expiry = card.expiry_at.strftime("%d.%m.%Y %H:%M") if card.expiry_at else "—"
        days = f"{card.days_left} дн." if card.days_left is not None else "—"
        panels = "\n".join(f"  • {p.panel}: {p.state}" for p in card.panel_statuses) or "  • —"
        subscription_label = card.subscription_display_name or "—"

        lines = [
            "<b>Карточка подписки</b>",
            "",
            f"👤 Клиент: {self._client_handle(card)}",
            f"🆔 Telegram ID: <code>{card.telegram_id}</code>",
            f"🔑 Подписка: {subscription_label}",
            f"🧩 VPN-аккаунт: <code>{card.vpn_account_name}</code>",
            f"📌 Статус: {card.status_label}",
            f"📅 Истекает: {expiry} ({days})",
            f"📊 Трафик: {card.traffic_display} / {card.traffic_limit_display} · "
            f"IP limit: {card.ip_limit_display}",
            f"🖥 Панели:\n{panels}",
        ]
        if card.plan_name:
            lines.insert(7, f"📦 Тариф: {card.plan_name}")
        if card.traffic_refresh_failed:
            lines.append("\n⚠️ Не удалось обновить трафик, показаны сохранённые данные.")
        return "\n".join(lines)

    async def _require_active_account(self, vpn_account_id: int) -> tuple[User, VpnAccount]:
        user, account = await self._require_account_with_user(vpn_account_id)
        if account.status == VpnAccountStatus.DELETED.value or account.deleted_at is not None:
            raise PaymentRequestNotFoundError("Подписка удалена.")
        return user, account

    async def _require_manageable_account(self, vpn_account_id: int) -> tuple[User, VpnAccount]:
        user, account = await self._require_account_with_user(vpn_account_id)
        if account.status == VpnAccountStatus.DELETED.value or account.deleted_at is not None:
            raise PaymentRequestNotFoundError("Подписка удалена — действие недоступно.")
        return user, account

    async def _require_account_with_user(self, vpn_account_id: int) -> tuple[User, VpnAccount]:
        account = await self._uow.vpn_accounts.get_by_id(vpn_account_id)
        if account is None:
            raise PaymentRequestNotFoundError("Подписка не найдена.")
        user = await self._uow.users.get_by_id(account.user_id)
        if user is None:
            raise PaymentRequestNotFoundError("Клиент не найден.")
        return user, account

    async def _disable_panels(self, account: VpnAccount) -> list[PanelActionResult]:
        results: list[PanelActionResult] = []
        if account.marzban_username and self._marzban:
            try:
                await self._marzban.disable_user(account.marzban_username)
                results.append(PanelActionResult("Marzban", True, "отключён"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, self._panel_error_detail(exc)))
        elif account.marzban_username:
            results.append(PanelActionResult("Marzban", False, "панель не настроена"))
        if account.xui_email and self._xui:
            try:
                await self._xui.disable_client(account.xui_email)
                results.append(PanelActionResult("3x-ui", True, "отключён"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, self._panel_error_detail(exc)))
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
                results.append(PanelActionResult("Marzban", False, self._panel_error_detail(exc)))
        elif account.marzban_username:
            results.append(PanelActionResult("Marzban", False, "панель не настроена"))
        if account.xui_email and self._xui:
            try:
                await self._xui.enable_client(account.xui_email)
                results.append(PanelActionResult("3x-ui", True, "активирован"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, self._panel_error_detail(exc)))
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
                results.append(PanelActionResult("Marzban", False, self._panel_error_detail(exc)))
        elif account.marzban_username:
            results.append(PanelActionResult("Marzban", False, "панель не настроена"))
        if account.xui_email and self._xui:
            try:
                await self._xui.delete_client(
                    account.xui_email,
                    client_uuid=account.xui_client_uuid,
                )
                results.append(PanelActionResult("3x-ui", True, "удалён"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, self._panel_error_detail(exc)))
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
                    verify_ip_limit=True,
                )
                results.append(PanelActionResult("Marzban", True, f"limit={new_limit}"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, self._panel_error_detail(exc)))
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
                results.append(PanelActionResult("3x-ui", False, self._panel_error_detail(exc)))
        return results

    async def _clear_ips_panels(self, account: VpnAccount) -> list[PanelActionResult]:
        results: list[PanelActionResult] = []
        if account.marzban_username and self._marzban:
            try:
                ok = await self._marzban.reset_user_ips(account.marzban_username)
                results.append(PanelActionResult("Marzban", ok, "очищено" if ok else "не удалось"))
            except Exception as exc:
                results.append(PanelActionResult("Marzban", False, self._panel_error_detail(exc)))
        if account.xui_email and self._xui:
            try:
                ok = await self._xui.reset_client_ips(account.xui_email)
                results.append(PanelActionResult("3x-ui", ok, "очищено" if ok else "не удалось"))
            except Exception as exc:
                results.append(PanelActionResult("3x-ui", False, self._panel_error_detail(exc)))
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
                results.append(PanelActionResult("Marzban", False, self._panel_error_detail(exc)))
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
                results.append(PanelActionResult("3x-ui", False, self._panel_error_detail(exc)))
        return results

    def _to_list_item(
        self,
        user: User,
        account: VpnAccount,
        *,
        now: datetime,
    ) -> ClientListItem:
        category = self._repo.categorize_account(account, now=now)
        return ClientListItem(
            user_id=user.id,
            telegram_id=user.telegram_id,
            customer_name=self._full_name(user),
            username=user.username,
            vpn_account_id=account.id,
            subscription_display_name=account.display_name,
            vpn_account_name=account.vpn_account_name,
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
    def _client_handle(card: ClientCardInfo) -> str:
        from app.application.utils.admin_client_format import format_admin_customer_handle

        return format_admin_customer_handle(
            full_name=card.full_name,
            username=card.username,
            telegram_id=card.telegram_id,
        )

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
    def _panel_error_detail(exc: Exception) -> str:
        if isinstance(exc, VpnPanelError):
            return exc.message[:200]
        return str(exc)[:200]

    @staticmethod
    def _panels_succeeded(results: list[PanelActionResult]) -> bool:
        return any(item.success for item in results)

    @staticmethod
    def _append_db_panel_warning(message: str, results: list[PanelActionResult], *, db_updated: bool) -> str:
        if not db_updated or not results:
            return message
        if all(item.success for item in results):
            return message
        if any(item.success for item in results):
            return f"{message}\n⚠️ БД обновлена, но не все панели применили изменение"
        return message

    @staticmethod
    def _format_panel_outcome(title: str, results: list[PanelActionResult]) -> str:
        if not results:
            return f"✅ {title}: обновлено в БД (панели не настроены)."
        lines = [f"<b>{title}</b>"]
        for item in results:
            mark = "✅" if item.success else "❌"
            lines.append(f"{mark} {item.panel}: {item.detail}")
        return "\n".join(lines)
