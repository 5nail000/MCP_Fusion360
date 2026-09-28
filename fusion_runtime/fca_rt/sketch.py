"""Sketch helpers. Sketch coordinates are centimetres; arguments here are millimetres."""

from __future__ import annotations

from fca_rt.units import mm_to_cm


def point_mm(x_mm: float, y_mm: float, z_mm: float = 0.0):
    import adsk.core

    return adsk.core.Point3D.create(mm_to_cm(x_mm), mm_to_cm(y_mm), mm_to_cm(z_mm))


def plane_offset(component, base_plane, offset_mm: float):
    if abs(offset_mm) < 1e-9:
        return base_plane
    planes = component.constructionPlanes
    plane_input = planes.createInput()
    import adsk.core

    plane_input.setByOffset(base_plane, adsk.core.ValueInput.createByString(f"{float(offset_mm)} mm"))
    return planes.add(plane_input)


def add_rectangle(sketch, x0_mm: float, y0_mm: float, x1_mm: float, y1_mm: float) -> None:
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(point_mm(x0_mm, y0_mm), point_mm(x1_mm, y1_mm))


def add_circle(sketch, x_mm: float, y_mm: float, diameter_mm: float):
    return sketch.sketchCurves.sketchCircles.addByCenterRadius(point_mm(x_mm, y_mm), mm_to_cm(diameter_mm) / 2.0)


def largest_profile(sketch):
    best = None
    best_area = -1.0
    for index in range(sketch.profiles.count):
        profile = sketch.profiles.item(index)
        try:
            area = float(profile.areaProperties().area)
        except Exception:
            area = 0.0
        if area > best_area:
            best = profile
            best_area = area
    if best is None:
        from fca_rt.errors import RtError

        raise RtError("FUSION_API_ERROR", "Эскиз не дал профиля")
    return best
