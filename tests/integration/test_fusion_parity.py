"""Live parity, export, and the extra Fusion domains. Fusion must already be running."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.paths import EXPORT_DIRS, MODELS, RENDERS, ROOT
from fusion_cad_ai.transport.envelope import runtime_sha
from fusion_cad_ai.transport.official_mcp import OfficialMcpTransport

pytestmark = pytest.mark.fusion

_GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "golden" / "parity_freecad.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cad() -> OfficialMcpTransport:
    return OfficialMcpTransport()


def _bbox_size(measured: dict) -> list[float]:
    return [float(item) for item in measured["bbox_mm"]]


def test_health_matches_runtime_and_reads_license(cad: OfficialMcpTransport) -> None:
    health = cad.call("health", {}, read_only=True)
    assert health["runtime_sha"] == runtime_sha()
    assert health["fusion_build"]
    license_info = cad.read({"queryType": "licensing"})
    assert isinstance(license_info, dict)
    assert license_info


def test_official_tool_names_match_snapshot(cad: OfficialMcpTransport) -> None:
    snapshot = json.loads((ROOT / "docs" / "official-fusion-mcp" / "2705.1.25.json").read_text(encoding="utf-8"))
    live = {item.get("name") for item in cad.list_tools()}
    expected = set(snapshot["tool_names"])
    assert live == expected


def test_golden_parts(cad: OfficialMcpTransport) -> None:
    specs = {
        "flange": ("parts", "flange", None),
        "enclosure": ("parts", "enclosure", None),
        "print_bracket": ("parts", "print_bracket", None),
    }
    for name, (folder, stem, _object) in specs.items():
        cad.call("new_design", {"name": name})
        cad.call("execute_file", {"path": str(MODELS / folder / f"{stem}.py")})
        measured = cad.call("measure", {}, read_only=True)
        want = _GOLDEN[name]
        assert measured["volume_mm3"] == pytest.approx(want["volume_mm3"], rel=_GOLDEN["tolerances"]["volume_ratio"])
        assert _bbox_size(measured) == pytest.approx(want["bbox_mm"], abs=_GOLDEN["tolerances"]["bbox_mm"])


def test_flange_bolt_circle_and_audit(cad: OfficialMcpTransport) -> None:
    cad.call("new_design", {"name": "flange"})
    cad.call("execute_file", {"path": str(MODELS / "parts" / "flange.py")})
    found = cad.call("find_features", {"family": "holes"}, read_only=True)
    circles = [item for item in found["patterns"] if item["type"] == "bolt_circle"]
    assert circles and circles[0]["holes"] == 4
    audit = cad.call("design_audit", {"epsilon": 0.1, "max_params": 8})
    assert audit["ok"] is True


def test_pin_volumes(cad: OfficialMcpTransport) -> None:
    cad.call("new_design", {"name": "pin_joint"})
    cad.call("execute_file", {"path": str(MODELS / "assemblies" / "pin_joint.py")})
    base = cad.call("measure", {"object_name": "Part_001_base"}, read_only=True)
    cap = cad.call("measure", {"object_name": "Part_002_cap"}, read_only=True)
    assert base["volume_mm3"] == pytest.approx(_GOLDEN["pin_base"]["volume_mm3"], rel=0.002)
    assert cap["volume_mm3"] == pytest.approx(_GOLDEN["pin_cap"]["volume_mm3"], rel=0.002)
    assert _bbox_size(base) == pytest.approx(_GOLDEN["pin_base"]["bbox_mm"], abs=0.02)
    assert _bbox_size(cap) == pytest.approx(_GOLDEN["pin_cap"]["bbox_mm"], abs=0.02)


def test_export_and_render(cad: OfficialMcpTransport) -> None:
    from fusion_cad_ai.service import export, render_view

    cad.call("new_design", {"name": "plate_e2e"})
    cad.call("execute_file", {"path": str(MODELS / "parts" / "plate_e2e.py")})
    written = export("plate_e2e", "step,stl,3mf,f3d")
    formats = {item["format"] for item in written["files"]}
    assert formats == {"step", "stl", "3mf", "f3d"}
    for item in written["files"]:
        assert Path(item["path"]).is_file()
        assert item["bytes"] > 32
    shot = render_view(direction="iso", width_px=320, height_px=240, save_to="plate_e2e.png")
    png = Path(shot["png_path"])
    assert png.is_file() and png.stat().st_size > 32
    assert png.parent == RENDERS


def test_printability_both_printers(cad: OfficialMcpTransport) -> None:
    from fusion_cad_ai.service import analyze_printability

    cad.call("new_design", {"name": "plate_e2e"})
    cad.call("execute_file", {"path": str(MODELS / "parts" / "plate_e2e.py")})
    for printer in ("bambu_a1", "bambu_a1_mini"):
        report = analyze_printability(printer)
        assert report["printer"] == printer
        assert report["fits_bed"] is True


def test_motion_sweep_hits_stop(cad: OfficialMcpTransport) -> None:
    cad.call("new_design", {"name": "motion_stop"})
    cad.call("execute_file", {"path": str(MODELS / "assemblies" / "motion_stop.py")})
    sweep = cad.call("motion_sweep", {"joint": 0, "start_deg": 0, "stop_deg": 90, "steps": 12})
    assert sweep["collision"] is True
    assert 0 <= float(sweep["angle_deg"]) <= 90


def test_execute_file_rolls_back(cad: OfficialMcpTransport) -> None:
    path = MODELS / "parts" / "_rollback_probe.py"
    path.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True)\n"
        "class Probe:\n"
        "    length_mm: float = 10.0\n"
        "    unit: str = 'mm'\n"
        "def build(ctx, params=None):\n"
        "    ctx.params_from(params or Probe())\n"
        "    ctx.box(10, 10, 10, name='probe')\n"
        "    raise RuntimeError('rollback')\n",
        encoding="utf-8",
    )
    try:
        cad.call("new_design", {"name": "rollback"})
        with pytest.raises(FcaError):
            cad.call("execute_file", {"path": str(path)})
        state = cad.call("session_state", {}, read_only=True)
        assert "probe" not in state["bodies"]
    finally:
        path.unlink(missing_ok=True)


def test_extra_domains_answer_without_faking_success(cad: OfficialMcpTransport) -> None:
    cad.call("new_design", {"name": "extra"})
    cad.call("execute", {"code": "make_box_mm(20, 20, 4, 'extra')"})
    for op, params in (
        ("cam_setup", {"template": ""}),
        ("sheet_rules", {}),
        ("sheet_flat", {"path": str(EXPORT_DIRS["dxf"] / "extra.dxf"), "thickness_mm": 1.0}),
        ("config_get", {}),
        ("volumetric", {}),
        ("visual_analyses", {}),
        ("cloud_list", {}),
    ):
        try:
            result = cad.call(op, params, read_only=op in {"sheet_rules", "config_get", "visual_analyses", "cloud_list"})
        except FcaError as exc:
            assert exc.code in {"FUSION_API_ERROR", "LICENSE_BLOCKED", "CONFIRMATION_REQUIRED"}
            continue
        assert isinstance(result, dict)
    with pytest.raises(FcaError) as caught:
        cad.call("drawing", {"confirm": False})
    assert caught.value.code in {"CONFIRMATION_REQUIRED", "LICENSE_BLOCKED", "FUSION_API_ERROR"}
    assert EXPORT_DIRS["nc"].parent.name == "exports"
