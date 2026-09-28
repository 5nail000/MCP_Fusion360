"""Sheet metal rule list and a flat-pattern DXF."""

from __future__ import annotations

import os

from fca_rt.doc import active_design, require_fca
from fca_rt.errors import RtError


def rules() -> dict:
    design = require_fca()
    names = []
    try:
        library = design.designSheetMetalRules
        for index in range(library.count):
            names.append(library.item(index).name)
    except Exception as exc:
        return {"rules": [], "error": str(exc).splitlines()[-1][:240]}
    return {"rules": names}


def flat_pattern(path: str, thickness_mm: float = 1.0) -> dict:
    design = require_fca()
    root = design.rootComponent
    face = _largest_planar_face(root)
    if face is None:
        _app, design = active_design()
        from fca_rt.features import box

        box(40, 20, thickness_mm, center_mm=(0, 0, thickness_mm / 2), name="sheet_blank")
        face = _largest_planar_face(design.rootComponent)
    if face is None:
        raise RtError("FUSION_API_ERROR", "Нет плоской грани для развёртки")
    try:
        pattern = root.createFlatPattern(face)
    except Exception as exc:
        message = str(exc).splitlines()[-1][:300]
        raise RtError(
            "FUSION_API_ERROR",
            message,
            hint="Развёртка нужна листовому телу. Обычный брусок Fusion не разворачивает.",
        ) from exc
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    options = design.exportManager.createDXFFlatPatternExportOptions(path, pattern)
    ok = bool(design.exportManager.execute(options))
    size = os.path.getsize(path) if os.path.isfile(path) else 0
    if not ok or size < 8:
        raise RtError("FUSION_API_ERROR", "DXF развёртки не записан")
    return {"path": path, "bytes": int(size)}


def _largest_planar_face(component):
    import adsk.core

    best = None
    best_area = -1.0
    for index in range(component.bRepBodies.count):
        body = component.bRepBodies.item(index)
        for face in body.faces:
            if not isinstance(face.geometry, adsk.core.Plane):
                continue
            area = float(face.area)
            if area > best_area:
                best = face
                best_area = area
    return best
