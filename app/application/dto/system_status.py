from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PanelStatusLine:
    enabled: bool
    ok: bool | None
    detail: str


@dataclass(slots=True)
class SystemStatusSnapshot:
    database_ok: bool
    database_error: str | None
    marzban: PanelStatusLine
    xui: PanelStatusLine
    total_users: int
    active_subscriptions: int
    pending_payments: int
    last_backup: str | None
