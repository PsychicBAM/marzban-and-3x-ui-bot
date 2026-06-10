from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminBroadcastStates(StatesGroup):
    waiting_title = State()
    waiting_text = State()
    waiting_photo = State()
    waiting_audience = State()
