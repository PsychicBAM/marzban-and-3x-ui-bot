from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

RF_HOME = "rf:home"
RF_SETTINGS = "rf:set"
RF_STATS = "rf:stat"
RF_TOP = "rf:top"
RF_HISTORY = "rf:hist"
RF_REWARDS = "rf:rew"
RF_BACK_ADMIN = "rf:adm"
RF_CANCEL = "rf:cancel"

RF_TOGGLE_ENABLED = "rf:t:en"
RF_EDIT_REWARD = "rf:e:rw"
RF_EDIT_MILESTONE = "rf:e:ms"
RF_EDIT_MILESTONE_REWARD = "rf:e:mr"
RF_EDIT_MIN_AMOUNT = "rf:e:min"
RF_TOGGLE_FIRST = "rf:t:1st"
RF_TOGGLE_ZERO = "rf:t:zero"
RF_TOGGLE_AUTO = "rf:t:auto"
RF_BACK_SETTINGS = "rf:back:set"
RF_APPLY_PREFIX = "rf:apply:"


def referral_admin_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data=RF_SETTINGS)],
            [InlineKeyboardButton(text="📊 Статистика", callback_data=RF_STATS)],
            [InlineKeyboardButton(text="👥 Топ рефералов", callback_data=RF_TOP)],
            [InlineKeyboardButton(text="📋 История", callback_data=RF_HISTORY)],
            [InlineKeyboardButton(text="🎁 Награды", callback_data=RF_REWARDS)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=RF_BACK_ADMIN)],
        ],
    )


def referral_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔘 Вкл/выкл рефералы", callback_data=RF_TOGGLE_ENABLED)],
            [InlineKeyboardButton(text="🎁 Изменить бонус за друга", callback_data=RF_EDIT_REWARD)],
            [InlineKeyboardButton(text="🏆 Изменить цель", callback_data=RF_EDIT_MILESTONE)],
            [InlineKeyboardButton(text="🎉 Изменить бонус за цель", callback_data=RF_EDIT_MILESTONE_REWARD)],
            [InlineKeyboardButton(text="💰 Изменить минимальную сумму", callback_data=RF_EDIT_MIN_AMOUNT)],
            [InlineKeyboardButton(text='🔁 Переключить "только первая покупка"', callback_data=RF_TOGGLE_FIRST)],
            [InlineKeyboardButton(text="🆓 Переключить 0 ₽ покупки", callback_data=RF_TOGGLE_ZERO)],
            [InlineKeyboardButton(text="⚡ Переключить автоначисление", callback_data=RF_TOGGLE_AUTO)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=RF_HOME)],
        ],
    )


def referral_settings_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=RF_CANCEL)]],
    )


def referral_back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=RF_HOME)]],
    )
