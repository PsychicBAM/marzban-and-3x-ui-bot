"""
End-to-end static validation checklist for the Telegram VPN bot.

Usage:
    python scripts/validate_e2e_checklist.py
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HANDLERS = ROOT / "app" / "presentation" / "handlers"
KEYBOARDS = ROOT / "app" / "presentation" / "keyboards"

CUSTOMER_MENU_KEYS = (
    "menu.buy_vpn",
    "menu.my_vpn",
    "menu.help",
    "menu.bonuses",
    "menu.more",
    "menu.guide",
    "menu.faq",
    "menu.support",
    "menu.invite_friend",
    "menu.promo_news",
    "menu.promo_codes",
    "menu.history",
    "menu.language",
    "menu.back",
    "menu.renew_vpn",
)

ADMIN_BUTTONS = (
    "📥 Заявки",
    "👥 Клиенты",
    "🆘 Обращения",
    "🛠 Управление",
    "📣 Маркетинг",
    "🩺 Система",
    "🏠 Главное меню",
    "➕ Создать ключ",
    "💰 Тарифы",
    "⚙️ Настройки",
    "📣 Рассылки",
    "🎁 Промокоды",
    "🎁 Рефералы",
    "📊 Статистика",
    "🩺 Статус системы",
    "🔙 Назад",
)

ADMIN_SUBMENU_BUTTONS = (
    "➕ Создать ключ",
    "💰 Тарифы",
    "⚙️ Настройки",
    "📣 Рассылки",
    "🎁 Промокоды",
    "🎁 Рефералы",
    "📊 Статистика",
    "🩺 Статус системы",
)


def _run(cmd: list[str], label: str) -> None:
    print(f">> {label}")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"FAILED: {label}")


def _handler_source_text() -> str:
    parts: list[str] = []
    for path in HANDLERS.rglob("*.py"):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _check_customer_menu_handlers() -> list[str]:
    from app.presentation.i18n import all_menu_texts

    source = _handler_source_text()
    issues: list[str] = []
    for key in CUSTOMER_MENU_KEYS:
        labels = all_menu_texts(key)
        if key in {"menu.guide"}:
            if "guide_menu_filter" not in source and not any(label in source for label in labels):
                issues.append(f"no handler for customer key {key}")
            continue
        if key in {"menu.help", "menu.bonuses", "menu.more", "menu.promo_codes"}:
            if f'menu_text_filter("{key}")' not in source:
                issues.append(f"no menu_text_filter for {key}")
            continue
        if not any(label in source for label in labels) and f'menu_text_filter("{key}")' not in source:
            issues.append(f"no handler coverage for customer key {key} ({labels})")
    return issues


def _check_admin_buttons() -> list[str]:
    source = _handler_source_text()
    issues: list[str] = []
    for label in ADMIN_BUTTONS:
        if label not in source and label.replace("🩺", "") not in source:
            if label == "🔙 Назад":
                if "ADMIN_BACK" not in source:
                    issues.append(f"no handler for admin button {label}")
                continue
            if label in {"🛠 Управление", "📣 Маркетинг", "🩺 Система"}:
                if label not in source:
                    issues.append(f"no handler for admin submenu opener {label}")
                continue
            issues.append(f"no handler for admin button {label}")
    return issues


def _check_risky_profile_access() -> list[str]:
    issues: list[str] = []
    manual_key = HANDLERS / "admin" / "manual_key.py"
    tree = ast.parse(manual_key.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if node.slice.value == "profile" and isinstance(node.ctx, ast.Load):
                # data["profile"] direct subscript is risky
                issues.append("manual_key.py uses direct data['profile'] subscript")
                break
    service = ROOT / "app" / "application" / "services" / "manual_key_flow_service.py"
    text = service.read_text(encoding="utf-8")
    if "profile.traffic_limit_gb" in text and "_profile_get" not in text:
        issues.append("manual_key_flow_service.py uses profile.attr without helper")
    return issues


def main() -> None:
    print("=== E2E static validation checklist ===\n")

    _run([sys.executable, "-m", "compileall", "app", "-q"], "compileall app")
    _run(
        [sys.executable, "-c", "from app.presentation.handlers import build_root_router; build_root_router()"],
        "build_root_router()",
    )
    _run([sys.executable, "scripts/validate_handler_di.py"], "handler DI validation")
    _run([sys.executable, "scripts/test_manual_key_confirmation.py"], "manual key confirmation test")
    _run([sys.executable, "scripts/test_vpn_provisioning_deleted_name.py"], "deleted name provisioning test")

    issues: list[str] = []
    issues.extend(_check_customer_menu_handlers())
    issues.extend(_check_admin_buttons())
    issues.extend(_check_risky_profile_access())

    if issues:
        print("\nFAILED checks:")
        for issue in issues:
            print(f"  - {issue}")
        raise SystemExit(1)

    print("\nAll static E2E checklist items passed.")
    print("Manual Telegram UI flows still require interactive testing in the bot.")


if __name__ == "__main__":
    main()
