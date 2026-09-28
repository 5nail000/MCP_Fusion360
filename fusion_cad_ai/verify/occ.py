"""Deep BRep check through build123d when the verify group is installed."""

from __future__ import annotations

from pathlib import Path


def deep_check(step_path: Path) -> dict:
    try:
        from build123d import import_step
    except ImportError:
        return {"deep": False, "warning": "группа verify не установлена"}
    shape = import_step(str(step_path))
    solids = list(getattr(shape, "solids", lambda: [])())
    return {
        "deep": True,
        "solid_count": len(solids) or (1 if shape is not None else 0),
        "volume_mm3": float(getattr(shape, "volume", 0.0) or 0.0),
        "ok": shape is not None,
    }
