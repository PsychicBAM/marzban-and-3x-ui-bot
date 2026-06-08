from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class InstructionSettingsStates(StatesGroup):
    waiting_text = State()
    waiting_url = State()
