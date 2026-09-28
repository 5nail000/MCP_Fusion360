"""Live Fusion checks. They are excluded from the default pytest run."""

from __future__ import annotations

import json

import pytest

from fusion_cad_ai.paths import MODELS
from fusion_cad_ai.transport.official_mcp import OfficialMcpTransport

pytestmark = pytest.mark.fusion


@pytest.fixture(scope="module")
def cad() -> OfficialMcpTransport:
    return OfficialMcpTransport()


def test_cube_10_mm(cad: OfficialMcpTransport) -> None:
    cad.call("new_design", {"name": "cube"})
    cad.call("execute", {"code": "make_box_mm(10, 10, 10, 'cube')"})
    measured = cad.call("measure", {}, read_only=True)
    assert measured["volume_mm3"] == pytest.approx(1000.0, rel=0.002)
    assert measured["bbox_mm"] == pytest.approx([10, 10, 10], abs=0.02)


def test_namespace_survives_calls(cad: OfficialMcpTransport) -> None:
    cad.call("new_design", {"name": "state"})
    cad.call("execute", {"code": "marker = 11"})
    second = cad.call("execute", {"code": "result = marker"})
    assert second["result"] == 11


def test_sandbox_blocks_os(cad: OfficialMcpTransport) -> None:
    from fusion_cad_ai.errors import FcaError

    cad.call("new_design", {"name": "sandbox"})
    with pytest.raises(FcaError) as caught:
        cad.call("execute", {"code": "import os"})
    assert caught.value.code == "SANDBOX_VIOLATION"


def test_plate_and_pin(cad: OfficialMcpTransport) -> None:
    cad.call("new_design", {"name": "plate_e2e"})
    cad.call("execute_file", {"path": str(MODELS / "parts" / "plate_e2e.py")})
    plate = cad.call("measure", {}, read_only=True)
    assert plate["bbox_mm"] == pytest.approx([60, 40, 6], abs=0.02)
    cad.call("new_design", {"name": "pin_joint"})
    cad.call("execute_file", {"path": str(MODELS / "assemblies" / "pin_joint.py")})
    loose = cad.call("interference", {"objects": "Part_001_base,Part_002_cap"}, read_only=True)
    assert loose["interference"] is False
    cad.call("new_design", {"name": "pin_tight"})
    cad.call(
        "execute_file",
        {
            "path": str(MODELS / "assemblies" / "pin_joint.py"),
            "params_json": json.dumps({"clearance_mm": -0.1}),
        },
    )
    tight = cad.call("interference", {"objects": "Part_001_base,Part_002_cap"}, read_only=True)
    assert tight["interference"] is True
