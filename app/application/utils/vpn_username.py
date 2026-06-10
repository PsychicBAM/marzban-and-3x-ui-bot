from __future__ import annotations

import re

from app.application.exceptions import VpnPanelValidationError

_SAFE_CHARS_RE = re.compile(r"[^a-z0-9_-]")
_MAX_LENGTH = 64
_MAX_LABEL_LENGTH = 32


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


def normalize_subscription_label(raw: str) -> str:
    """Normalize user-facing subscription label into a safe suffix."""
    value = raw.strip().lower().replace(" ", "_")
    value = _SAFE_CHARS_RE.sub("", value)
    if not value:
        raise VpnPanelValidationError(
            "Название подписки может содержать только латинские буквы, цифры, _ и -.",
        )
    return value[:_MAX_LABEL_LENGTH]


def build_vpn_account_name_with_label(base_name: str, label: str) -> str:
    base = normalize_vpn_account_name(base_name)
    suffix = normalize_subscription_label(label)
    combined = f"{base}_{suffix}"
    return normalize_vpn_account_name(combined)


def build_vpn_account_name_with_suffix(base_name: str, label: str, suffix_number: int) -> str:
    base = normalize_vpn_account_name(base_name)
    norm_label = normalize_subscription_label(label)
    combined = f"{base}_{norm_label}_{suffix_number}"
    return normalize_vpn_account_name(combined)
