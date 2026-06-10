from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminPromoCreateStates(StatesGroup):
    waiting_code = State()
    waiting_discount_type = State()
    waiting_value = State()
    waiting_dates = State()
    waiting_max_uses = State()
    waiting_max_per_user = State()
    waiting_scope = State()
    waiting_plan = State()
    confirm = State()


class AdminPromoSearchStates(StatesGroup):
    waiting_query = State()
