from __future__ import annotations

from html import escape

from aiogram.enums import ParseMode

CUSTOMER_PARSE_MODE = ParseMode.HTML


def h(value: object) -> str:
    """Escape dynamic text for Telegram HTML messages."""
    if value is None:
        return ""
    return escape(str(value), quote=False)
