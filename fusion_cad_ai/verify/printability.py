"""Bed fit plus optional augura/trimesh. A missing library is a warning."""

from __future__ import annotations

from pathlib import Path

from fusion_cad_ai.printers import get_printer


def analyze(bbox_mm: list[float], printer_name: str, support_angle_deg: float, nozzle_mm: float, stl_path: Path | None = None) -> dict:
    printer = get_printer(printer_name)
    fits = (
        bbox_mm[0] <= printer.bed_x_mm
        and bbox_mm[1] <= printer.bed_y_mm
        and bbox_mm[2] <= printer.bed_z_mm
    )
    warnings = []
    if nozzle_mm <= 0:
        warnings.append("сопло должно быть больше нуля")
    mesh = {}
    if stl_path is not None and stl_path.is_file():
        try:
            import trimesh

            loaded = trimesh.load(stl_path, force="mesh")
            mesh = {"watertight": bool(loaded.is_watertight), "face_count": int(len(loaded.faces))}
        except ImportError:
            warnings.append("trimesh не установлен, сетка не проверялась")
        try:
            import augura  # noqa: F401
        except ImportError:
            warnings.append("augura не установлен, проверка нависаний пропущена")
    else:
        warnings.append("STL нет, проверка сетки пропущена")
    return {
        "printer": printer.name,
        "bed_mm": [printer.bed_x_mm, printer.bed_y_mm, printer.bed_z_mm],
        "bbox_mm": bbox_mm,
        "fits_bed": fits,
        "nozzle_mm": nozzle_mm,
        "support_angle_deg": support_angle_deg,
        "mesh": mesh,
        "warnings": warnings,
        "ok": fits and not any("сопло" in item for item in warnings),
    }
