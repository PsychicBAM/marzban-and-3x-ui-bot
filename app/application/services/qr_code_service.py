from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import qrcode

logger = logging.getLogger(__name__)


class QrCodeService:
    """Generate QR-code images in memory from subscription or VPN links."""

    def __init__(
        self,
        *,
        box_size: int = 10,
        border: int = 4,
        save_to_disk: bool = False,
        output_dir: Path | None = None,
    ) -> None:
        self._box_size = box_size
        self._border = border
        self._save_to_disk = save_to_disk
        self._output_dir = output_dir

    def generate_png_bytes(self, data: str) -> bytes:
        buffer = self.generate_buffer(data)
        return buffer.getvalue()

    def generate_buffer(self, data: str) -> BytesIO:
        if not data or not data.strip():
            raise ValueError("QR data must be a non-empty string.")

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=self._box_size,
            border=self._border,
        )
        qr.add_data(data.strip())
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        if self._save_to_disk:
            self._persist_optional(buffer, data)

        buffer.seek(0)
        return buffer

    def _persist_optional(self, buffer: BytesIO, data: str) -> None:
        if self._output_dir is None:
            logger.warning("save_to_disk enabled but output_dir is not set; skipping file write.")
            return
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"qr_{abs(hash(data.strip())) % 10_000_000}.png"
        path = self._output_dir / filename
        path.write_bytes(buffer.getvalue())
        logger.info("QR code saved to disk", extra={"path": str(path)})
