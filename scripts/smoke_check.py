#!/usr/bin/env python3
"""Safe post-install diagnostics — no external API calls by default."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_VARS = ("BOT_TOKEN", "DATABASE_URL", "ADMIN_TELEGRAM_IDS")
OPTIONAL_VARS = (
    "POSTGRES_PASSWORD",
    "MARZBAN_ENABLED",
    "XUI_ENABLED",
    "PAYMENT_DETAILS",
)
DATABASE_URL_RE = re.compile(
    r"^postgresql\+asyncpg://[^:]+:[^@]+@[^:/]+:\d+/\w+$",
)
PLACEHOLDER_PATTERNS = (
    "your_telegram_bot_token",
    "change_me",
    "example.com",
    "0000 0000",
)


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def mask(value: str, visible: int = 4) -> str:
    if len(value) <= visible:
        return "***"
    return f"{value[:visible]}…({len(value)} chars)"


def check_required_env() -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_VARS:
        raw = os.environ.get(name, "").strip()
        if not raw:
            errors.append(f"Missing required env: {name}")
            continue
        lower = raw.lower()
        if any(p in lower for p in PLACEHOLDER_PATTERNS):
            errors.append(f"{name} still looks like a placeholder")
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and not DATABASE_URL_RE.match(db_url):
        errors.append("DATABASE_URL format looks invalid (expected postgresql+asyncpg://...)")
    return errors


def check_imports() -> list[str]:
    errors: list[str] = []
    modules = (
        "app.config.settings",
        "app.application.services.settings_service",
        "app.presentation.handlers",
        "app.main",
    )
    for mod in modules:
        try:
            __import__(mod)
        except Exception as exc:
            errors.append(f"Import failed: {mod} ({type(exc).__name__})")
    return errors


def main() -> int:
    env_path = ROOT / ".env"
    load_dotenv(env_path)

    print("=== Telegram VPN Bot — smoke check ===")
    print(f"Project root: {ROOT}")
    print(f".env file:   {'found' if env_path.is_file() else 'not found (using environment)'}")

    errors = check_required_env()
    errors.extend(check_imports())

    print("\n--- Environment (safe summary) ---")
    for name in REQUIRED_VARS + OPTIONAL_VARS:
        raw = os.environ.get(name, "")
        if not raw:
            print(f"  {name}: <empty>")
        elif name in {"BOT_TOKEN", "POSTGRES_PASSWORD", "MARZBAN_PASSWORD", "XUI_PASSWORD", "MARZBAN_API_TOKEN", "XUI_API_TOKEN"}:
            print(f"  {name}: {mask(raw)}")
        elif name == "DATABASE_URL":
            print(f"  {name}: {mask(raw, 12)}")
        else:
            preview = raw.replace("\n", " ")[:60]
            print(f"  {name}: {preview}{'…' if len(raw) > 60 else ''}")

    if os.environ.get("SMOKE_CHECK_LIVE") == "1":
        print("\n[WARN] SMOKE_CHECK_LIVE=1 — live API checks are not implemented in this script.")

    print("\n--- Result ---")
    if errors:
        for item in errors:
            print(f"  FAIL: {item}")
        return 1

    print("  OK: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
