from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class InstructionSettings:
    text: str | None
    url: str | None
    enabled: bool
