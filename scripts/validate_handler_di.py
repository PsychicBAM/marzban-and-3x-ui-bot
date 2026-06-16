"""
Validate that handler DI parameter names are provided by middleware.

Usage:
    python scripts/validate_handler_di.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLERS_ROOT = ROOT / "app" / "presentation" / "handlers"

# Keys injected by DatabaseMiddleware, UserLanguageMiddleware, and dispatcher setup.
INJECTED_KEYS = frozenset(
    {
        "uow",
        "settings",
        "lang",
        "flow_service",
        "settings_service",
        "plan_service",
        "payment_request_service",
        "subscription_purchase_service",
        "admin_log_service",
        "vpn_provisioning_service",
        "free_plan_activation_service",
        "customer_vpn_service",
        "promo_code_service",
        "qr_code_service",
        "provisioning_notification_service",
        "admin_customer_service",
        "referral_service",
        "user_service",
        "payment_approval_service",
        "promo_activation_service",
        "expiry_notification_service",
        "statistics_service",
        "system_status_service",
        "customer_history_service",
        "support_ticket_service",
        "daily_report_service",
        "manual_provisioning_service",
        "manual_key_flow_service",
        "broadcast_service",
        "broadcast_sender_service",
    },
)

# Aiogram / handler parameters resolved without DatabaseMiddleware keys.
ALLOWED_PARAMS = frozenset(
    {
        "self",
        "cls",
        "message",
        "callback",
        "callback_query",
        "state",
        "bot",
        "event",
        "raw_state",
        "dispatcher",
        "handler",
    },
)

DI_SUFFIXES = ("_service", "_repo")
DI_EXACT = frozenset({"uow", "flow_service"})


class HandlerVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.issues: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if not _is_router_handler(node):
            return
        for arg in node.args.args:
            name = arg.arg
            if name in ALLOWED_PARAMS or name in INJECTED_KEYS:
                continue
            if name in DI_EXACT or name.endswith(DI_SUFFIXES):
                rel = self.path.relative_to(ROOT)
                self.issues.append(f"{rel}:{node.lineno} {node.name}() missing DI key '{name}'")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def _is_router_handler(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = _decorator_target(decorator)
        if target is None:
            continue
        if target.startswith("router."):
            return True
    return False


def _decorator_target(decorator: ast.expr) -> str | None:
    if isinstance(decorator, ast.Attribute):
        parts: list[str] = []
        current: ast.expr = decorator
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        parts.reverse()
        return ".".join(parts)
    if isinstance(decorator, ast.Call):
        return _decorator_target(decorator.func)
    return None


def collect_issues() -> list[str]:
    issues: list[str] = []
    for path in sorted(HANDLERS_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        visitor = HandlerVisitor(path)
        visitor.visit(tree)
        issues.extend(visitor.issues)
    return issues


def main() -> None:
    issues = collect_issues()
    if issues:
        print("Handler DI validation failed:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    print("Handler DI validation passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
