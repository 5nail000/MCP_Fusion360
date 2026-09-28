"""Client for the optional add-in. ADR-001 did not enable the add-in."""

from __future__ import annotations

import json

from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.paths import RUNTIME


class BridgeTransport:
    """Fails clearly until a bridge descriptor exists. No add-in is shipped."""

    def call(
        self,
        op: str,
        params: dict | None = None,
        *,
        timeout_s: float | None = None,
        read_only: bool = False,
    ) -> dict:
        del op, params, timeout_s, read_only
        self._missing()

    def screenshot(self, direction: str, width_px: int, height_px: int) -> dict:
        del direction, width_px, height_px
        self._missing()

    def _missing(self) -> None:
        marker = RUNTIME / "bridge.json"
        if not marker.is_file():
            raise FcaError(
                "FUSION_NOT_REACHABLE",
                "Транспорт bridge не включён: нет .runtime/bridge.json",
                hint="ADR-001 оставил OfficialMcpTransport основным. Add-in не входит в поставку.",
            )
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FcaError("FUSION_API_ERROR", f"bridge.json повреждён: {exc}") from exc
        raise FcaError(
            "FUSION_NOT_REACHABLE",
            "Описатель моста есть, но add-in FusionCadAiBridge не поставляется",
            hint=f"Порт {data.get('port', '?')}. Используйте FCA_TRANSPORT=official.",
        )
