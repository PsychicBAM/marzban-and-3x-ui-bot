from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class TariffCreateStates(StatesGroup):
    name = State()
    price = State()
    duration_days = State()
    traffic_limit_gb = State()
    ip_limit = State()
    issuing_mode = State()
    description = State()
    confirm = State()


class TariffEditStates(StatesGroup):
    enter_value = State()
