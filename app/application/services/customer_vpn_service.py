from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto.customer_vpn import CustomerVpnOverview, PanelOverview
from app.application.exceptions import PaymentRequestNotFoundError
from app.config.settings import Settings
from app.domain.enums import VpnAccountStatus
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.uow import UnitOfWork
from app.infrastructure.integrations.marzban.service import MarzbanService
from app.infrastructure.integrations.xui.service import XuiService

logger = logging.getLogger(__name__)

NO_VPN_TEXT = "У вас пока нет активного VPN. Нажмите «🛒 Купить VPN»."
TRAFFIC_REFRESH_WARNING = "⚠️ Не удалось обновить трафик, показаны сохранённые данные."
LINK_FETCH_ERROR = "Не удалось получить ссылку. Свяжитесь с поддержкой."

STATUS_LABELS: dict[str, str] = {
    VpnAccountStatus.ACTIVE.value: "Активен",
    VpnAccountStatus.EXPIRED.value: "Истёк",
    VpnAccountStatus.DISABLED.value: "Отключён",
    VpnAccountStatus.DELETED.value: "Удалён",
}


class CustomerVpnService:
    """Customer-facing VPN account overview, links, and live panel refresh."""

    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        marzban: MarzbanService | None,
        xui: XuiService | None,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._marzban = marzban if settings.marzban_enabled else None
        self._xui = xui if settings.xui_enabled else None

    async def get_primary_account(self, telegram_id: int) -> VpnAccount | None:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            return None
        accounts = await self._uow.vpn_accounts.list_by_user_id(user.id, include_deleted=False)
        return accounts[0] if accounts else None

    async def get_account_for_user(self, telegram_id: int, account_id: int) -> VpnAccount | None:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            return None
        account = await self._uow.vpn_accounts.get_by_id(account_id)
        if account is None or account.user_id != user.id:
            return None
        if account.status == VpnAccountStatus.DELETED.value or account.deleted_at is not None:
            return None
        return account

    async def build_overview(self, telegram_id: int) -> CustomerVpnOverview | None:
        account = await self.get_primary_account(telegram_id)
        if account is None:
            return None

        now = datetime.now(UTC)
        used_bytes = account.traffic_used_bytes
        refresh_failed = False

        live_used, failed = await self._fetch_live_traffic_bytes(account)
        if failed:
            refresh_failed = True
        elif live_used is not None:
            used_bytes = live_used

        plan_name = None
        if account.plan_id is not None:
            plan = await self._uow.plans.get_by_id(account.plan_id)
            if plan is not None:
                plan_name = plan.name

        status_label = self._status_label(account, now)
        days_left = self._days_left(account.expiry_date, now)

        return CustomerVpnOverview(
            account_id=account.id,
            vpn_account_name=account.vpn_account_name,
            status_label=status_label,
            plan_name=plan_name,
            expiry_at=account.expiry_date,
            days_left=days_left,
            traffic_display=self._format_used_traffic(used_bytes),
            traffic_limit_display=self._format_traffic_limit(account.traffic_limit_gb),
            ip_limit_display=self._format_ip_limit(account.ip_limit),
            panels=self._panel_overviews(account),
            traffic_refresh_failed=refresh_failed,
        )

    async def resolve_subscription_links(self, account: VpnAccount) -> dict[str, str]:
        links: dict[str, str] = {}

        if account.marzban_username:
            url = account.marzban_subscription_url
            if self._marzban is not None:
                try:
                    fresh = await self._marzban.get_subscription_link(account.marzban_username)
                    if fresh:
                        url = fresh
                except Exception as exc:
                    logger.warning(
                        "Marzban subscription refresh failed",
                        extra={"account_id": account.id, "error": str(exc)[:300]},
                    )
            if url:
                links["Marzban"] = url

        if account.xui_email:
            url = account.xui_subscription_url
            if self._xui is not None:
                try:
                    fresh = await self._xui.get_subscription_link(account.xui_email)
                    if fresh:
                        url = fresh
                except Exception as exc:
                    logger.warning(
                        "3x-ui subscription refresh failed",
                        extra={"account_id": account.id, "error": str(exc)[:300]},
                    )
            if url:
                links["3x-ui"] = url

        return links

    def format_overview_message(self, overview: CustomerVpnOverview) -> str:
        expiry = (
            overview.expiry_at.strftime("%d.%m.%Y %H:%M")
            if overview.expiry_at is not None
            else "—"
        )
        days_left = (
            f"{overview.days_left} дн."
            if overview.days_left is not None
            else "—"
        )
        panels = ", ".join(panel.name for panel in overview.panels if panel.configured) or "—"

        lines = [
            "📊 <b>Мой VPN</b>",
            "",
            f"👤 Аккаунт: <code>{overview.vpn_account_name}</code>",
            f"📌 Статус: {overview.status_label}",
            f"📦 Тариф: {overview.plan_name or '—'}",
            f"📅 Действует до: {expiry}",
            f"⏳ Осталось: {days_left}",
            f"📶 Трафик: {overview.traffic_display} / {overview.traffic_limit_display}",
            f"📱 Устройств: {overview.ip_limit_display}",
            f"🖥 Панели: {panels}",
        ]
        if overview.traffic_refresh_failed:
            lines.append("")
            lines.append(TRAFFIC_REFRESH_WARNING)
        return "\n".join(lines)

    def format_links_message(self, links: dict[str, str]) -> str:
        if not links:
            return LINK_FETCH_ERROR
        lines = ["🔗 <b>Ваши ссылки для подключения:</b>", ""]
        for panel, url in links.items():
            lines.append(f"<b>{panel}</b>:\n{url}")
            lines.append("")
        return "\n".join(lines).strip()

    async def require_account(self, telegram_id: int, account_id: int) -> VpnAccount:
        account = await self.get_account_for_user(telegram_id, account_id)
        if account is None:
            raise PaymentRequestNotFoundError("VPN-аккаунт не найден.")
        return account

    async def _fetch_live_traffic_bytes(self, account: VpnAccount) -> tuple[int | None, bool]:
        total = 0
        fetched_any = False
        failed = False

        if account.marzban_username and self._marzban is not None:
            try:
                traffic = await self._marzban.get_traffic(account.marzban_username)
                if traffic is not None:
                    total += traffic.used_traffic_bytes
                    fetched_any = True
            except Exception as exc:
                failed = True
                logger.warning(
                    "Marzban traffic fetch failed",
                    extra={"account_id": account.id, "error": str(exc)[:300]},
                )

        if account.xui_email and self._xui is not None:
            try:
                traffic = await self._xui.get_traffic(account.xui_email)
                if traffic is not None:
                    total += traffic.used_traffic_bytes
                    fetched_any = True
            except Exception as exc:
                failed = True
                logger.warning(
                    "3x-ui traffic fetch failed",
                    extra={"account_id": account.id, "error": str(exc)[:300]},
                )

        if fetched_any:
            return total, failed
        return None, failed

    def _panel_overviews(self, account: VpnAccount) -> list[PanelOverview]:
        panels: list[PanelOverview] = []
        if account.marzban_username:
            panels.append(
                PanelOverview(
                    name="Marzban",
                    configured=True,
                    status=account.marzban_status,
                )
            )
        if account.xui_email:
            panels.append(
                PanelOverview(
                    name="3x-ui",
                    configured=True,
                    status=account.xui_status,
                )
            )
        return panels

    @staticmethod
    def _status_label(account: VpnAccount, now: datetime) -> str:
        expiry = account.expiry_date
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry is not None and expiry <= now:
            return "Истёк"
        return STATUS_LABELS.get(account.status, account.status)

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
    def _format_used_traffic(used_bytes: int) -> str:
        if used_bytes <= 0:
            return "0 ГБ"
        gb = used_bytes / (1024**3)
        if gb < 0.01:
            return f"{used_bytes / (1024**2):.1f} МБ"
        return f"{gb:.2f} ГБ"

    @staticmethod
    def _format_traffic_limit(limit_gb: int) -> str:
        return "Безлимит" if limit_gb <= 0 else f"{limit_gb} ГБ"

    @staticmethod
    def _format_ip_limit(ip_limit: int) -> str:
        return "Безлимит" if ip_limit <= 0 else str(ip_limit)
