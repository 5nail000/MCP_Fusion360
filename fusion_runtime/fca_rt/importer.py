"""STEP, F3D and SMT into the active FCA design. Meshes go to MeshBodies."""

from __future__ import annotations

import os

from fca_rt.doc import application, require_fca
from fca_rt.errors import RtError


def import_file(path: str, name: str = "") -> dict:
    design = require_fca()
    if not os.path.isfile(path):
        raise RtError("FUSION_API_ERROR", "Файл для импорта не найден")
    suffix = os.path.splitext(path)[1].lower()
    app = application()
    manager = app.importManager
    root = design.rootComponent
    if suffix in {".step", ".stp"}:
        options = manager.createSTEPImportOptions(path)
    elif suffix == ".f3d":
        options = manager.createFusionArchiveImportOptions(path)
    elif suffix == ".smt":
        options = manager.createSMTImportOptions(path)
    elif suffix in {".stl", ".obj", ".3mf"}:
        return _import_mesh(design, path, name or os.path.splitext(os.path.basename(path))[0])
    else:
        raise RtError("FUSION_API_ERROR", f"Импорт {suffix} не поддержан")
    try:
        manager.importToTarget(options, root)
    except Exception as exc:
        raise RtError("FUSION_API_ERROR", str(exc).splitlines()[-1][:300]) from exc
    title = name or os.path.splitext(os.path.basename(path))[0]
    return {"name": title, "imported": suffix, "bodies": int(root.bRepBodies.count)}


def _import_mesh(design, path: str, name: str) -> dict:
    root = design.rootComponent
    manager = design.importManager if hasattr(design, "importManager") else None
    if manager is None:
        from fca_rt.doc import application

        manager = application().importManager
    suffix = os.path.splitext(path)[1].lower()
    try:
        if suffix == ".stl":
            options = manager.createSTLImportOptions(path)
        elif suffix == ".obj":
            options = manager.createOBJImportOptions(path)
        else:
            options = manager.createC3MFImportOptions(path) if hasattr(manager, "createC3MFImportOptions") else None
        if options is None:
            raise RtError("FUSION_API_ERROR", "Импорт сетки недоступен в этом билде")
        manager.importToTarget(options, root)
    except RtError:
        raise
    except Exception as exc:
        raise RtError("FUSION_API_ERROR", str(exc).splitlines()[-1][:300]) from exc
    return {"name": name, "imported": suffix, "mesh_bodies": int(root.meshBodies.count)}
