from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.application.dto.customer_vpn import CustomerVpnListItem, CustomerVpnOverview, PanelOverview
from app.application.exceptions import PaymentRequestNotFoundError
from app.config.settings import Settings
from app.domain.enums import VpnAccountStatus
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.uow import UnitOfWork
from app.infrastructure.integrations.marzban.mappers import normalize_marzban_subscription_url
from app.infrastructure.integrations.marzban.service import MarzbanService
from app.infrastructure.integrations.xui.mappers import normalize_xui_subscription_url
from app.infrastructure.integrations.xui.service import XuiService
from app.presentation.i18n import normalize_lang, t

logger = logging.getLogger(__name__)


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
        return await self._uow.vpn_accounts.get_primary_for_user(user.id)

    async def list_subscriptions(self, telegram_id: int, *, lang: str | None = None) -> list[CustomerVpnListItem]:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            return []
        code = normalize_lang(lang)
        now = datetime.now(UTC)
        accounts = await self._uow.vpn_accounts.list_by_user_id(user.id, include_deleted=False)
        items: list[CustomerVpnListItem] = []
        for account in accounts:
            title = self._account_title(account)
            items.append(
                CustomerVpnListItem(
                    account_id=account.id,
                    title=title,
                    vpn_account_name=account.vpn_account_name,
                    status_label=self._status_label(account, now, code),
                    expiry_at=account.expiry_date,
                    is_primary=account.is_primary,
                ),
            )
        return items

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

    async def build_overview(
        self,
        telegram_id: int,
        *,
        account_id: int | None = None,
        lang: str | None = None,
    ) -> CustomerVpnOverview | None:
        if account_id is not None:
            account = await self.get_account_for_user(telegram_id, account_id)
        else:
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

        code = normalize_lang(lang)
        status_label = self._status_label(account, now, code)
        days_left = self._days_left(account.expiry_date, now)

        return CustomerVpnOverview(
            account_id=account.id,
            vpn_account_name=account.vpn_account_name,
            display_name=account.display_name,
            status_label=status_label,
            plan_name=plan_name,
            expiry_at=account.expiry_date,
            days_left=days_left,
            traffic_display=self._format_used_traffic(used_bytes, code),
            traffic_limit_display=self._format_traffic_limit(account.traffic_limit_gb, code),
            ip_limit_display=self._format_ip_limit(account.ip_limit, code),
            panels=self._panel_overviews(account),
            traffic_refresh_failed=refresh_failed,
        )

    async def resolve_subscription_links(self, account: VpnAccount) -> dict[str, str]:
        links: dict[str, str] = {}

        if account.marzban_username:
            url = (account.marzban_subscription_url or "").strip() or None
            subscription_base = (self._settings.marzban_subscription_base_url or "").strip()

            if subscription_base and url:
                url = normalize_marzban_subscription_url(
                    url,
                    subscription_base_url=subscription_base,
                    username=account.marzban_username,
                )
            elif self._marzban is not None:
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
            url = (account.xui_subscription_url or "").strip() or None
            subscription_base = (self._settings.xui_subscription_base_url or "").strip()

            if subscription_base and url:
                url = normalize_xui_subscription_url(
                    url,
                    subscription_base_url=subscription_base,
                    panel_base_url=self._settings.xui_base_url,
                    email=account.xui_email,
                )
            elif self._xui is not None:
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

    def format_overview_message(self, overview: CustomerVpnOverview, *, lang: str | None = None) -> str:
        code = normalize_lang(lang)
        expiry = (
            overview.expiry_at.strftime("%d.%m.%Y %H:%M")
            if overview.expiry_at is not None
            else "—"
        )
        days_left = (
            t(code, "myvpn.days_unit", n=overview.days_left)
            if overview.days_left is not None
            else "—"
        )
        panels = ", ".join(panel.name for panel in overview.panels if panel.configured) or "—"
        title = overview.display_name or overview.vpn_account_name
        lines = [
            t(code, "myvpn.title"),
            "",
            t(code, "myvpn.subscription_label", title=title),
            t(code, "myvpn.account", name=overview.vpn_account_name),
            t(code, "myvpn.status", status=overview.status_label),
            t(code, "myvpn.plan", plan=overview.plan_name or "—"),
            t(code, "myvpn.expiry", expiry=expiry),
            t(code, "myvpn.days_left", days=days_left),
            t(code, "myvpn.traffic_full", used=overview.traffic_display, limit=overview.traffic_limit_display),
            t(code, "myvpn.devices", count=overview.ip_limit_display),
            t(code, "myvpn.panels", panels=panels),
        ]
        if overview.traffic_refresh_failed:
            lines.append("")
            lines.append(t(code, "myvpn.traffic_warning"))
        return "\n".join(lines)

    def format_subscription_list_message(self, items: list[CustomerVpnListItem], *, lang: str | None = None) -> str:
        code = normalize_lang(lang)
        lines = [t(code, "myvpn.list_title"), "", t(code, "myvpn.list_choose")]
        for item in items:
            expiry = item.expiry_at.strftime("%d.%m.%Y") if item.expiry_at else "—"
            primary = t(code, "myvpn.primary_mark") if item.is_primary else ""
            lines.append(
                t(
                    code,
                    "myvpn.subscription_line",
                    title=item.title,
                    primary=primary,
                    status=item.status_label,
                    expiry=expiry,
                )
            )
        return "\n".join(lines)

    @staticmethod
    def _account_title(account: VpnAccount) -> str:
        if account.display_name:
            return account.display_name
        return account.vpn_account_name

    def format_links_message(self, links: dict[str, str], *, lang: str | None = None) -> str:
        code = normalize_lang(lang)
        if not links:
            return t(code, "myvpn.links_error")
        lines = [t(code, "myvpn.links_title"), ""]
        for panel, url in links.items():
            lines.append(t(code, "myvpn.link_line", panel=panel, url=url))
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

    def _status_label(self, account: VpnAccount, now: datetime, lang: str) -> str:
        expiry = account.expiry_date
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry is not None and expiry <= now:
            return t(lang, "myvpn.status.expired")
        key = {
            VpnAccountStatus.ACTIVE.value: "myvpn.status.active",
            VpnAccountStatus.EXPIRED.value: "myvpn.status.expired",
            VpnAccountStatus.DISABLED.value: "myvpn.status.disabled",
            VpnAccountStatus.DELETED.value: "myvpn.status.deleted",
        }.get(account.status)
        if key:
            return t(lang, key)
        return account.status

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
    def _format_used_traffic(used_bytes: int, lang: str = "ru") -> str:
        if used_bytes <= 0:
            return t(lang, "myvpn.traffic.zero")
        gb = used_bytes / (1024**3)
        if gb < 0.01:
            return t(lang, "myvpn.traffic.mb", n=f"{used_bytes / (1024**2):.1f}")
        return t(lang, "myvpn.traffic.gb", n=f"{gb:.2f}")

    @staticmethod
    def _format_traffic_limit(limit_gb: int, lang: str = "ru") -> str:
        if limit_gb <= 0:
            return t(lang, "myvpn.unlimited")
        return t(lang, "myvpn.traffic.gb", n=limit_gb)

    @staticmethod
    def _format_ip_limit(ip_limit: int, lang: str = "ru") -> str:
        if ip_limit <= 0:
            return t(lang, "myvpn.unlimited")
        return str(ip_limit)
