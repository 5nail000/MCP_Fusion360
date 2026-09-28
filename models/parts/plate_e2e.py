"""Acceptance plate: 60 x 40 x 6 mm with two through holes of 5 mm."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlateParams:
    length_mm: float = 60.0
    width_mm: float = 40.0
    height_mm: float = 6.0
    hole_diameter_mm: float = 5.0
    hole_spacing_mm: float = 30.0
    unit: str = "mm"


EXPECTED = {"bbox_mm": [60.0, 40.0, 6.0], "solids": 1}


def build(ctx, params: PlateParams | None = None) -> None:
    p = params or PlateParams()
    ctx.params_from(p)
    body = ctx.box(p.length_mm, p.width_mm, p.height_mm, center_mm=(0.0, 0.0, 0.0), name="plate")
    for sign in (-1.0, 1.0):
        ctx.cut_cylinder(
            body,
            p.hole_diameter_mm,
            p.height_mm + 2.0,
            (sign * p.hole_spacing_mm / 2.0, 0.0, 0.0),
            diameter_expr="hole_diameter_mm",
        )
    ctx.show(body, "plate")
