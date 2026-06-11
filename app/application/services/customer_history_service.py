from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.application.dto.customer_history import HistoryEntry
from app.application.utils.admin_client_format import total_pages
from app.domain.enums import (
    AdminActionType,
    PaymentRequestStatus,
    PaymentRequestType,
    ReferralRewardStatus,
)
from app.infrastructure.db.uow import UnitOfWork
from app.presentation.i18n import t

HISTORY_PAGE_SIZE = 6

_ADMIN_ACTION_I18N = {
    AdminActionType.CLIENT_DISABLED.value: "history.vpn_disabled",
    AdminActionType.CLIENT_ENABLED.value: "history.vpn_enabled",
    AdminActionType.CLIENT_DELETED.value: "history.vpn_deleted",
    AdminActionType.VPN_ACCOUNT_MANUALLY_EXTENDED.value: "history.admin_renewal",
    AdminActionType.CLIENT_RENEWED.value: "history.vpn_renewed",
}

_CUSTOMER_ADMIN_ACTIONS = (
    AdminActionType.CLIENT_DISABLED.value,
    AdminActionType.CLIENT_ENABLED.value,
    AdminActionType.CLIENT_DELETED.value,
    AdminActionType.VPN_ACCOUNT_MANUALLY_EXTENDED.value,
    AdminActionType.CLIENT_RENEWED.value,
)

_APPROVED_STATUSES = {
    PaymentRequestStatus.APPROVED.value,
    PaymentRequestStatus.PROVISIONING_FAILED.value,
    PaymentRequestStatus.PROVISIONING_PARTIAL.value,
}


class CustomerHistoryService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def list_entries(self, user_id: int, *, lang: str) -> list[HistoryEntry]:
        entries: list[HistoryEntry] = []
        seen_promo_payment_ids: set[int] = set()

        payments = await self._uow.payment_requests.list_history_by_user_id(user_id)
        for payment in payments:
            if payment.status not in _APPROVED_STATUSES:
                continue
            event_at = payment.approved_at or payment.created_at
            if event_at.tzinfo is None:
                event_at = event_at.replace(tzinfo=UTC)

            is_free = (
                payment.request_type == PaymentRequestType.PURCHASE.value
                and payment.amount == 0
            )
            is_renewal = payment.request_type == PaymentRequestType.RENEWAL.value
            days = payment.plan.duration_days if payment.plan else 0
            amount = payment.final_amount if payment.final_amount is not None else payment.amount
            date_label = event_at.strftime("%d.%m.%Y")

            if is_free:
                entries.append(
                    HistoryEntry(
                        created_at=event_at,
                        lines=(
                            t(lang, "history.free_plan_title"),
                            t(lang, "history.free_plan_days", days=days),
                            t(lang, "history.date", date=date_label),
                        ),
                    )
                )
            elif is_renewal:
                entries.append(
                    HistoryEntry(
                        created_at=event_at,
                        lines=(
                            t(lang, "history.renewal_title"),
                            t(lang, "history.purchase_days_amount", days=days, amount=self._money(amount, lang)),
                            t(lang, "history.date", date=date_label),
                        ),
                    )
                )
            else:
                entries.append(
                    HistoryEntry(
                        created_at=event_at,
                        lines=(
                            t(lang, "history.purchase_title"),
                            t(lang, "history.purchase_days_amount", days=days, amount=self._money(amount, lang)),
                            t(lang, "history.date", date=date_label),
                        ),
                    )
                )

            if payment.promo_code_id and payment.discount_amount > 0:
                code = payment.promo_code.code if payment.promo_code else "—"
                pay_amount = payment.final_amount if payment.final_amount is not None else payment.amount
                entries.append(
                    HistoryEntry(
                        created_at=event_at,
                        lines=(
                            t(lang, "history.promo_title", code=code),
                            t(lang, "history.promo_discount", amount=self._money(payment.discount_amount, lang)),
                            t(lang, "history.promo_final", amount=self._money(pay_amount, lang)),
                        ),
                    )
                )
                seen_promo_payment_ids.add(payment.id)

        redemptions = await self._uow.promo_codes.list_redemptions_by_user_id(user_id)
        for redemption in redemptions:
            if redemption.payment_request_id in seen_promo_payment_ids:
                continue
            event_at = redemption.created_at
            if event_at.tzinfo is None:
                event_at = event_at.replace(tzinfo=UTC)
            code = redemption.promo_code.code if redemption.promo_code else "—"
            entries.append(
                HistoryEntry(
                    created_at=event_at,
                    lines=(
                        t(lang, "history.promo_title", code=code),
                        t(lang, "history.promo_discount", amount=self._money(redemption.discount_amount, lang)),
                        t(lang, "history.promo_final", amount=self._money(redemption.final_amount, lang)),
                    ),
                )
            )

        rewards = await self._uow.referrals.list_rewards_for_user(user_id, limit=100)
        for reward in rewards:
            if reward.status != ReferralRewardStatus.APPLIED.value:
                continue
            event_at = reward.applied_at or reward.created_at
            if event_at is None:
                continue
            if event_at.tzinfo is None:
                event_at = event_at.replace(tzinfo=UTC)
            entries.append(
                HistoryEntry(
                    created_at=event_at,
                    lines=(
                        t(lang, "history.referral_title"),
                        t(lang, "history.referral_days", days=reward.reward_days),
                        t(lang, "history.date", date=event_at.strftime("%d.%m.%Y")),
                    ),
                )
            )

        admin_logs = await self._uow.admin_logs.list_for_customer_user(user_id, _CUSTOMER_ADMIN_ACTIONS)
        for log in admin_logs:
            event_at = log.created_at
            if event_at.tzinfo is None:
                event_at = event_at.replace(tzinfo=UTC)
            key = _ADMIN_ACTION_I18N.get(log.action_type)
            if key is None:
                continue
            entries.append(
                HistoryEntry(
                    created_at=event_at,
                    lines=(
                        t(lang, key),
                        t(lang, "history.date", date=event_at.strftime("%d.%m.%Y")),
                    ),
                )
            )

        stored = await self._uow.customer_events.list_by_user_id(user_id)
        for event in stored:
            event_at = event.created_at
            if event_at.tzinfo is None:
                event_at = event_at.replace(tzinfo=UTC)
            lines = [event.title]
            if event.description:
                lines.append(event.description)
            lines.append(t(lang, "history.date", date=event_at.strftime("%d.%m.%Y")))
            entries.append(HistoryEntry(created_at=event_at, lines=tuple(lines)))

        entries.sort(key=lambda item: item.created_at, reverse=True)
        return entries

    async def get_page(self, user_id: int, *, lang: str, page: int) -> tuple[str, int, int]:
        entries = await self.list_entries(user_id, lang=lang)
        total = len(entries)
        pages = total_pages(total, HISTORY_PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        if total == 0:
            return t(lang, "history.empty"), 0, 1

        start = page * HISTORY_PAGE_SIZE
        chunk = entries[start : start + HISTORY_PAGE_SIZE]
        lines = [t(lang, "history.title"), ""]
        for index, entry in enumerate(chunk, start=start + 1):
            lines.append(f"{index}. {entry.lines[0]}")
            for extra in entry.lines[1:]:
                lines.append(f"   {extra}")
            lines.append("")
        lines.append(t(lang, "history.page", current=page + 1, total=pages))
        return "\n".join(lines).strip(), page, pages

    @staticmethod
    def _money(amount: Decimal, lang: str) -> str:
        value = int(amount) if amount == amount.to_integral_value() else float(amount)
        suffix = "₽" if lang == "ru" else "RUB"
        return f"{value} {suffix}"
