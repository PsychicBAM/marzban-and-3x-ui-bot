from aiogram.fsm.state import State, StatesGroup


class CustomerSupportStates(StatesGroup):
    waiting_message = State()
    waiting_reply = State()


class AdminSupportStates(StatesGroup):
    waiting_reply = State()
    waiting_search_id = State()


class AdminDailyReportStates(StatesGroup):
    waiting_time = State()
