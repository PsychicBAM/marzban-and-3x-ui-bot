from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminManualKeyStates(StatesGroup):
    waiting_user_search = State()
    waiting_account_name = State()
    waiting_custom_duration = State()
    waiting_custom_traffic = State()
    waiting_custom_ip = State()
    waiting_custom_comment = State()
