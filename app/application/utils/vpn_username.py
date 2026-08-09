from __future__ import annotations

import re

from app.application.exceptions import VpnPanelValidationError

_SAFE_CHARS_RE = re.compile(r"[^a-z0-9_-]")
_BASE_ALLOWED_RE = re.compile(r"^[a-z0-9_]+$")
_MAX_LENGTH = 64
_MAX_LABEL_LENGTH = 32
_MAX_BASE_LENGTH = 32

VPN_BASE_NAME_INVALID_MESSAGE = (
    "Имя VPN может содержать только латинские буквы, цифры и _.\n"
    "Примеры: abdallah, mohamed, work_phone"
)


def _has_non_latin_letters(text: str) -> bool:
    return any(ch.isalpha() and not ("a" <= ch.lower() <= "z") for ch in text)


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


def clean_vpn_base_name(raw: str, *, max_length: int = _MAX_BASE_LENGTH) -> str:
    """
    Clean a human-entered VPN base name.

    - lowercases
    - replaces spaces/dashes with underscore
    - allows only [a-z0-9_]
    - rejects empty / non-Latin text
    """
    value = (raw or "").strip().lstrip("@")
    if not value:
        raise VpnPanelValidationError(VPN_BASE_NAME_INVALID_MESSAGE)

    lowered = value.lower().replace(" ", "_").replace("-", "_")
    lowered = re.sub(r"_+", "_", lowered).strip("_")

    # Reject Cyrillic/Arabic/other scripts politely instead of silently stripping.
    if _has_non_latin_letters(value):
        raise VpnPanelValidationError(VPN_BASE_NAME_INVALID_MESSAGE)
    if not _BASE_ALLOWED_RE.fullmatch(lowered):
        raise VpnPanelValidationError(VPN_BASE_NAME_INVALID_MESSAGE)
    if not lowered:
        raise VpnPanelValidationError(VPN_BASE_NAME_INVALID_MESSAGE)

    return lowered[:max_length].rstrip("_")


def build_primary_vpn_account_name(base: str, telegram_id: int) -> str:
    """Build final primary VPN name: {clean_base}_{telegram_id}."""
    suffix = f"_{int(telegram_id)}"
    max_base = max(1, _MAX_LENGTH - len(suffix))
    cleaned = clean_vpn_base_name(base, max_length=max_base)
    if not cleaned:
        raise VpnPanelValidationError(VPN_BASE_NAME_INVALID_MESSAGE)
    return f"{cleaned}{suffix}"


def resolve_primary_vpn_account_name(
    *,
    vpn_account_name: str | None,
    username: str | None,
    telegram_id: int,
) -> str | None:
    """
    Resolve the primary VPN account name for a user.

    Existing vpn_account_name is kept as-is (no rename).
    Otherwise build from Telegram username + telegram_id.
    Returns None when a manual base name must be requested.
    """
    if vpn_account_name:
        try:
            return normalize_vpn_account_name(vpn_account_name)
        except VpnPanelValidationError:
            pass

    if username:
        try:
            return build_primary_vpn_account_name(username, telegram_id)
        except VpnPanelValidationError:
            return None
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
