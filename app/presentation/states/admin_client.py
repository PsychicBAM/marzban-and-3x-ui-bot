from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminClientSearchStates(StatesGroup):
    waiting_query = State()
    viewing_results = State()


class AdminClientIpLimitStates(StatesGroup):
    waiting_value = State()


class AdminClientExtendStates(StatesGroup):
    waiting_days = State()
