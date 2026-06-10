from __future__ import annotations

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def encode_referral_code(user_id: int) -> str:
    """Stable base36 referral code from internal user id."""
    if user_id <= 0:
        raise ValueError("user_id must be positive")
    chars: list[str] = []
    n = user_id
    while n:
        n, remainder = divmod(n, 36)
        chars.append(_ALPHABET[remainder])
    return "".join(reversed(chars))


def parse_start_referral_payload(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if not payload.lower().startswith("ref_"):
        return None
    code = payload[4:].strip().upper()
    return code or None
