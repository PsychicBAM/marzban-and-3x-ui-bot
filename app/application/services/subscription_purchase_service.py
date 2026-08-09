from __future__ import annotations

import logging

from app.application.exceptions import PaymentRequestNotFoundError, VpnPanelValidationError
from app.application.utils.vpn_username import (
    build_primary_vpn_account_name,
    build_vpn_account_name_with_label,
    build_vpn_account_name_with_suffix,
    clean_vpn_base_name,
    normalize_subscription_label,
    normalize_vpn_account_name,
    resolve_primary_vpn_account_name,
)
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.vpn_account import VpnAccount
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

LABEL_INVALID_MESSAGE = (
    "Название может содержать только латинские буквы, цифры, пробелы, _ и -.\n"
    "Примеры: grandma, phone, work"
)


class SubscriptionPurchaseService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def user_has_active_vpn(self, telegram_id: int) -> bool:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            return False
        return await self._uow.vpn_accounts.has_active_vpn(user.id)

    async def list_active_accounts(self, telegram_id: int) -> list[VpnAccount]:
        user = await self.get_user(telegram_id)
        return await self._uow.vpn_accounts.list_active_for_user(user.id)

    async def list_manageable_accounts(self, telegram_id: int) -> list[VpnAccount]:
        user = await self.get_user(telegram_id)
        return await self._uow.vpn_accounts.list_by_user_id(user.id, include_deleted=False)

    def resolve_primary_account_name(self, user: User) -> str | None:
        """Return existing/generated primary VPN name, or None if customer must enter a base name."""
        return resolve_primary_vpn_account_name(
            vpn_account_name=user.vpn_account_name,
            username=user.username,
            telegram_id=user.telegram_id,
        )

    async def resolve_base_name(self, user: User) -> str:
        primary = self.resolve_primary_account_name(user)
        if primary is not None:
            return primary
        raise VpnPanelValidationError(
            "Не удалось определить имя VPN. Введите имя латиницей.",
        )

    def parse_subscription_label(self, raw: str) -> str:
        try:
            return normalize_subscription_label(raw)
        except VpnPanelValidationError as exc:
            raise VpnPanelValidationError(LABEL_INVALID_MESSAGE) from exc

    def parse_vpn_base_name(self, raw: str) -> str:
        return clean_vpn_base_name(raw)

    async def assign_primary_vpn_account_name(self, user: User, raw_base_name: str) -> str:
        """Validate entered base name, build {base}_{telegram_id}, persist on user if empty."""
        account_name = build_primary_vpn_account_name(raw_base_name, user.telegram_id)
        if user.vpn_account_name:
            # Never rename an already assigned primary account name.
            return normalize_vpn_account_name(user.vpn_account_name)
        await self._uow.users.set_vpn_account_name(user, account_name)
        logger.info(
            "vpn_primary_account_name_assigned",
            extra={"user_id": user.id, "vpn_account_name": account_name},
        )
        return account_name

    async def ensure_primary_vpn_account_name(self, user: User) -> str | None:
        """
        Ensure the user has a resolvable primary VPN name.

        Returns the name when available (including newly built from Telegram username).
        Returns None when the customer must enter a base name manually.
        """
        existing = self.resolve_primary_account_name(user)
        if existing is None:
            return None
        if not user.vpn_account_name:
            # Persist username-derived primary name so later provisioning does not depend on @username.
            await self._uow.users.set_vpn_account_name(user, existing)
        return existing

    async def generate_unique_vpn_account_name(
        self,
        user: User,
        *,
        label: str,
    ) -> tuple[str, str]:
        display_name = label.strip()
        norm_label = self.parse_subscription_label(label)
        base_name = await self.resolve_base_name(user)

        candidate = build_vpn_account_name_with_label(base_name, norm_label)
        if not await self._uow.vpn_accounts.exists_by_name(candidate):
            logger.info(
                "vpn_account_name_generated",
                extra={"user_id": user.id, "vpn_account_name": candidate},
            )
            return candidate, display_name

        for suffix in range(2, 100):
            candidate = build_vpn_account_name_with_suffix(base_name, norm_label, suffix)
            if not await self._uow.vpn_accounts.exists_by_name(candidate):
                logger.info(
                    "vpn_account_name_generated",
                    extra={"user_id": user.id, "vpn_account_name": candidate, "suffix": suffix},
                )
                return candidate, display_name

        raise VpnPanelValidationError(
            "Не удалось подобрать уникальное имя подписки. Попробуйте другое название.",
        )

    async def get_user(self, telegram_id: int) -> User:
        user = await self._uow.users.get_by_telegram_id(telegram_id)
        if user is None:
            raise PaymentRequestNotFoundError("Пользователь не найден. Отправьте /start.")
        return user
