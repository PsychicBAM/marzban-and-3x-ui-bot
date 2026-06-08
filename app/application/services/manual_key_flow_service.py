from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.dto.manual_provision import ManualProvisionRequest, ManualProvisionResult, ProvisionProfile
from app.application.services.plan_service import ISSUING_MODE_LABELS, PlanService
from app.application.utils.vpn_username import normalize_from_telegram_username, normalize_vpn_account_name
from app.domain.enums import IssuingMode
from app.infrastructure.db.models.user import User
from app.infrastructure.db.uow import UnitOfWork


class ManualKeyFlowService:
    """Validation and formatting helpers for admin manual key FSM."""

    def __init__(self, uow: UnitOfWork, plan_service: PlanService) -> None:
        self._uow = uow
        self._plans = plan_service

    async def search_users(self, query: str) -> list[User]:
        return await self._uow.admin_customers.search_users(query)

    def default_account_name(self, user: User) -> str | None:
        if user.vpn_account_name:
            try:
                return normalize_vpn_account_name(user.vpn_account_name)
            except Exception:
                return None
        return normalize_from_telegram_username(user.username)

    def validate_account_name(self, raw: str) -> str:
        return normalize_vpn_account_name(raw)

    async def user_has_active_account(self, user_id: int) -> bool:
        account = await self._uow.vpn_accounts.get_renewal_candidate(user_id)
        return account is not None

    async def get_renewal_account(self, user_id: int):
        return await self._uow.vpn_accounts.get_renewal_candidate(user_id)

    @staticmethod
    def profile_to_dict(profile: ProvisionProfile) -> dict:
        return {
            "name": profile.name,
            "duration_days": profile.duration_days,
            "traffic_limit_gb": profile.traffic_limit_gb,
            "ip_limit": profile.ip_limit,
            "issuing_mode": profile.issuing_mode,
            "plan_id": profile.plan_id,
        }

    @staticmethod
    def profile_from_dict(data: dict) -> ProvisionProfile:
        return ProvisionProfile(
            name=data["name"],
            duration_days=int(data["duration_days"]),
            traffic_limit_gb=int(data["traffic_limit_gb"]),
            ip_limit=int(data["ip_limit"]),
            issuing_mode=str(data["issuing_mode"]),
            plan_id=data.get("plan_id"),
        )

    def profile_from_plan(self, plan) -> ProvisionProfile:
        return ProvisionProfile(
            name=plan.name,
            duration_days=plan.duration_days,
            traffic_limit_gb=plan.traffic_limit_gb,
            ip_limit=plan.ip_limit,
            issuing_mode=plan.issuing_mode,
            plan_id=plan.id,
        )

    def validate_custom_duration(self, raw: str) -> int:
        value = int(raw.strip())
        if value <= 0:
            raise ValueError("Срок должен быть больше 0.")
        return value

    def validate_custom_int(self, raw: str, *, field: str) -> int:
        value = int(raw.strip())
        if value < 0:
            raise ValueError(f"{field} не может быть отрицательным.")
        return value

    def validate_issuing_mode(self, raw: str) -> str:
        value = raw.strip().lower()
        allowed = {IssuingMode.MARZBAN.value, IssuingMode.XUI.value, IssuingMode.BOTH.value}
        if value not in allowed:
            raise ValueError("Режим выдачи: marzban, xui или both.")
        return value

    def preview_expiry(
        self,
        *,
        duration_days: int,
        extend_existing: bool,
        user_id: int | None,
        renewal_account,
    ) -> datetime:
        now = datetime.now(UTC)
        if extend_existing and renewal_account is not None:
            from app.application.services.expiry_calculator import ExpiryCalculator

            expiry, _ = ExpiryCalculator.calculate(
                now=now,
                duration_days=duration_days,
                account=renewal_account,
            )
            return expiry
        return now + timedelta(days=duration_days)

    def format_confirmation(self, data: dict) -> str:
        mode = data.get("mode")
        mode_label = "Существующий клиент" if mode == "existing" else "Ручной ключ без клиента"
        profile: ProvisionProfile | None = data.get("profile")
        if profile is None:
            return "Данные неполные."

        traffic = "Безлимит" if profile.traffic_limit_gb <= 0 else f"{profile.traffic_limit_gb} ГБ"
        devices = "Безлимит" if profile.ip_limit <= 0 else str(profile.ip_limit)
        issuing = ISSUING_MODE_LABELS.get(profile.issuing_mode, profile.issuing_mode)
        expiry: datetime | None = data.get("preview_expiry")
        expiry_text = expiry.strftime("%d.%m.%Y %H:%M") if expiry else "—"

        lines = [
            "📋 <b>Подтверждение создания ключа</b>",
            "",
            f"🎯 Режим: {mode_label}",
        ]
        if mode == "existing":
            lines.append(f"👤 Клиент: {data.get('target_display_name', '—')}")
            lines.append(f"🆔 Telegram ID: <code>{data.get('target_telegram_id', '—')}</code>")
            extend = data.get("extend_existing")
            if extend is True:
                lines.append("🔄 Действие: продлить существующий аккаунт")
            elif extend is False:
                lines.append("🆕 Действие: создать отдельный новый ключ")
        lines.extend(
            [
                f"🔑 Имя VPN: <code>{data.get('account_name', '—')}</code>",
                f"📦 Тариф/профиль: {profile.name}",
                f"📅 Срок: {profile.duration_days} дн.",
                f"📅 Истекает: {expiry_text}",
                f"📶 Трафик: {traffic}",
                f"📱 Устройств: {devices}",
                f"🖥 Выдача: {issuing}",
            ]
        )
        comment = data.get("admin_comment")
        if comment:
            lines.append(f"💬 Комментарий: {comment}")
        return "\n".join(lines)

    def customer_delivery_message(self, result: ManualProvisionResult) -> str:
        lines = [
            "🔑 <b>Ваш VPN-ключ готов</b>",
            "",
            f"Аккаунт: <code>{result.vpn_account_name}</code>",
            f"Истекает: {result.expiry_at.strftime('%d.%m.%Y %H:%M')}",
            "",
        ]
        for panel, url in result.subscription_links.items():
            lines.append(f"🔗 {panel}:\n{url}")
        return "\n".join(lines)

    def build_request(self, data: dict) -> ManualProvisionRequest:
        profile: ProvisionProfile = data["profile"]
        return ManualProvisionRequest(
            mode=data["mode"],
            user_id=int(data["user_id"]),
            account_name=data["account_name"],
            profile=profile,
            extend_existing=bool(data.get("extend_existing")),
            admin_comment=data.get("admin_comment"),
            target_telegram_id=data.get("target_telegram_id"),
            target_display_name=data.get("target_display_name"),
        )

    def format_success_admin(self, result) -> str:
        lines = [
            "✅ <b>VPN-ключ создан</b>" if result.success else "⚠️ <b>VPN создан частично</b>",
            "",
            f"🔑 Аккаунт: <code>{result.vpn_account_name}</code>",
            f"📅 Истекает: {result.expiry_at.strftime('%d.%m.%Y %H:%M')}",
        ]
        for panel in result.panel_results:
            mark = "✅" if panel.success else "❌"
            lines.append(f"{mark} {panel.panel}: {panel.subscription_url or panel.error or '—'}")
        for panel, url in result.subscription_links.items():
            lines.append(f"\n🔗 {panel}:\n{url}")
        if result.partial:
            lines.append("\n⚠️ Не все панели настроены. Проверьте детали выше.")
        return "\n".join(lines)
