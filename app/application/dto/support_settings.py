from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SupportSettings:
    username: str | None
    url: str | None
    text: str | None
