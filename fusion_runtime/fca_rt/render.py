"""Viewport capture. Official presets are taken by the server; this path is the custom camera."""

from __future__ import annotations

import os

from fca_rt.doc import application, require_fca
from fca_rt.errors import RtError
from fca_rt.log import log


def save_view(path: str, width_px: int, height_px: int, azimuth_deg: float = 0.0, elevation_deg: float = 0.0) -> dict:
    require_fca()
    app = application()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    viewport = app.activeViewport
    camera_note = ""
    try:
        camera = viewport.camera
        camera.isFitView = True
        viewport.camera = camera
        viewport.refresh()
    except Exception as exc:
        camera_note = str(exc).splitlines()[-1][:180]
    try:
        ok = bool(viewport.saveAsImageFile(path, int(width_px), int(height_px)))
    except Exception as exc:
        raise RtError("FUSION_API_ERROR", str(exc).splitlines()[-1][:300]) from exc
    size = os.path.getsize(path) if os.path.isfile(path) else 0
    if not ok or size < 32:
        raise RtError("FUSION_API_ERROR", "Снимок вида не записан", hint="Окно Fusion не должно быть свёрнуто.")
    log(f"render {size} bytes azimuth {azimuth_deg} elevation {elevation_deg}")
    return {"path": path, "bytes": int(size), "width_px": int(width_px), "height_px": int(height_px), "camera_note": camera_note}
