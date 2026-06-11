from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from app.application.dto.system_status import PanelStatusLine, SystemStatusSnapshot
from app.application.exceptions import VpnPanelAuthError, VpnPanelError
from app.config.settings import Settings
from app.infrastructure.db.uow import UnitOfWork
from app.infrastructure.integrations.factory import create_marzban_service, create_xui_service

logger = logging.getLogger(__name__)

_BACKUP_DIR_CANDIDATES = (
    Path("/app/backups"),
    Path("backups"),
    Path("/opt/marzban-and-3x-ui-bot/backups"),
)


class SystemStatusService:
    """Read-only health snapshot for admin diagnostics."""

    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def collect(self) -> SystemStatusSnapshot:
        db_ok, db_error = await self._check_database()
        marzban = await self._check_marzban()
        xui = await self._check_xui()
        total_users = await self._uow.statistics.count_users()
        vpn_counts = await self._uow.statistics.get_vpn_account_counts()
        payments = await self._uow.statistics.get_payment_status_counts()
        last_backup = self._find_latest_backup()
        return SystemStatusSnapshot(
            database_ok=db_ok,
            database_error=db_error,
            marzban=marzban,
            xui=xui,
            total_users=total_users,
            active_subscriptions=vpn_counts.active,
            pending_payments=payments.pending,
            last_backup=last_backup,
        )

    def format_admin_message(self, snapshot: SystemStatusSnapshot) -> str:
        db_line = "✅ OK" if snapshot.database_ok else f"❌ {snapshot.database_error or 'ошибка'}"
        lines = [
            "🩺 <b>Статус системы</b>",
            "",
            f"🤖 Бот: ✅ работает",
            f"🗄 База данных: {db_line}",
            f"📡 Marzban: {self._format_panel_line(snapshot.marzban)}",
            f"📡 3x-ui: {self._format_panel_line(snapshot.xui)}",
            "",
            f"👥 Пользователей: <b>{snapshot.total_users}</b>",
            f"📊 Активных подписок VPN: <b>{snapshot.active_subscriptions}</b>",
            f"📥 Заявок на проверке: <b>{snapshot.pending_payments}</b>",
        ]
        if snapshot.last_backup:
            lines.append(f"💾 Последний бэкап: <code>{snapshot.last_backup}</code>")
        else:
            lines.append("💾 Последний бэкап: не найден")
        lines.append("")
        lines.append(f"🕐 Проверено: {datetime.now(UTC).strftime('%d.%m.%Y %H:%M UTC')}")
        return "\n".join(lines)

    async def _check_database(self) -> tuple[bool, str | None]:
        try:
            await self._uow.session.execute(text("SELECT 1"))
            return True, None
        except Exception as exc:
            logger.warning("Database health check failed", extra={"error": str(exc)[:200]})
            return False, str(exc)[:120]

    async def _check_marzban(self) -> PanelStatusLine:
        if not self._settings.marzban_enabled:
            return PanelStatusLine(enabled=False, ok=None, detail="выключен")
        service = create_marzban_service(self._settings)
        if service is None:
            return PanelStatusLine(enabled=True, ok=False, detail="ошибка конфигурации")
        try:
            await service.get_user("__healthcheck__")
            return PanelStatusLine(enabled=True, ok=True, detail="доступен, auth OK")
        except VpnPanelAuthError as exc:
            return PanelStatusLine(enabled=True, ok=False, detail=f"ошибка авторизации: {exc.message[:80]}")
        except VpnPanelError as exc:
            return PanelStatusLine(enabled=True, ok=False, detail=str(exc.message)[:80])
        except Exception as exc:
            return PanelStatusLine(enabled=True, ok=False, detail=str(exc)[:80])

    async def _check_xui(self) -> PanelStatusLine:
        if not self._settings.xui_enabled:
            return PanelStatusLine(enabled=False, ok=None, detail="выключен")
        service = create_xui_service(self._settings)
        if service is None:
            return PanelStatusLine(enabled=True, ok=False, detail="ошибка конфигурации")
        try:
            await service.list_inbounds()
            return PanelStatusLine(enabled=True, ok=True, detail="доступен, auth OK")
        except VpnPanelAuthError as exc:
            return PanelStatusLine(enabled=True, ok=False, detail=f"ошибка авторизации: {exc.message[:80]}")
        except VpnPanelError as exc:
            return PanelStatusLine(enabled=True, ok=False, detail=str(exc.message)[:80])
        except Exception as exc:
            return PanelStatusLine(enabled=True, ok=False, detail=str(exc)[:80])

    @staticmethod
    def _format_panel_line(panel: PanelStatusLine) -> str:
        if not panel.enabled:
            return f"⚪ {panel.detail}"
        if panel.ok:
            return f"✅ {panel.detail}"
        return f"❌ {panel.detail}"

    @staticmethod
    def _find_latest_backup() -> str | None:
        latest: Path | None = None
        latest_mtime = 0.0
        for base in _BACKUP_DIR_CANDIDATES:
            try:
                if not base.is_dir():
                    continue
                for path in base.glob("*.sql.gz"):
                    try:
                        if not path.is_file():
                            continue
                        mtime = path.stat().st_mtime
                        if latest is None or mtime > latest_mtime:
                            latest = path
                            latest_mtime = mtime
                    except OSError as exc:
                        logger.debug(
                            "Skipping backup file",
                            extra={"path": str(path), "error": str(exc)[:120]},
                        )
            except OSError as exc:
                logger.debug(
                    "Backup directory not readable",
                    extra={"path": str(base), "error": str(exc)[:120]},
                )
        if latest is None:
            return None
        return latest.name
