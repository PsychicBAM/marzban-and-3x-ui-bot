from __future__ import annotations

from aiogram import F

from app.presentation.i18n import all_menu_texts


def menu_text_filter(key: str):
    return F.text.in_(all_menu_texts(key))
