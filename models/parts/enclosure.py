"""Open-top enclosure. The inner void is shifted by half the wall, matching the FreeCAD reference."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnclosureParams:
    length_mm: float = 80.0
    width_mm: float = 40.0
    height_mm: float = 25.0
    wall_thickness_mm: float = 2.0
    hole_diameter_mm: float = 8.0
    hole_spacing_mm: float = 30.0
    unit: str = "mm"


EXPECTED = {"bbox_mm": [80.0, 40.0, 25.0], "solids": 1}


def build(ctx, params: EnclosureParams | None = None) -> None:
    p = params or EnclosureParams()
    if p.wall_thickness_mm * 2 >= min(p.length_mm, p.width_mm):
        raise ValueError("wall_thickness_mm слишком велика для length/width")
    ctx.params_from(p)
    body = ctx.box(
        p.length_mm,
        p.width_mm,
        p.height_mm,
        center_mm=(0.0, 0.0, 0.0),
        name="enclosure",
    )
    ctx.cut_box(
        body,
        (
            p.length_mm - 2 * p.wall_thickness_mm,
            p.width_mm - 2 * p.wall_thickness_mm,
            p.height_mm,
        ),
        center_mm=(0.0, 0.0, p.wall_thickness_mm / 2.0),
    )
    span = p.width_mm + 4.0
    for sign in (-1.0, 1.0):
        ctx.cut_cylinder(
            body,
            p.hole_diameter_mm,
            span,
            (sign * p.hole_spacing_mm / 2.0, 0.0, 0.0),
            axis="y",
            diameter_expr="hole_diameter_mm",
        )
    ctx.show(body, "enclosure")
