from __future__ import annotations

import logging
from dataclasses import dataclass

from app.application.dto.provisioning import ProvisioningResult
from app.application.services.admin_log_service import AdminLogService
from app.application.services.qr_code_service import QrCodeService
from app.domain.enums import AdminActionType

logger = logging.getLogger(__name__)

PANEL_QR_CAPTIONS: dict[str, str] = {
    "Marzban": "📷 QR-code для Marzban",
    "3x-ui": "📷 QR-code для 3x-ui",
}

QR_FAILURE_CUSTOMER_MESSAGE = (
    "⚠️ QR-code не удалось создать, но ссылка выше работает."
)


@dataclass(slots=True)
class PanelQrDelivery:
    panel: str
    link: str
    caption: str
    png_bytes: bytes | None = None
    filename: str = ""
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.png_bytes is not None and self.error is None


class ProvisioningNotificationService:
    """Prepare QR deliveries and admin summaries for successful VPN provisioning."""

    def __init__(self, qr_code_service: QrCodeService) -> None:
        self._qr = qr_code_service

    def build_panel_qr_deliveries(self, provisioning: ProvisioningResult) -> list[PanelQrDelivery]:
        return self.build_panel_qr_deliveries_from_links(provisioning.subscription_links)

    def build_panel_qr_deliveries_from_links(self, links: dict[str, str]) -> list[PanelQrDelivery]:
        deliveries: list[PanelQrDelivery] = []
        for panel, link in links.items():
            if not link:
                continue
            deliveries.append(self._build_delivery_for_panel(panel, link))
        return deliveries

    def _build_delivery_for_panel(self, panel: str, link: str) -> PanelQrDelivery:
        caption = PANEL_QR_CAPTIONS.get(panel, f"📷 QR-code для {panel}")
        filename = self._filename_for_panel(panel)
        try:
            png_bytes = self._qr.generate_png_bytes(link)
        except Exception as exc:
            safe_error = str(exc)[:500]
            logger.warning(
                "QR generation failed",
                extra={"panel": panel, "error": safe_error},
            )
            return PanelQrDelivery(
                panel=panel,
                link=link,
                caption=caption,
                filename=filename,
                error=safe_error,
            )
        return PanelQrDelivery(
            panel=panel,
            link=link,
            caption=caption,
            png_bytes=png_bytes,
            filename=filename,
        )

    async def log_qr_failures(
        self,
        admin_log_service: AdminLogService,
        *,
        admin_telegram_id: int,
        payment_request_id: int | None,
        deliveries: list[PanelQrDelivery],
    ) -> None:
        for delivery in deliveries:
            if delivery.error is None:
                continue
            await admin_log_service.log(
                admin_telegram_id=admin_telegram_id,
                action=AdminActionType.QR_GENERATION_FAILED,
                details={
                    "payment_request_id": payment_request_id,
                    "panel": delivery.panel,
                    "error": delivery.error,
                },
            )

    def admin_qr_status_message(self, deliveries: list[PanelQrDelivery]) -> str:
        if not deliveries:
            return ""
        lines = ["", "📷 QR-коды:"]
        for delivery in deliveries:
            if delivery.succeeded:
                lines.append(f"✅ {delivery.panel}: отправлен")
            else:
                lines.append(f"⚠️ {delivery.panel}: не создан ({delivery.error or 'ошибка'})")
        return "\n".join(lines)

    @staticmethod
    def _filename_for_panel(panel: str) -> str:
        slug = panel.lower().replace(" ", "_").replace("-", "_")
        return f"vpn_qr_{slug}.png"
