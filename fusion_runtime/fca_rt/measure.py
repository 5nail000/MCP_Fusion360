"""Measurements published in millimetres, square millimetres, cubic millimetres and grams."""

from __future__ import annotations

from fca_rt.doc import active_design, require_fca
from fca_rt.features import _walk_bodies, body_by_name
from fca_rt.units import cm2_to_mm2, cm3_to_mm3, cm_to_mm, kg_to_g


def measure(object_name: str = "", density_g_cm3: float = 0.0) -> dict:
    design = require_fca()
    bodies = [body_by_name(object_name)] if object_name else list(_walk_bodies(design.rootComponent))
    if not bodies:
        from fca_rt.errors import RtError

        raise RtError("VALIDATION_FAILED", "В документе нет тел")
    volume_cm3 = 0.0
    area_cm2 = 0.0
    faces = 0
    low = [1e99, 1e99, 1e99]
    high = [-1e99, -1e99, -1e99]
    com = [0.0, 0.0, 0.0]
    for body in bodies:
        props = body.physicalProperties
        volume_cm3 += float(props.volume)
        area_cm2 += float(props.area)
        faces += int(body.faces.count)
        bbox = body.boundingBox
        for index, point in enumerate((bbox.minPoint, bbox.maxPoint)):
            coords = (point.x, point.y, point.z)
            for axis in range(3):
                if index == 0:
                    low[axis] = min(low[axis], coords[axis])
                else:
                    high[axis] = max(high[axis], coords[axis])
        center = props.centerOfMass
        weight = float(props.volume) or 1.0
        com[0] += center.x * weight
        com[1] += center.y * weight
        com[2] += center.z * weight
    if volume_cm3:
        com = [value / volume_cm3 for value in com]
    mass_g = kg_to_g(float(bodies[0].physicalProperties.mass)) if len(bodies) == 1 else 0.0
    if density_g_cm3:
        mass_g = volume_cm3 * float(density_g_cm3)
    return {
        "volume_mm3": cm3_to_mm3(volume_cm3),
        "area_mm2": cm2_to_mm2(area_cm2),
        "bbox_mm": [cm_to_mm(high[i] - low[i]) for i in range(3)],
        "bbox_min_mm": [cm_to_mm(value) for value in low],
        "bbox_max_mm": [cm_to_mm(value) for value in high],
        "solid_count": len(bodies),
        "face_count": faces,
        "center_of_mass_mm": [cm_to_mm(value) for value in com],
        "mass_g": mass_g,
        "is_solid": all(bool(body.isSolid) for body in bodies),
    }


def timeline_report(design) -> dict:
    import adsk.fusion

    errors = []
    warnings = []
    for index in range(design.timeline.count):
        item = design.timeline.item(index)
        health = int(getattr(item, "healthState", 0) or 0)
        label = getattr(item.entity, "name", "") if item.entity is not None else str(index)
        if health == adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState:
            errors.append({"index": index, "name": label})
        elif health == adsk.fusion.FeatureHealthStates.WarningFeatureHealthState:
            warnings.append({"index": index, "name": label})
    return {"errors": errors, "warnings": warnings, "count": int(design.timeline.count)}
