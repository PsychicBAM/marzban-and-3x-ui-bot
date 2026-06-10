from __future__ import annotations

from typing import Any

from app.application.exceptions import VpnPanelError, VpnPanelNotFoundError


def read_marzban_status(payload: dict[str, Any]) -> str:
    return str(payload.get("status") or "").strip().lower()


def is_marzban_user_active(payload: dict[str, Any]) -> bool:
    return read_marzban_status(payload) == "active"


def read_marzban_ip_limit(payload: dict[str, Any]) -> int | None:
    if "limit_ip" not in payload:
        return None
    return int(payload.get("limit_ip") or 0)


def verify_marzban_status(payload: dict[str, Any], *, expected_active: bool) -> None:
    status = read_marzban_status(payload)
    is_active = status == "active"
    if is_active != expected_active:
        expected = "active" if expected_active else "disabled"
        raise VpnPanelError(
            f"Marzban update verification failed: expected status={expected} got {status or 'unknown'}",
            panel="marzban",
        )


def verify_marzban_ip_limit(payload: dict[str, Any], *, expected: int) -> None:
    actual = read_marzban_ip_limit(payload)
    if actual is None:
        raise VpnPanelError("Marzban: IP limit не изменён панелью", panel="marzban")
    if actual != expected:
        raise VpnPanelError(
            f"Marzban update verification failed: expected limit_ip={expected} got {actual}",
            panel="marzban",
        )


def require_user_payload(payload: dict[str, Any] | None, *, username: str) -> dict[str, Any]:
    if payload is None:
        raise VpnPanelNotFoundError(f"Marzban user '{username}' not found", panel="marzban")
    return payload
