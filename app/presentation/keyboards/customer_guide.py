from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.presentation.i18n import t

GUIDE_DEVICES = "guide:devices"
GUIDE_IPHONE = "guide:iphone"
GUIDE_ANDROID = "guide:android"
GUIDE_MACOS = "guide:macos"
GUIDE_WINDOWS = "guide:windows"
GUIDE_LINUX = "guide:linux"
GUIDE_TV = "guide:tv"
GUIDE_BACK_MENU = "guide:back_menu"
GUIDE_BACK_DEVICES = "guide:back_devices"

_DEVICE_STEP_KEYS = {
    GUIDE_IPHONE: "guide.steps.iphone",
    GUIDE_ANDROID: "guide.steps.android",
    GUIDE_MACOS: "guide.steps.macos",
    GUIDE_WINDOWS: "guide.steps.windows",
    GUIDE_LINUX: "guide.steps.linux",
    GUIDE_TV: "guide.steps.tv",
}


def guide_devices_keyboard(lang: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "guide.btn.iphone"), callback_data=GUIDE_IPHONE)],
            [InlineKeyboardButton(text=t(lang, "guide.btn.android"), callback_data=GUIDE_ANDROID)],
            [InlineKeyboardButton(text=t(lang, "guide.btn.mac"), callback_data=GUIDE_MACOS)],
            [InlineKeyboardButton(text=t(lang, "guide.btn.windows"), callback_data=GUIDE_WINDOWS)],
            [InlineKeyboardButton(text=t(lang, "guide.btn.tv"), callback_data=GUIDE_TV)],
            [InlineKeyboardButton(text=t(lang, "guide.btn.back_menu"), callback_data=GUIDE_BACK_MENU)],
        ],
    )


def guide_steps_keyboard(lang: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "guide.btn.back_devices"), callback_data=GUIDE_BACK_DEVICES)],
        ],
    )


def guide_step_key(callback_data: str) -> str | None:
    return _DEVICE_STEP_KEYS.get(callback_data)
