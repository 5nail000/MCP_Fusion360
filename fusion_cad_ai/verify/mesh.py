"""STL mesh checks through trimesh."""

from __future__ import annotations

from pathlib import Path


def mesh_report(path: Path) -> dict:
    try:
        import trimesh
    except ImportError:
        return {"checked": False, "warning": "trimesh не установлен"}
    mesh = trimesh.load(path, force="mesh")
    return {
        "checked": True,
        "watertight": bool(getattr(mesh, "is_watertight", False)),
        "volume_mm3": float(getattr(mesh, "volume", 0.0) or 0.0),
        "face_count": int(len(getattr(mesh, "faces", []) or [])),
    }
