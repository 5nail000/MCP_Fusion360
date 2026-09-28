"""Sections and expected-value checks."""

from __future__ import annotations

import json

from fca_rt.doc import require_fca
from fca_rt.features import _walk_bodies, body_by_name
from fca_rt.measure import measure
from fca_rt.units import cm_to_mm, mm_to_cm
from fca_rt.validate import validate


def inspect_part(object_name: str = "", expected_json: str = "") -> dict:
    measured = measure(object_name)
    health = validate(object_name)
    report = {"ok": health["ok"], "measured": measured, "mismatches": [], "warnings": health["warnings"]}
    if not expected_json:
        return report
    expected = json.loads(expected_json)
    mismatches = []
    if "bbox_mm" in expected:
        for got, want in zip(measured["bbox_mm"], expected["bbox_mm"], strict=False):
            if abs(float(got) - float(want)) > 0.02:
                mismatches.append({"field": "bbox_mm", "got_mm": got, "want_mm": want})
    if "solids" in expected and measured["solid_count"] != int(expected["solids"]):
        mismatches.append({"field": "solids", "got": measured["solid_count"], "want": expected["solids"]})
    report["mismatches"] = mismatches
    report["ok"] = health["ok"] and not mismatches
    return report


def cross_sections(axis: str = "Z", num_slices: int = 10) -> dict:
    import adsk.core
    import adsk.fusion

    design = require_fca()
    bodies = list(_walk_bodies(design.rootComponent))
    if not bodies:
        return {"axis": axis, "slices": []}
    measured = measure()
    index = {"X": 0, "Y": 1, "Z": 2}[axis.upper()]
    start = measured["bbox_min_mm"][index]
    end = measured["bbox_max_mm"][index]
    manager = adsk.fusion.TemporaryBRepManager.get()
    normal = [0.0, 0.0, 0.0]
    normal[index] = 1.0
    rows = []
    count = max(int(num_slices), 1)
    for step in range(count):
        position = start + (end - start) * (step + 0.5) / count
        point = [0.0, 0.0, 0.0]
        point[index] = position
        plane = adsk.core.Plane.create(
            adsk.core.Point3D.create(mm_to_cm(point[0]), mm_to_cm(point[1]), mm_to_cm(point[2])),
            adsk.core.Vector3D.create(*normal),
        )
        area = 0.0
        for body in bodies:
            try:
                section = manager.planeIntersection(body, plane)
                if section is not None:
                    area += float(section.physicalProperties.area)
            except Exception:
                continue
        rows.append({"at_mm": position, "area_mm2": area * 100.0})
    return {"axis": axis.upper(), "slices": rows}


def compare(kind: str, a: str = "", b: str = "") -> dict:
    if kind == "fit":
        from fca_rt.assembly import interference

        return interference(a or b, False)
    if kind == "snapshot":
        from fca_rt import session

        snap = session.STATE.snapshots.get(b)
        if snap is None:
            from fca_rt.errors import RtError

            raise RtError("FUSION_API_ERROR", f"Снимок {b} не найден")
        current = measure(a)
        return {"kind": kind, "current_volume_mm3": current["volume_mm3"], "snapshot": b}
    left = measure(a) if a else measure()
    right = measure(b) if b else left
    return {
        "kind": kind,
        "volume_delta_mm3": left["volume_mm3"] - right["volume_mm3"],
        "bbox_a_mm": left["bbox_mm"],
        "bbox_b_mm": right["bbox_mm"],
    }


def design_audit(epsilon: float = 0.1, max_params: int = 8) -> dict:
    from fca_rt.params import read_all
    from fca_rt.snapshots import capture, restore

    design = require_fca()
    capture("fca_auto_before_audit")
    checked = []
    try:
        for name, spec in list(read_all().items())[:max_params]:
            expression = str(spec.get("expression") or "")
            if not expression.endswith(" mm"):
                checked.append({"name": name, "skipped": "не миллиметры"})
                continue
            try:
                original = float(expression.split()[0])
            except ValueError:
                checked.append({"name": name, "skipped": "выражение не число"})
                continue
            brittle = False
            for delta in (epsilon, -epsilon):
                trial = original + delta
                if trial <= 0:
                    continue
                item = _parameter(design, name)
                if item is None:
                    continue
                item.expression = f"{trial} mm"
                health = _healthy(design)
                item.expression = expression
                if not health:
                    brittle = True
            checked.append({"name": name, "brittle": brittle, "epsilon_mm": epsilon})
    finally:
        restore("fca_auto_before_audit")
    return {"ok": not any(item.get("brittle") for item in checked), "parameters": checked}


def _parameter(design, name: str):
    for index in range(design.userParameters.count):
        item = design.userParameters.item(index)
        if item.name == name:
            return item
    return None


def _healthy(design) -> bool:
    import adsk.fusion

    for index in range(design.timeline.count):
        item = design.timeline.item(index)
        if int(getattr(item, "healthState", 0) or 0) == adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState:
            return False
    return True
