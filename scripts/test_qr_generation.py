"""
Development-only script to verify in-memory QR generation.

Usage:
    python scripts/test_qr_generation.py
    python scripts/test_qr_generation.py --save
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import importlib.util

_qr_module_path = ROOT / "app" / "application" / "services" / "qr_code_service.py"
_spec = importlib.util.spec_from_file_location("qr_code_service", _qr_module_path)
if _spec is None or _spec.loader is None:
    raise SystemExit("Cannot load qr_code_service module.")
_qr_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_qr_module)
QrCodeService = _qr_module.QrCodeService

SAMPLE_LINK = "vless://example-user@vpn.example.com:443?type=ws&security=tls#demo"


def main() -> None:
    parser = argparse.ArgumentParser(description="Test in-memory QR generation.")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save test QR image to tmp/ (gitignored).",
    )
    args = parser.parse_args()

    output_dir = ROOT / "tmp" if args.save else None
    service = QrCodeService(save_to_disk=args.save, output_dir=output_dir)

    png_bytes = service.generate_png_bytes(SAMPLE_LINK)
    if len(png_bytes) < 100:
        raise SystemExit("FAIL: QR PNG bytes look too small.")

    print(f"OK: generated {len(png_bytes)} bytes of PNG data.")
    if args.save and output_dir is not None:
        saved = list(output_dir.glob("qr_*.png"))
        if saved:
            print(f"Saved to: {saved[0]}")


if __name__ == "__main__":
    main()
