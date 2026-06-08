from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class PlanInfo:
    id: int
    name: str
    price: Decimal
    duration_days: int
    traffic_limit_gb: int
    ip_limit: int
    issuing_mode: str
    is_active: bool
    description: str | None


@dataclass(slots=True)
class PlanCreateInput:
    name: str
    price: Decimal
    duration_days: int
    traffic_limit_gb: int
    ip_limit: int
    issuing_mode: str
    description: str | None = None
