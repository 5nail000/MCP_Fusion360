"""Timeline health, solids and volume. Deep BRep checks run on the server from the STEP file."""

from __future__ import annotations

from fca_rt.doc import require_fca
from fca_rt.measure import measure, timeline_report


def validate(object_name: str = "") -> dict:
    design = require_fca()
    health = timeline_report(design)
    measured = measure(object_name)
    errors = list(health["errors"])
    if measured["volume_mm3"] <= 0:
        errors.append({"name": "volume", "message": "объём не больше нуля"})
    if not measured["is_solid"]:
        errors.append({"name": "solid", "message": "есть тело, которое не является solid"})
    underconstrained = 0
    for index in range(design.rootComponent.sketches.count):
        sketch = design.rootComponent.sketches.item(index)
        try:
            if not sketch.isFullyConstrained:
                underconstrained += 1
        except Exception:
            pass
    warnings = list(health["warnings"])
    if underconstrained:
        warnings.append({"name": "sketch", "message": f"эскизов без полной определённости: {underconstrained}"})
    return {
        "ok": not errors,
        "timeline_health": "error" if health["errors"] else "healthy",
        "solid_count": measured["solid_count"],
        "volume_mm3": measured["volume_mm3"],
        "errors": errors,
        "warnings": warnings,
    }
