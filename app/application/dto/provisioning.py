from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import ProvisionAction


@dataclass(slots=True)
class PanelProvisionResult:
    panel: str
    success: bool
    created: bool
    subscription_url: str | None = None
    external_id: str | None = None
    error: str | None = None


@dataclass(slots=True)
class ProvisioningResult:
    success: bool
    partial: bool
    failed: bool
    vpn_account_id: int | None
    vpn_account_name: str
    plan_name: str
    expiry_at: datetime
    traffic_limit_gb: int
    ip_limit: int
    action: ProvisionAction
    panel_results: list[PanelProvisionResult] = field(default_factory=list)
    subscription_links: dict[str, str] = field(default_factory=dict)

    def customer_message(self, *, free: bool = False) -> str:
        panels = ", ".join(
            result.panel for result in self.panel_results if result.success
        ) or "—"
        traffic = "Безлимит" if self.traffic_limit_gb <= 0 else f"{self.traffic_limit_gb} ГБ"
        devices = "Безлимит" if self.ip_limit <= 0 else str(self.ip_limit)
        expiry = self.expiry_at.strftime("%d.%m.%Y %H:%M")

        if free:
            header = "🎁 Бесплатный доступ активирован. Ваш VPN создан."
        elif self.action == ProvisionAction.CREATE_NEW:
            header = "✅ Оплата подтверждена. Ваша подписка создана."
        else:
            header = "✅ Оплата подтверждена. Ваш VPN продлён."

        lines = [
            header,
            "",
            f"👤 Подписка: {self.vpn_account_name}",
            f"📦 Тариф: {self.plan_name}",
            f"📅 Действует до: {expiry}",
            f"📱 Устройств: {devices}",
            f"📶 Трафик: {traffic}",
            f"🖥 Панели: {panels}",
        ]
        for panel, url in self.subscription_links.items():
            if url:
                lines.append(f"\n🔗 {panel}: {url}")
        return "\n".join(lines)

    def admin_message(self) -> str:
        action_label = {
            ProvisionAction.CREATE_NEW: "создан",
            ProvisionAction.RENEW_ACTIVE: "продлён (с учётом оставшихся дней)",
            ProvisionAction.RENEW_FROM_NOW: "продлён с текущей даты",
            ProvisionAction.RENEW_REENABLE_DISABLED: "продлён и активирован",
        }.get(self.action, self.action.value)

        lines = [
            f"✅ Заявка обработана. VPN {action_label}.",
            f"📅 Истекает: {self.expiry_at.strftime('%d.%m.%Y %H:%M')}",
        ]
        for result in self.panel_results:
            if result.success:
                state = "создан" if result.created else "обновлён"
                lines.append(f"✅ {result.panel}: {state}")
            else:
                lines.append(f"❌ {result.panel}: {result.error or 'ошибка'}")
        if self.partial:
            lines.append("\n⚠️ Частичная выдача: не все панели настроены.")
        return "\n".join(lines)
