from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class PurchaseReceiptStates(StatesGroup):
    waiting_receipt = State()


class PurchaseSubscriptionStates(StatesGroup):
    waiting_label = State()
