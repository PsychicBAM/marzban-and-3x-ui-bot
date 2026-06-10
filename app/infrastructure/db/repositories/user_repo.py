from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> User | None:
        stmt = select(User).where(User.referral_code == code.upper())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_referral_code(self, user: User, code: str) -> User:
        user.referral_code = code.upper()
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def set_referred_by(self, user: User, referrer_user_id: int) -> User:
        user.referred_by_user_id = referrer_user_id
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def create(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        is_admin: bool = False,
        referred_by_user_id: int | None = None,
        referral_code: str | None = None,
        language_code: str = "ru",
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin,
            referred_by_user_id=referred_by_user_id,
            referral_code=referral_code,
            language_code=language_code,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def set_language(self, user: User, language_code: str) -> User:
        user.language_code = language_code
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def set_promo_enabled(self, user: User, *, enabled: bool) -> User:
        user.promo_enabled = enabled
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update_profile(
        self,
        user: User,
        *,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        is_admin: bool,
    ) -> User:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.is_admin = is_admin
        await self._session.flush()
        await self._session.refresh(user)
        return user
