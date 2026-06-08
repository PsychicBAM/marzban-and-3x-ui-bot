from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.application.dto.statistics import StatisticsSnapshot
from app.application.exceptions import StatisticsLoadError
from app.config.settings import Settings
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


class StatisticsService:
    """Aggregate and format admin dashboard statistics."""

    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def build_snapshot(self) -> StatisticsSnapshot:
        try:
            now_utc = datetime.now(UTC)
            tz = ZoneInfo(self._settings.timezone)
            now_local = datetime.now(tz)
            start_today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            start_month_local = start_today_local.replace(day=1)
            start_today_utc = start_today_local.astimezone(UTC)
            start_month_utc = start_month_local.astimezone(UTC)

            users = await self._uow.statistics.get_user_vpn_counts(now=now_utc)
            payments = await self._uow.statistics.get_payment_status_counts()
            revenue = await self._uow.statistics.get_revenue_summary(
                start_today_utc=start_today_utc,
                start_month_utc=start_month_utc,
            )
            vpn_accounts = await self._uow.statistics.get_vpn_account_counts()
            expiring = await self._uow.statistics.count_expiring_soon(now=now_utc)

            return StatisticsSnapshot(
                users=users,
                payments=payments,
                revenue=revenue,
                vpn_accounts=vpn_accounts,
                expiring=expiring,
                generated_at_label=now_local.strftime("%d.%m.%Y %H:%M"),
            )
        except Exception as exc:
            logger.exception("Failed to build statistics snapshot", extra={"error": str(exc)[:300]})
            raise StatisticsLoadError("Не удалось загрузить статистику.") from exc

    async def build_today_payment_summary(self) -> tuple[StatisticsSnapshot, Decimal, list[tuple[str, Decimal]], int]:
        snapshot = await self.build_snapshot()
        tz = ZoneInfo(self._settings.timezone)
        now_local = datetime.now(tz)
        start_today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_today_local = start_today_local + timedelta(days=1)
        total, by_plan, count = await self._uow.statistics.get_revenue_for_period(
            start_utc=start_today_local.astimezone(UTC),
            end_utc=end_today_local.astimezone(UTC),
        )
        return snapshot, total, by_plan, count

    async def build_month_payment_summary(self) -> tuple[StatisticsSnapshot, Decimal, list[tuple[str, Decimal]], int]:
        snapshot = await self.build_snapshot()
        tz = ZoneInfo(self._settings.timezone)
        now_local = datetime.now(tz)
        start_month_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_month_local.month == 12:
            end_month_local = start_month_local.replace(year=start_month_local.year + 1, month=1)
        else:
            end_month_local = start_month_local.replace(month=start_month_local.month + 1)
        total, by_plan, count = await self._uow.statistics.get_revenue_for_period(
            start_utc=start_month_local.astimezone(UTC),
            end_utc=end_month_local.astimezone(UTC),
        )
        return snapshot, total, by_plan, count

    def format_overview(self, snapshot: StatisticsSnapshot) -> str:
        lines = [
            "📊 <b>Статистика</b>",
            f"<i>Обновлено: {snapshot.generated_at_label}</i>",
            "",
            "👥 <b>Пользователи:</b>",
            f"Всего: {snapshot.users.total_users}",
            f"Активных VPN: {snapshot.users.active_vpn}",
            f"Истёкших: {snapshot.users.expired_vpn}",
            f"Отключённых: {snapshot.users.disabled_vpn}",
            f"Удалённых: {snapshot.users.deleted_vpn}",
            "",
            "💰 <b>Оплаты:</b>",
            f"Ожидают: {snapshot.payments.pending}",
            f"Подтверждены: {snapshot.payments.approved}",
            f"Отклонены: {snapshot.payments.rejected}",
            f"Ошибка выдачи: {snapshot.payments.provisioning_failed}",
            f"Частичная выдача: {snapshot.payments.provisioning_partial}",
            "",
            "💵 <b>Доход</b> <i>(только status=approved)</i>:",
            f"Сегодня: {self._money(snapshot.revenue.today)} ₽",
            f"Этот месяц: {self._money(snapshot.revenue.month)} ₽",
            f"Всего: {self._money(snapshot.revenue.total)} ₽",
        ]
        if snapshot.revenue.by_plan:
            lines.append("")
            lines.append("<b>По тарифам:</b>")
            for plan_name, amount in snapshot.revenue.by_plan[:10]:
                lines.append(f"• {plan_name}: {self._money(amount)} ₽")
        lines.extend(
            [
                "",
                "🔐 <b>VPN-аккаунты:</b>",
                f"Всего записей: {snapshot.vpn_accounts.total}",
                f"Marzban: {snapshot.vpn_accounts.marzban}",
                f"3x-ui: {snapshot.vpn_accounts.xui}",
                f"Активные: {snapshot.vpn_accounts.active}",
                f"Истёкшие: {snapshot.vpn_accounts.expired}",
                f"Отключённые: {snapshot.vpn_accounts.disabled}",
                f"Удалённые: {snapshot.vpn_accounts.deleted}",
                "",
                "⏰ <b>Скоро истекают</b> (активные):",
                f"1 день: {snapshot.expiring.in_1_day}",
                f"3 дня: {snapshot.expiring.in_3_days}",
                f"7 дней: {snapshot.expiring.in_7_days}",
            ]
        )
        return "\n".join(lines)

    def format_today_summary(
        self,
        snapshot: StatisticsSnapshot,
        *,
        period_total: Decimal,
        by_plan: list[tuple[str, Decimal]],
        approved_count: int,
    ) -> str:
        lines = [
            "📊 <b>Статистика — сегодня</b>",
            f"<i>Обновлено: {snapshot.generated_at_label}</i>",
            "",
            "💵 <b>Доход за сегодня</b> <i>(только approved)</i>:",
            f"Сумма: {self._money(period_total)} ₽",
            f"Подтверждённых заявок: {approved_count}",
            "",
            "💰 <b>Оплаты (все статусы):</b>",
            f"Ожидают: {snapshot.payments.pending}",
            f"Подтверждены: {snapshot.payments.approved}",
            f"Отклонены: {snapshot.payments.rejected}",
            f"Ошибка выдачи: {snapshot.payments.provisioning_failed}",
            f"Частичная выдача: {snapshot.payments.provisioning_partial}",
        ]
        if by_plan:
            lines.extend(["", "<b>По тарифам за сегодня:</b>"])
            for plan_name, amount in by_plan:
                lines.append(f"• {plan_name}: {self._money(amount)} ₽")
        lines.append("")
        lines.append(
            "<i>provisioning_failed не входит в доход — учитываются только заявки со статусом approved.</i>"
        )
        return "\n".join(lines)

    def format_month_summary(
        self,
        snapshot: StatisticsSnapshot,
        *,
        period_total: Decimal,
        by_plan: list[tuple[str, Decimal]],
        approved_count: int,
    ) -> str:
        lines = [
            "📊 <b>Статистика — этот месяц</b>",
            f"<i>Обновлено: {snapshot.generated_at_label}</i>",
            "",
            "💵 <b>Доход за месяц</b> <i>(только approved)</i>:",
            f"Сумма: {self._money(period_total)} ₽",
            f"Подтверждённых заявок: {approved_count}",
            "",
            "💵 <b>Справочно — всего approved:</b>",
            f"Всего: {self._money(snapshot.revenue.total)} ₽",
        ]
        if by_plan:
            lines.extend(["", "<b>По тарифам за месяц:</b>"])
            for plan_name, amount in by_plan:
                lines.append(f"• {plan_name}: {self._money(amount)} ₽")
        return "\n".join(lines)

    @staticmethod
    def _money(value: Decimal) -> str:
        return f"{value:.0f}"
