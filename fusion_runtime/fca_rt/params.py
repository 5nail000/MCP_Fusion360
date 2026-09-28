"""User parameters. Expressions keep the design editable in the Fusion UI."""

from __future__ import annotations

from fca_rt.doc import active_design, require_fca
from fca_rt.errors import RtError


def sync_object(obj) -> dict:
    design = require_fca()
    fields = getattr(obj, "__dataclass_fields__", None)
    if not fields:
        raise RtError("FUSION_API_ERROR", "params_from ждёт dataclass")
    written = {}
    for name in fields:
        if name == "unit" or name.startswith("_"):
            continue
        value = getattr(obj, name)
        if name.endswith("_mm"):
            written[name] = _upsert(design, name, f"{float(value)} mm", "mm")
        elif name.endswith("_deg"):
            written[name] = _upsert(design, name, f"{float(value)} deg", "deg")
        elif isinstance(value, bool):
            continue
        elif isinstance(value, int):
            written[name] = _upsert(design, name, str(int(value)), "")
        elif isinstance(value, float):
            written[name] = _upsert(design, name, str(float(value)), "")
    return written


def upsert_one(name: str, value: float, unit: str) -> dict:
    design = require_fca()
    expression = f"{value} {unit}".strip()
    return _upsert(design, name, expression, unit)


def read_all() -> dict:
    _app, design = active_design()
    rows = {}
    for index in range(design.userParameters.count):
        item = design.userParameters.item(index)
        rows[item.name] = {"expression": item.expression, "value": _safe_value(item), "unit": str(item.unit) if hasattr(item, "unit") else ""}
    return rows


def set_values(values: dict) -> list[str]:
    design = require_fca()
    updated = []
    for name, spec in values.items():
        if not isinstance(spec, dict) or not spec.get("unit"):
            raise RtError("UNIT_AMBIGUOUS", f"Параметр {name} передан без единиц")
        _upsert(design, name, f"{spec['value']} {spec['unit']}", str(spec["unit"]))
        updated.append(name)
    return updated


def _upsert(design, name: str, expression: str, units: str) -> dict:
    import adsk.core

    existing = _find(design, name)
    if existing is not None:
        existing.expression = expression
        return {"name": name, "expression": expression}
    value = adsk.core.ValueInput.createByString(expression)
    design.userParameters.add(name, value, units, "fusion-cad-ai")
    return {"name": name, "expression": expression}


def _find(design, name: str):
    for index in range(design.userParameters.count):
        item = design.userParameters.item(index)
        if item.name == name:
            return item
    return None


def _safe_value(item) -> float:
    try:
        return float(item.value)
    except Exception:
        return 0.0
