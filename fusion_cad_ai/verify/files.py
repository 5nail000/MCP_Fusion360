"""File gates: STEP header, STL shell, 3MF zip. Deep geometry is optional."""

from __future__ import annotations

import zipfile
from pathlib import Path


def verify_files(paths: dict[str, Path]) -> dict:
    reports = []
    warnings = []
    ok = True
    for fmt, path in paths.items():
        item = {"format": fmt, "path": str(path), "ok": False, "bytes": 0}
        if not path.is_file():
            item["error"] = "файл не создан"
            ok = False
            reports.append(item)
            continue
        item["bytes"] = path.stat().st_size
        if item["bytes"] < 32 and fmt != "dxf":
            item["error"] = "файл слишком маленький"
            ok = False
            reports.append(item)
            continue
        if fmt == "step" and not path.read_text(encoding="utf-8", errors="replace").startswith("ISO-10303-21"):
            item["error"] = "нет заголовка STEP"
            ok = False
        elif fmt == "stl" and not _stl_ok(path):
            item["error"] = "STL не читается"
            ok = False
        elif fmt in {"3mf", "f3d"} and not _zip_ok(path):
            item["error"] = "архив повреждён"
            ok = False
        else:
            item["ok"] = True
        reports.append(item)
    mesh = _mesh_warnings(paths.get("stl"))
    warnings.extend(mesh)
    brep = _brep_warning(paths.get("step"))
    warnings.extend(brep)
    return {"ok": ok, "files": reports, "warnings": warnings}


def _stl_ok(path: Path) -> bool:
    data = path.read_bytes()
    if data.startswith(b"solid"):
        return b"endsolid" in data
    return len(data) >= 84


def _zip_ok(path: Path) -> bool:
    if not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    return bool(names)


def _mesh_warnings(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    try:
        import trimesh
    except ImportError:
        return ["trimesh не установлен: watertight STL не проверялся. Группа verify."]
    mesh = trimesh.load(path, force="mesh")
    if not getattr(mesh, "is_watertight", False):
        return ["STL не watertight"]
    return []


def _brep_warning(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    try:
        from build123d import import_step
    except ImportError:
        return ["build123d не установлен: глубокая проверка STEP пропущена. Группа verify."]
    try:
        shape = import_step(str(path))
    except Exception as exc:
        return [f"STEP не открылся во втором ядре: {exc}"]
    if shape is None:
        return ["STEP не дал форму во втором ядре"]
    return []
