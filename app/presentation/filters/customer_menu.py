from __future__ import annotations

from aiogram import F

from app.presentation.i18n import all_menu_texts


def menu_text_filter(key: str):
    return F.text.in_(all_menu_texts(key))


# Legacy reply-keyboard labels (pre-guide rename)
LEGACY_GUIDE_LABELS = ("ℹ️ Инструкция", "ℹ️ Instructions")


def guide_menu_filter():
    return F.text.in_([*all_menu_texts("menu.guide"), *LEGACY_GUIDE_LABELS])
