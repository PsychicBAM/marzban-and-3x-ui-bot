from __future__ import annotations

import logging

import httpx

from app.application.exceptions import (
    VpnPanelAuthError,
    VpnPanelConflictError,
    VpnPanelError,
    VpnPanelNotFoundError,
    VpnPanelValidationError,
)

logger = logging.getLogger(__name__)


def map_http_status(
    *,
    panel: str,
    status_code: int,
    body: str,
    context: str,
) -> VpnPanelError:
    message = f"{panel} {context} failed (HTTP {status_code})"
    if status_code in {401, 403}:
        return VpnPanelAuthError(message, panel=panel)
    if status_code == 404:
        return VpnPanelNotFoundError(message, panel=panel)
    if status_code == 409:
        return VpnPanelConflictError(message, panel=panel)
    if status_code == 422:
        return VpnPanelValidationError(f"{message}: {body[:300]}", panel=panel)
    return VpnPanelError(f"{message}: {body[:300]}", panel=panel)


def map_transport_error(panel: str, exc: Exception, *, context: str) -> VpnPanelError:
    if isinstance(exc, VpnPanelError):
        return exc
    if isinstance(exc, httpx.TimeoutException):
        return VpnPanelError(f"{panel} {context} timed out", panel=panel)
    if isinstance(exc, httpx.RequestError):
        logger.warning("%s transport error during %s", panel, context, exc_info=exc)
        return VpnPanelError(f"{panel} {context} network error", panel=panel)
    return VpnPanelError(f"{panel} {context} failed: {exc}", panel=panel)
