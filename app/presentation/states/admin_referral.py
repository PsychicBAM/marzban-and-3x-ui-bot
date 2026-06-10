from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminReferralSettingsStates(StatesGroup):
    waiting_reward_days = State()
    waiting_milestone_count = State()
    waiting_milestone_reward_days = State()
    waiting_min_amount = State()
