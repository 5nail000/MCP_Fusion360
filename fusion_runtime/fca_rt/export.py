"""Exports. STEP and Fusion archive take a component. Meshes take a body."""

from __future__ import annotations

import os

from fca_rt.doc import active_design, require_fca
from fca_rt.errors import RtError
from fca_rt.features import body_by_name
from fca_rt.log import log

_COMPONENT_FORMATS = {"step", "f3d", "smt", "iges"}
_BODY_FORMATS = {"stl", "3mf", "obj"}


def export_files(targets: dict, object_name: str = "") -> dict:
    design = require_fca()
    manager = design.exportManager
    _app, design = active_design()
    root = design.rootComponent
    body = body_by_name(object_name) if object_name else _first_body(root)
    written = []
    for fmt, path in targets.items():
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        options = _options(manager, fmt, path, root, body)
        try:
            ok = bool(manager.execute(options))
        except Exception as exc:
            message = str(exc).splitlines()[-1][:300]
            if "license" in message.lower() or "personal" in message.lower():
                raise RtError("LICENSE_BLOCKED", message, hint="Формат недоступен на текущей лицензии.") from exc
            raise RtError("FUSION_API_ERROR", message) from exc
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        if not ok or size < 32:
            raise RtError("FUSION_API_ERROR", f"Экспорт {fmt} не записал файл", hint=path)
        log(f"export {fmt} {size} bytes")
        written.append({"format": fmt, "path": path, "bytes": int(size)})
    return {"files": written}


def _options(manager, fmt: str, path: str, root, body):
    key = fmt.lower()
    if key == "step":
        return manager.createSTEPExportOptions(path, root)
    if key == "f3d":
        return manager.createFusionArchiveExportOptions(path, root)
    if key == "smt":
        return manager.createSMTExportOptions(path, root)
    if key == "iges":
        return manager.createIGESExportOptions(path, root)
    geometry = body if body is not None else root
    if key == "stl":
        return manager.createSTLExportOptions(geometry, path)
    if key == "3mf":
        return manager.createC3MFExportOptions(geometry, path)
    if key == "obj":
        return manager.createOBJExportOptions(geometry, path)
    raise RtError("FUSION_API_ERROR", f"Формат {fmt} не поддержан")


def _first_body(component):
    if component.bRepBodies.count:
        return component.bRepBodies.item(0)
    for index in range(component.occurrences.count):
        found = _first_body(component.occurrences.item(index).component)
        if found is not None:
            return found
    return None
