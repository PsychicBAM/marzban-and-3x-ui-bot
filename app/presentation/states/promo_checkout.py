from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class PromoCheckoutStates(StatesGroup):
    waiting_code = State()
