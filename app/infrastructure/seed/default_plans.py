from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DefaultPlanSeed:
    name: str
    price: Decimal
    duration_days: int
    traffic_limit_gb: int
    ip_limit: int
    issuing_mode: str
    description: str | None = None


DEFAULT_DEMO_PLANS: tuple[DefaultPlanSeed, ...] = (
    DefaultPlanSeed(
        name="30 дней",
        price=Decimal("200"),
        duration_days=30,
        traffic_limit_gb=0,
        ip_limit=3,
        issuing_mode="both",
        description="Тариф на 30 дней, до 3 устройств",
    ),
    DefaultPlanSeed(
        name="60 дней",
        price=Decimal("370"),
        duration_days=60,
        traffic_limit_gb=0,
        ip_limit=3,
        issuing_mode="both",
        description="Тариф на 60 дней, до 3 устройств",
    ),
    DefaultPlanSeed(
        name="90 дней",
        price=Decimal("560"),
        duration_days=90,
        traffic_limit_gb=0,
        ip_limit=3,
        issuing_mode="both",
        description="Тариф на 90 дней, до 3 устройств",
    ),
)
