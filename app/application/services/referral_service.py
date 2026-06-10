from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from app.application.dto.referral import (
    ReferralCustomerStats,
    ReferralNotification,
    ReferralProcessOutcome,
    ReferralRewardInfo,
    ReferralSettingsInfo,
)
from app.application.exceptions import ReferralError
from app.application.services.admin_customer_service import AdminCustomerService
from app.application.services.admin_log_service import AdminLogService
from app.application.utils.referral_code import encode_referral_code
from app.config.settings import Settings
from app.domain.enums import (
    AdminActionType,
    PaymentRequestType,
    ReferralRewardStatus,
    ReferralRewardType,
)
from app.infrastructure.db.models.payment_request import PaymentRequest
from app.infrastructure.db.models.referral import ReferralReward, ReferralSettings
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

BOOL_YES = "да"
BOOL_NO = "нет"


@dataclass(slots=True)
class ReferralApplyOutcome:
    applied_count: int
    pending_count: int
    message: str
    notifications: list[ReferralNotification]


class ReferralService:
    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        admin_log_service: AdminLogService,
        admin_customer_service: AdminCustomerService | None = None,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._admin_log = admin_log_service
        self._admin_customer = admin_customer_service

    async def get_settings(self) -> ReferralSettingsInfo:
        row = await self._uow.referrals.get_settings()
        return self._settings_to_info(row)

    async def attach_referrer_on_register(
        self,
        *,
        new_user: User,
        referral_code: str | None,
    ) -> None:
        if not referral_code or new_user.referred_by_user_id is not None:
            return
        cfg = await self._uow.referrals.get_settings()
        if not cfg.is_enabled:
            return

        referrer = await self._uow.users.get_by_referral_code(referral_code)
        if referrer is None:
            return
        if referrer.id == new_user.id or referrer.telegram_id == new_user.telegram_id:
            return

        await self._uow.users.set_referred_by(new_user, referrer.id)
        await self._uow.referrals.create_event(
            referrer_user_id=referrer.id,
            referred_user_id=new_user.id,
        )
        await self._admin_log.log(
            admin_telegram_id=0,
            action=AdminActionType.REFERRAL_REGISTERED,
            details={
                "referrer_user_id": referrer.id,
                "referred_user_id": new_user.id,
                "referral_code": referral_code,
            },
        )

    async def ensure_referral_code(self, user: User) -> str:
        if user.referral_code:
            return user.referral_code
        code = encode_referral_code(user.id)
        await self._uow.users.set_referral_code(user, code)
        return code

    async def build_customer_stats(self, user: User, *, bot_username: str) -> ReferralCustomerStats:
        code = await self.ensure_referral_code(user)
        cfg = await self._uow.referrals.get_settings()
        link = f"https://t.me/{bot_username}?start=ref_{code}"
        invited = await self._uow.referrals.count_invited(user.id)
        paid = await self._uow.referrals.count_paid_referrals(user.id)
        earned = await self._uow.referrals.sum_reward_days(
            user.id,
            status=ReferralRewardStatus.APPLIED.value,
        )
        pending = await self._uow.referrals.sum_reward_days(
            user.id,
            status=ReferralRewardStatus.PENDING.value,
        )
        return ReferralCustomerStats(
            referral_code=code,
            referral_link=link,
            invited_count=invited,
            paid_referrals_count=paid,
            earned_bonus_days=earned,
            pending_bonus_days=pending,
            milestone_target=cfg.milestone_paid_referrals,
            milestone_progress=min(paid, cfg.milestone_paid_referrals),
        )

    def format_customer_home(self, stats: ReferralCustomerStats) -> str:
        return (
            "🎁 Пригласить друга\n\n"
            f"🔗 Ваша ссылка:\n{stats.referral_link}\n\n"
            f"👥 Приглашено: {stats.invited_count}\n"
            f"💳 Оплатили: {stats.paid_referrals_count}\n"
            f"✅ Начислено дней: {stats.earned_bonus_days}\n"
            f"⏳ Ожидает: {stats.pending_bonus_days} дн.\n"
            f"🏆 До цели: {stats.milestone_progress}/{stats.milestone_target}"
        )

    def format_link_message(self, stats: ReferralCustomerStats) -> str:
        return (
            "🔗 Ваша реферальная ссылка:\n\n"
            f"{stats.referral_link}\n\n"
            "Отправьте её другу — бонус начислится после его оплаты."
        )

    def format_stats_message(self, stats: ReferralCustomerStats) -> str:
        return (
            "📊 Реферальная статистика\n\n"
            f"👥 Приглашено: {stats.invited_count}\n"
            f"💳 Оплатили: {stats.paid_referrals_count}\n"
            f"✅ Начислено дней: {stats.earned_bonus_days}\n"
            f"⏳ Ожидает начисления: {stats.pending_bonus_days} дн.\n"
            f"🏆 Прогресс к цели: {stats.milestone_progress}/{stats.milestone_target}"
        )

    async def list_customer_rewards(self, user_id: int) -> list[ReferralRewardInfo]:
        rewards = await self._uow.referrals.list_rewards_for_user(user_id)
        result: list[ReferralRewardInfo] = []
        for reward in rewards:
            referred_name = None
            if reward.referred_user_id is not None:
                referred = await self._uow.users.get_by_id(reward.referred_user_id)
                if referred is not None:
                    referred_name = self._user_display(referred)
            result.append(
                ReferralRewardInfo(
                    id=reward.id,
                    reward_type=reward.reward_type,
                    reward_days=reward.reward_days,
                    status=reward.status,
                    referred_name=referred_name,
                    created_at=reward.created_at,
                    applied_at=reward.applied_at,
                )
            )
        return result

    def format_customer_bonuses(self, rewards: list[ReferralRewardInfo]) -> str:
        if not rewards:
            return "🎁 Мои бонусы\n\nПока нет бонусов."
        type_labels = {
            ReferralRewardType.PER_REFERRAL.value: "за друга",
            ReferralRewardType.MILESTONE.value: "за цель",
            ReferralRewardType.MANUAL.value: "вручную",
        }
        status_labels = {
            ReferralRewardStatus.PENDING.value: "⏳ ожидает",
            ReferralRewardStatus.APPLIED.value: "✅ начислен",
            ReferralRewardStatus.CANCELED.value: "❌ отменён",
        }
        lines = ["🎁 Мои бонусы", ""]
        for item in rewards[:20]:
            label = type_labels.get(item.reward_type, item.reward_type)
            status = status_labels.get(item.status, item.status)
            who = f" ({item.referred_name})" if item.referred_name else ""
            lines.append(f"• +{item.reward_days} дн. {label}{who} — {status}")
        return "\n".join(lines)

    async def process_paid_payment(self, request: PaymentRequest) -> ReferralProcessOutcome:
        notifications: list[ReferralNotification] = []
        if request.request_type != PaymentRequestType.PURCHASE.value:
            return ReferralProcessOutcome(notifications=notifications)

        buyer = request.user
        if buyer is None or buyer.referred_by_user_id is None:
            return ReferralProcessOutcome(notifications=notifications)

        cfg = await self._uow.referrals.get_settings()
        if not cfg.is_enabled:
            return ReferralProcessOutcome(notifications=notifications)

        referrer = await self._uow.users.get_by_id(buyer.referred_by_user_id)
        if referrer is None or referrer.id == buyer.id:
            return ReferralProcessOutcome(notifications=notifications)

        amount = request.final_amount if request.final_amount is not None else request.amount
        if amount < cfg.min_purchase_amount:
            return ReferralProcessOutcome(notifications=notifications)
        if amount == Decimal("0") and not cfg.allow_zero_amount_rewards:
            return ReferralProcessOutcome(notifications=notifications)

        if cfg.count_only_first_paid_purchase:
            approved_count = await self._uow.referrals.count_approved_payments(buyer.id)
            if approved_count > 1:
                return ReferralProcessOutcome(notifications=notifications)

        if await self._uow.referrals.get_per_referral_reward(buyer.id) is not None:
            return ReferralProcessOutcome(notifications=notifications)

        event = await self._uow.referrals.get_event_by_referred(buyer.id)
        if event is None:
            event = await self._uow.referrals.create_event(
                referrer_user_id=referrer.id,
                referred_user_id=buyer.id,
                source="payment",
            )
        await self._uow.referrals.mark_event_paid(event, payment_request_id=request.id)

        per_reward = await self._uow.referrals.create_reward(
            referrer_user_id=referrer.id,
            referred_user_id=buyer.id,
            payment_request_id=request.id,
            reward_type=ReferralRewardType.PER_REFERRAL.value,
            reward_days=cfg.reward_days_per_paid_referral,
        )
        await self._admin_log.log(
            admin_telegram_id=0,
            action=AdminActionType.REFERRAL_PAID,
            details={
                "referrer_user_id": referrer.id,
                "referred_user_id": buyer.id,
                "payment_request_id": request.id,
                "reward_days": cfg.reward_days_per_paid_referral,
            },
        )

        paid_count = await self._uow.referrals.count_paid_referrals(referrer.id)
        if (
            paid_count >= cfg.milestone_paid_referrals
            and await self._uow.referrals.get_milestone_reward(referrer.id) is None
        ):
            await self._uow.referrals.create_reward(
                referrer_user_id=referrer.id,
                referred_user_id=None,
                payment_request_id=request.id,
                reward_type=ReferralRewardType.MILESTONE.value,
                reward_days=cfg.milestone_reward_days,
            )

        if cfg.apply_reward_automatically:
            apply_outcome = await self._apply_pending_rewards(referrer, cfg)
            notifications.extend(apply_outcome.notifications)
            if apply_outcome.applied_count == 0 and apply_outcome.pending_count > 0:
                notifications.append(
                    ReferralNotification(
                        telegram_id=referrer.telegram_id,
                        message=(
                            f"🎁 Ваш друг оплатил VPN. "
                            f"Вам начислено +{cfg.reward_days_per_paid_referral} дней! "
                            "Активируйте VPN, чтобы применить бонус."
                        ),
                    )
                )
        else:
            await self._admin_log.log(
                admin_telegram_id=0,
                action=AdminActionType.REFERRAL_REWARD_PENDING,
                details={"referrer_user_id": referrer.id, "reward_id": per_reward.id},
            )
            notifications.append(
                ReferralNotification(
                    telegram_id=referrer.telegram_id,
                    message=(
                        f"🎁 Ваш друг оплатил VPN. "
                        f"Вам начислено +{cfg.reward_days_per_paid_referral} дней! "
                        "Активируйте VPN, чтобы применить бонус."
                    ),
                )
            )

        await self._uow.referrals.mark_event_rewarded(event)
        return ReferralProcessOutcome(notifications=notifications)

    async def apply_pending_for_user(self, user_id: int) -> ReferralApplyOutcome:
        user = await self._uow.users.get_by_id(user_id)
        if user is None:
            raise ReferralError("Пользователь не найден.")
        cfg = await self._uow.referrals.get_settings()
        outcome = await self._apply_pending_rewards(user, cfg)
        if outcome.applied_count == 0 and outcome.pending_count > 0:
            message = "⏳ Бонусы ожидают. Нужен активный VPN для начисления."
        elif outcome.applied_count > 0:
            message = f"✅ Начислено бонусов: {outcome.applied_count}."
        else:
            message = "Нет бонусов для начисления."
        return ReferralApplyOutcome(
            applied_count=outcome.applied_count,
            pending_count=outcome.pending_count,
            message=message,
            notifications=outcome.notifications,
        )

    async def apply_reward_manual(self, reward_id: int, *, admin_telegram_id: int) -> str:
        reward = await self._uow.referrals.get_reward_by_id(reward_id)
        if reward is None:
            raise ReferralError("Награда не найдена.")
        if reward.status != ReferralRewardStatus.PENDING.value:
            raise ReferralError("Награда уже обработана.")
        referrer = await self._uow.users.get_by_id(reward.referrer_user_id)
        if referrer is None:
            raise ReferralError("Реферер не найден.")
        account = await self._pick_active_account(referrer.id)
        if account is None:
            raise ReferralError("У реферера нет активного VPN.")
        await self._extend_account(referrer, account, reward, admin_telegram_id=admin_telegram_id)
        return f"✅ Награда #{reward.id} применена (+{reward.reward_days} дн.)."

    def format_admin_settings(self, info: ReferralSettingsInfo) -> str:
        enabled = "включена" if info.is_enabled else "выключена"
        first_only = BOOL_YES if info.count_only_first_paid_purchase else BOOL_NO
        zero = BOOL_YES if info.allow_zero_amount_rewards else BOOL_NO
        auto = BOOL_YES if info.apply_reward_automatically else BOOL_NO
        return (
            "⚙️ Настройки рефералов\n\n"
            f"✅ Реферальная программа: {enabled}\n"
            f"🎁 За 1 оплаченного друга: +{info.reward_days_per_paid_referral} дней\n"
            f"🏆 Цель: {info.milestone_paid_referrals} оплаченных друзей\n"
            f"🎉 Бонус за цель: +{info.milestone_reward_days} дней\n"
            f"💰 Минимальная покупка для зачёта: {info.min_purchase_amount:.0f} ₽\n"
            f"🔁 Считать только первую покупку друга: {first_only}\n"
            f"🆓 Засчитывать бесплатные/0 ₽ покупки: {zero}\n"
            f"⚡ Начислять бонус автоматически: {auto}"
        )

    def format_admin_stats(self) -> str:
        return "📊 Статистика рефералов"

    async def get_admin_stats_text(self) -> str:
        stats = await self._uow.referrals.get_admin_stats()
        return (
            "📊 Статистика рефералов\n\n"
            f"Регистраций по ссылке: {stats['registrations']}\n"
            f"Оплативших друзей: {stats['paid']}\n"
            f"Наград применено: {stats['applied']}\n"
            f"Наград в ожидании: {stats['pending']}"
        )

    async def format_admin_top(self) -> str:
        rows = await self._uow.referrals.top_referrers(limit=10)
        if not rows:
            return "👥 Топ рефералов\n\nПока нет данных."
        lines = ["👥 Топ рефералов", ""]
        for idx, (_uid, paid_count, user) in enumerate(rows, start=1):
            name = self._user_display(user) if user else "—"
            lines.append(f"{idx}. {name} — {paid_count} оплат")
        return "\n".join(lines)

    async def format_admin_history(self) -> str:
        events = await self._uow.referrals.list_recent_events(limit=15)
        rewards = await self._uow.referrals.list_recent_rewards(limit=15)
        lines = ["📋 История рефералов", "", "События:", ""]
        if not events:
            lines.append("— нет событий —")
        else:
            for event in events:
                ref_name = self._user_display(event.referrer) if event.referrer else "—"
                referred_name = self._user_display(event.referred) if event.referred else "—"
                created = event.created_at.strftime("%d.%m.%Y %H:%M")
                lines.append(f"• {ref_name} → {referred_name} · {event.status} · {created}")
        lines.extend(["", "Награды:", ""])
        if not rewards:
            lines.append("— нет наград —")
        else:
            for reward in rewards:
                ref_name = self._user_display(reward.referrer) if reward.referrer else "—"
                created = reward.created_at.strftime("%d.%m.%Y %H:%M")
                lines.append(
                    f"• {ref_name} · +{reward.reward_days} дн. · "
                    f"{reward.reward_type} · {reward.status} · {created}"
                )
        return "\n".join(lines)

    async def format_admin_rewards(self) -> str:
        rewards = await self._uow.referrals.list_recent_rewards(limit=20)
        if not rewards:
            return "🎁 Награды\n\nПока нет наград."
        lines = ["🎁 Награды", ""]
        for reward in rewards:
            ref_name = self._user_display(reward.referrer) if reward.referrer else "—"
            created = reward.created_at.strftime("%d.%m.%Y %H:%M")
            lines.append(
                f"#{reward.id} · {ref_name} · +{reward.reward_days} дн. · "
                f"{reward.status} · {created}"
            )
        return "\n".join(lines)

    async def toggle_enabled(self, *, admin_telegram_id: int) -> ReferralSettingsInfo:
        row = await self._uow.referrals.get_settings()
        row.is_enabled = not row.is_enabled
        await self._uow.referrals.update_settings(row)
        await self._log_settings_update(admin_telegram_id, "is_enabled", row.is_enabled)
        return self._settings_to_info(row)

    async def toggle_count_first_only(self, *, admin_telegram_id: int) -> ReferralSettingsInfo:
        row = await self._uow.referrals.get_settings()
        row.count_only_first_paid_purchase = not row.count_only_first_paid_purchase
        await self._uow.referrals.update_settings(row)
        await self._log_settings_update(admin_telegram_id, "count_only_first_paid_purchase", row.count_only_first_paid_purchase)
        return self._settings_to_info(row)

    async def toggle_allow_zero(self, *, admin_telegram_id: int) -> ReferralSettingsInfo:
        row = await self._uow.referrals.get_settings()
        row.allow_zero_amount_rewards = not row.allow_zero_amount_rewards
        await self._uow.referrals.update_settings(row)
        await self._log_settings_update(admin_telegram_id, "allow_zero_amount_rewards", row.allow_zero_amount_rewards)
        return self._settings_to_info(row)

    async def toggle_auto_apply(self, *, admin_telegram_id: int) -> ReferralSettingsInfo:
        row = await self._uow.referrals.get_settings()
        row.apply_reward_automatically = not row.apply_reward_automatically
        await self._uow.referrals.update_settings(row)
        await self._log_settings_update(admin_telegram_id, "apply_reward_automatically", row.apply_reward_automatically)
        return self._settings_to_info(row)

    async def set_reward_days_per_referral(self, value: int, *, admin_telegram_id: int) -> ReferralSettingsInfo:
        self._validate_non_negative_int(value, "Бонус за друга")
        row = await self._uow.referrals.get_settings()
        row.reward_days_per_paid_referral = value
        await self._uow.referrals.update_settings(row)
        await self._log_settings_update(admin_telegram_id, "reward_days_per_paid_referral", value)
        return self._settings_to_info(row)

    async def set_milestone_count(self, value: int, *, admin_telegram_id: int) -> ReferralSettingsInfo:
        if value < 1:
            raise ReferralError("Цель должна быть не меньше 1.")
        row = await self._uow.referrals.get_settings()
        row.milestone_paid_referrals = value
        await self._uow.referrals.update_settings(row)
        await self._log_settings_update(admin_telegram_id, "milestone_paid_referrals", value)
        return self._settings_to_info(row)

    async def set_milestone_reward_days(self, value: int, *, admin_telegram_id: int) -> ReferralSettingsInfo:
        self._validate_non_negative_int(value, "Бонус за цель")
        row = await self._uow.referrals.get_settings()
        row.milestone_reward_days = value
        await self._uow.referrals.update_settings(row)
        await self._log_settings_update(admin_telegram_id, "milestone_reward_days", value)
        return self._settings_to_info(row)

    async def set_min_purchase_amount(self, value: Decimal, *, admin_telegram_id: int) -> ReferralSettingsInfo:
        if value < 0:
            raise ReferralError("Минимальная сумма не может быть отрицательной.")
        row = await self._uow.referrals.get_settings()
        row.min_purchase_amount = value
        await self._uow.referrals.update_settings(row)
        await self._log_settings_update(admin_telegram_id, "min_purchase_amount", str(value))
        return self._settings_to_info(row)

    @staticmethod
    def parse_int(text: str) -> int:
        raw = (text or "").strip()
        try:
            return int(raw)
        except ValueError as exc:
            raise ReferralError("Введите целое число.") from exc

    @staticmethod
    def parse_decimal(text: str) -> Decimal:
        raw = (text or "").strip().replace(",", ".")
        try:
            return Decimal(raw)
        except InvalidOperation as exc:
            raise ReferralError("Введите корректное число.") from exc

    async def _apply_pending_rewards(
        self,
        referrer: User,
        cfg: ReferralSettings,
    ) -> ReferralApplyOutcome:
        notifications: list[ReferralNotification] = []
        pending = await self._uow.referrals.list_pending_rewards(referrer.id)
        if not pending:
            return ReferralApplyOutcome(applied_count=0, pending_count=0, message="", notifications=notifications)

        account = await self._pick_active_account(referrer.id)
        if account is None:
            return ReferralApplyOutcome(
                applied_count=0,
                pending_count=len(pending),
                message="",
                notifications=notifications,
            )

        applied = 0
        admin_id = self._resolve_admin_id()
        for reward in pending:
            await self._extend_account(referrer, account, reward, admin_telegram_id=admin_id)
            applied += 1
            notifications.append(
                ReferralNotification(
                    telegram_id=referrer.telegram_id,
                    message=self._reward_notification(reward),
                )
            )
            if reward.reward_type == ReferralRewardType.MILESTONE.value:
                notifications[-1] = ReferralNotification(
                    telegram_id=referrer.telegram_id,
                    message=f"🎉 Цель достигнута! Вам начислено +{reward.reward_days} дней!",
                )

        remaining = await self._uow.referrals.list_pending_rewards(referrer.id)
        return ReferralApplyOutcome(
            applied_count=applied,
            pending_count=len(remaining),
            message="",
            notifications=notifications,
        )

    async def _extend_account(
        self,
        referrer: User,
        account: VpnAccount,
        reward: ReferralReward,
        *,
        admin_telegram_id: int,
    ) -> None:
        if self._admin_customer is None:
            raise ReferralError("Сервис продления недоступен.")
        outcome = await self._admin_customer.manual_extend(
            account.id,
            days=reward.reward_days,
            admin_telegram_id=admin_telegram_id,
        )
        if not outcome.success:
            raise ReferralError(outcome.admin_message)
        await self._uow.referrals.mark_reward_applied(reward, vpn_account_id=account.id)
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.REFERRAL_REWARD_APPLIED,
            details={
                "reward_id": reward.id,
                "referrer_user_id": referrer.id,
                "reward_days": reward.reward_days,
                "vpn_account_id": account.id,
            },
        )

    async def _pick_active_account(self, user_id: int) -> VpnAccount | None:
        active = await self._uow.vpn_accounts.list_active_for_user(user_id)
        if not active:
            return None
        for account in active:
            if account.is_primary:
                return account
        return max(active, key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC))

    def _reward_notification(self, reward: ReferralReward) -> str:
        if reward.reward_type == ReferralRewardType.MILESTONE.value:
            return f"🎉 Цель достигнута! Вам начислено +{reward.reward_days} дней!"
        return f"🎁 Ваш друг оплатил VPN. Вам начислено +{reward.reward_days} дней!"

    async def _log_settings_update(self, admin_telegram_id: int, field: str, value: object) -> None:
        await self._admin_log.log(
            admin_telegram_id=admin_telegram_id,
            action=AdminActionType.REFERRAL_SETTINGS_UPDATED,
            details={"field": field, "value": value},
        )

    def _resolve_admin_id(self) -> int:
        if self._settings.admin_telegram_ids:
            return self._settings.admin_telegram_ids[0]
        return 0

    @staticmethod
    def _settings_to_info(row: ReferralSettings) -> ReferralSettingsInfo:
        return ReferralSettingsInfo(
            is_enabled=row.is_enabled,
            reward_days_per_paid_referral=row.reward_days_per_paid_referral,
            milestone_paid_referrals=row.milestone_paid_referrals,
            milestone_reward_days=row.milestone_reward_days,
            min_purchase_amount=row.min_purchase_amount,
            count_only_first_paid_purchase=row.count_only_first_paid_purchase,
            allow_zero_amount_rewards=row.allow_zero_amount_rewards,
            apply_reward_automatically=row.apply_reward_automatically,
        )

    @staticmethod
    def _validate_non_negative_int(value: int, label: str) -> None:
        if value < 0:
            raise ReferralError(f"{label} не может быть отрицательным.")

    @staticmethod
    def _user_display(user: User | None) -> str:
        if user is None:
            return "—"
        parts = [user.first_name, user.last_name]
        name = " ".join(part for part in parts if part) or "Пользователь"
        if user.username:
            return f"{name} (@{user.username})"
        return name
