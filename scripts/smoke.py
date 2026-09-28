"""Run after a Fusion update. Does not save or close documents."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.logger import log
from fusion_cad_ai.transport.official_mcp import OfficialMcpTransport


def main() -> int:
    cad = OfficialMcpTransport()
    try:
        health = cad.call("health", {}, read_only=True)
    except FcaError as exc:
        log(f"{exc.code}: {exc.message}", "ERROR")
        return 2
    log(f"Fusion {health.get('fusion_build')} документов {health.get('document_count')}")
    if hasattr(cad, "read"):
        try:
            license_info = cad.read({"queryType": "licensing"})
            summary = license_info.get("licenseTypeSummary") or license_info.get("licenseType") or license_info
            log(f"лицензия {summary}")
        except FcaError as exc:
            log(f"лицензия не прочитана: {exc.message}", "WARN")
    cad.call("new_design", {"name": "smoke"})
    cad.call("execute", {"code": "make_box_mm(10, 10, 10, 'smoke')"})
    measured = cad.call("measure", {}, read_only=True)
    volume = float(measured["volume_mm3"])
    bbox = measured["bbox_mm"]
    log(f"куб объём {volume:.3f} мм3 bbox {bbox}")
    if abs(volume - 1000.0) > 2.0 or any(abs(float(item) - 10.0) > 0.02 for item in bbox):
        log("куб не сошёлся с 10 мм", "ERROR")
        return 3
    log("smoke PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
