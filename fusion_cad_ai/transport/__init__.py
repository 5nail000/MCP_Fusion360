"""How the server reaches Fusion."""

from __future__ import annotations

from fusion_cad_ai.config import TRANSPORT
from fusion_cad_ai.transport.base import FusionTransport

_current: FusionTransport | None = None


def set_transport(transport: FusionTransport | None) -> None:
    global _current
    _current = transport


def get_transport() -> FusionTransport:
    if _current is not None:
        return _current
    kind = TRANSPORT
    if kind == "fake":
        from fusion_cad_ai.transport.fake import FakeTransport

        return FakeTransport()
    if kind == "bridge":
        from fusion_cad_ai.transport.bridge import BridgeTransport

        return BridgeTransport()
    from fusion_cad_ai.transport.official_mcp import OfficialMcpTransport

    return OfficialMcpTransport()
