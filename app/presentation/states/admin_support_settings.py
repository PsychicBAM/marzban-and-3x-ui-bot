from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SupportSettingsStates(StatesGroup):
    waiting_username = State()
    waiting_url = State()
    waiting_text = State()
