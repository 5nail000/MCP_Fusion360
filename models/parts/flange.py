"""Parametric flange: center hole, bolt circle, top fillet, bottom chamfer."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FlangeParams:
    outer_diameter_mm: float = 40.0
    height_mm: float = 8.0
    center_hole_diameter_mm: float = 10.0
    bolt_circle_diameter_mm: float = 28.0
    bolt_hole_diameter_mm: float = 4.0
    bolt_count: int = 4
    fillet_radius_mm: float = 0.6
    chamfer_mm: float = 0.4
    unit: str = "mm"


EXPECTED = {"bbox_mm": [40.0, 40.0, 8.0], "solids": 1, "hole_patterns": [{"type": "bolt_circle", "holes": 4}]}


def build(ctx, params: FlangeParams | None = None) -> None:
    p = params or FlangeParams()
    ctx.params_from(p)
    body = ctx.cylinder(
        p.outer_diameter_mm,
        p.height_mm,
        center_mm=(0.0, 0.0, p.height_mm / 2.0),
        diameter_expr="outer_diameter_mm",
        height_expr="height_mm",
        name="flange",
    )
    ctx.cut_cylinder(
        body,
        p.center_hole_diameter_mm,
        p.height_mm + 2.0,
        (0.0, 0.0, p.height_mm / 2.0),
        diameter_expr="center_hole_diameter_mm",
    )
    radius = p.bolt_circle_diameter_mm / 2.0
    for index in range(p.bolt_count):
        angle = 2.0 * math.pi * index / p.bolt_count
        ctx.cut_cylinder(
            body,
            p.bolt_hole_diameter_mm,
            p.height_mm + 2.0,
            (radius * math.cos(angle), radius * math.sin(angle), p.height_mm / 2.0),
            diameter_expr="bolt_hole_diameter_mm",
        )
    if p.fillet_radius_mm > 0:
        ctx.fillet_z(body, "top", p.fillet_radius_mm, radius_expr="fillet_radius_mm")
    if p.chamfer_mm > 0:
        ctx.chamfer_z(body, "bottom", p.chamfer_mm, distance_expr="chamfer_mm")
    ctx.show(body, "flange")
