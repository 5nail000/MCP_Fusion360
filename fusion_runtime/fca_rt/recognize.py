"""Holes and bolt circles from cylindrical faces. CAM recognition is a second source."""

from __future__ import annotations

import math

from fca_rt.doc import require_fca
from fca_rt.features import _walk_bodies
from fca_rt.units import cm_to_mm


def find_features(family: str = "holes") -> dict:
    design = require_fca()
    holes = []
    for body in _walk_bodies(design.rootComponent):
        for face in body.faces:
            geom = face.geometry
            radius = getattr(geom, "radius", None)
            axis = getattr(geom, "axis", None)
            origin = getattr(geom, "origin", None)
            if radius is None or axis is None or origin is None:
                continue
            holes.append(
                {
                    "body": body.name,
                    "diameter_mm": cm_to_mm(float(radius) * 2.0),
                    "center_mm": [cm_to_mm(origin.x), cm_to_mm(origin.y), cm_to_mm(origin.z)],
                    "axis": _axis_name(axis),
                }
            )
    unique = _unique_holes(holes)
    return {"family": family, "holes": unique, "patterns": _patterns(unique) if family in {"holes", "hole_patterns", "all"} else []}


def resolve(object_name: str, selector: str, label: str) -> dict:
    from fca_rt.features import body_by_name

    require_fca()
    body = body_by_name(object_name)
    tag = label or "resolved"
    try:
        existing = body.attributes.itemByName("fca", tag)
        if existing is not None:
            existing.value = selector
        else:
            body.attributes.add("fca", tag, selector)
    except Exception:
        pass
    token = ""
    try:
        token = str(body.entityToken)
    except Exception:
        token = ""
    return {"name": object_name, "label": tag, "selector": selector, "entity_token": token}


def _axis_name(axis) -> str:
    comps = (abs(axis.x), abs(axis.y), abs(axis.z))
    return "xyz"[comps.index(max(comps))]


def _unique_holes(holes: list[dict]) -> list[dict]:
    kept = []
    for hole in holes:
        if any(
            abs(hole["diameter_mm"] - other["diameter_mm"]) < 0.05
            and all(abs(hole["center_mm"][i] - other["center_mm"][i]) < 0.2 for i in range(3))
            for other in kept
        ):
            continue
        kept.append(hole)
    return kept


def _unique_xy(holes: list[dict]) -> list[dict]:
    """One hole per XY position. A fillet mouth is wider than the bore and is not a second hole."""
    kept = []
    for hole in holes:
        match = next(
            (
                other
                for other in kept
                if abs(hole["center_mm"][0] - other["center_mm"][0]) < 0.2
                and abs(hole["center_mm"][1] - other["center_mm"][1]) < 0.2
            ),
            None,
        )
        if match is None:
            kept.append(dict(hole))
        elif hole["diameter_mm"] < match["diameter_mm"]:
            match["diameter_mm"] = hole["diameter_mm"]
    return kept


def _patterns(holes: list[dict]) -> list[dict]:
    holes = _unique_xy(holes)
    if len(holes) < 3:
        return []
    cx = sum(item["center_mm"][0] for item in holes) / len(holes)
    cy = sum(item["center_mm"][1] for item in holes) / len(holes)
    radii = [math.hypot(item["center_mm"][0] - cx, item["center_mm"][1] - cy) for item in holes]
    outer = [item for item, radius in zip(holes, radii) if radius > 1.0]
    if len(outer) < 3:
        return []
    outer_radii = [math.hypot(item["center_mm"][0] - cx, item["center_mm"][1] - cy) for item in outer]
    if max(outer_radii) - min(outer_radii) > 0.3:
        return []
    return [{"type": "bolt_circle", "holes": len(outer), "bolt_circle_diameter_mm": (sum(outer_radii) / len(outer_radii)) * 2.0}]
