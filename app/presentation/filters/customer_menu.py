from __future__ import annotations

from aiogram import F

from app.presentation.i18n import all_menu_texts

# Pre-submenu reply-keyboard labels kept for cached Telegram clients.
LEGACY_MENU_LABELS: dict[str, tuple[str, ...]] = {
    "menu.guide": ("ℹ️ Инструкция", "ℹ️ Instructions"),
    "menu.history": ("🧾 История", "🧾 History"),
    "menu.promo_news": ("🔔 Promotions & news",),
}


def menu_text_filter(key: str):
    legacy = LEGACY_MENU_LABELS.get(key, ())
    return F.text.in_([*all_menu_texts(key), *legacy])


# Legacy reply-keyboard labels (pre-guide rename)
LEGACY_GUIDE_LABELS = ("ℹ️ Инструкция", "ℹ️ Instructions")


def guide_menu_filter():
    return F.text.in_([*all_menu_texts("menu.guide"), *LEGACY_GUIDE_LABELS])
