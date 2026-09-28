from __future__ import annotations

import json

import pytest

from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.paths import MODELS
from fusion_cad_ai.pipeline import run_pipeline
from fusion_cad_ai.transport.fake import FakeTransport


def test_cube_is_1000_mm3() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "cube"})
    cad.call("execute", {"code": "make_box_mm(10, 10, 10, 'cube')"})
    measured = cad.call("measure", {})
    assert measured["volume_mm3"] == pytest.approx(1000.0)
    assert measured["bbox_mm"] == pytest.approx([10, 10, 10])


def test_execute_keeps_namespace() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "state"})
    cad.call("execute", {"code": "marker = 7"})
    second = cad.call("execute", {"code": "result = marker"})
    assert second["result"] == 7


def test_import_os_rejected_by_execute() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "sandbox"})
    with pytest.raises(FcaError) as caught:
        cad.call("execute", {"code": "import os"})
    assert caught.value.code == "SANDBOX_VIOLATION"


def test_foreign_document_rejected() -> None:
    cad = FakeTransport()
    with pytest.raises(FcaError) as caught:
        cad.call("execute", {"code": "make_box_mm(1, 1, 1)"})
    assert caught.value.code == "NOT_FCA_DOCUMENT"


def test_pipeline_plate() -> None:
    result = run_pipeline("plate_e2e", ["step", "stl", "3mf", "f3d"], FakeTransport())
    assert result.ok
    assert result.stages["validate"]["ok"]
    assert len(result.files) == 4


def test_reference_bboxes() -> None:
    cad = FakeTransport()
    for name, bbox in (
        ("flange", [40, 40, 8]),
        ("enclosure", [80, 40, 25]),
        ("print_bracket", [24, 16, 17.5]),
        ("plate_e2e", [60, 40, 6]),
    ):
        cad.call("new_design", {"name": name})
        cad.call("execute_file", {"path": str(MODELS / "parts" / f"{name}.py")})
        measured = cad.call("measure", {})
        assert measured["bbox_mm"] == pytest.approx(bbox), name


def test_pin_clearance_and_interference() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "pin"})
    cad.call("execute_file", {"path": str(MODELS / "assemblies" / "pin_joint.py")})
    loose = cad.call("interference", {"objects": "Part_001_base,Part_002_cap"})
    assert loose["interference"] is False
    cad.call("new_design", {"name": "pin-tight"})
    cad.call(
        "execute_file",
        {"path": str(MODELS / "assemblies" / "pin_joint.py"), "params_json": json.dumps({"clearance_mm": -0.1})},
    )
    tight = cad.call("interference", {"objects": "Part_001_base,Part_002_cap"})
    assert tight["interference"] is True


def test_execute_file_rolls_back() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "rollback"})
    cad.call("execute", {"code": "make_box_mm(10, 10, 10, 'keep')"})
    broken = MODELS / "parts" / "broken_rollback.py"
    broken.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True)\nclass BrokenParams:\n    unit: str = 'mm'\n"
        "def build(ctx, params=None):\n"
        "    ctx.box(4, 4, 4, center_mm=(0, 0, 2), name='bad')\n"
        "    raise RuntimeError('сломано')\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(RuntimeError):
            cad.call("execute_file", {"path": str(broken)})
        measured = cad.call("measure", {})
        assert measured["volume_mm3"] == pytest.approx(1000.0)
        assert "bad" not in cad.bodies
    finally:
        broken.unlink(missing_ok=True)


def test_reset_needs_confirm() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "reset"})
    with pytest.raises(FcaError) as caught:
        cad.call("reset", {"confirm": False})
    assert caught.value.code == "CONFIRMATION_REQUIRED"


def test_motion_sweep_reports_angle() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "motion"})
    cad.call("execute_file", {"path": str(MODELS / "assemblies" / "motion_stop.py")})
    report = cad.call("motion_sweep", {"joint": 0, "start_deg": 0, "stop_deg": 90, "steps": 8})
    assert report["collision"] is True
    assert report["restored"] is True


def test_cloud_save_needs_confirm() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "cloud"})
    with pytest.raises(FcaError) as caught:
        cad.call("cloud_save", {"confirm": False})
    assert caught.value.code == "CONFIRMATION_REQUIRED"


def test_params_set_requires_unit() -> None:
    cad = FakeTransport()
    cad.call("new_design", {"name": "params"})
    with pytest.raises(FcaError) as caught:
        cad.call("params_set", {"values": {"length_mm": 10}})
    assert caught.value.code == "UNIT_AMBIGUOUS"
