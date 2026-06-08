from __future__ import annotations

import re

from app.application.exceptions import VpnPanelValidationError

_SAFE_CHARS_RE = re.compile(r"[^a-z0-9_-]")
_MAX_LENGTH = 64


def normalize_vpn_account_name(raw: str) -> str:
    """Normalize Telegram username or manual name for VPN panels."""
    value = raw.strip().lstrip("@").lower()
    value = _SAFE_CHARS_RE.sub("", value)
    if not value:
        raise VpnPanelValidationError(
            "Имя VPN-аккаунта может содержать только латинские буквы, цифры, _ и -.",
        )
    return value[:_MAX_LENGTH]


def normalize_from_telegram_username(username: str | None) -> str | None:
    if not username:
        return None
    try:
        return normalize_vpn_account_name(username)
    except VpnPanelValidationError:
        return None
