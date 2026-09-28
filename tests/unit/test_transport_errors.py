from __future__ import annotations

import pytest

from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.transport.bridge import BridgeTransport
from fusion_cad_ai.transport.official_mcp import OfficialMcpTransport


def test_bridge_is_not_shipped() -> None:
    with pytest.raises(FcaError) as caught:
        BridgeTransport().call("health", {})
    assert caught.value.code == "FUSION_NOT_REACHABLE"


def test_official_port_closed_is_unreachable() -> None:
    transport = OfficialMcpTransport("http://127.0.0.1:1/mcp", timeout_s=1)
    with pytest.raises(FcaError) as caught:
        transport.call("health", {})
    assert caught.value.code == "FUSION_NOT_REACHABLE"
