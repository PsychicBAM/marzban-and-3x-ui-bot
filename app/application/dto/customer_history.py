from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HistoryEntry:
    created_at: datetime
    lines: tuple[str, ...]
