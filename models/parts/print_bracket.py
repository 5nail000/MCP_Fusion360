"""Printable L-bracket. The hole is opened by the print clearance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrintBracketParams:
    length_mm: float = 24.0
    width_mm: float = 16.0
    height_mm: float = 16.0
    thickness_mm: float = 3.0
    hole_diameter_mm: float = 3.2
    hole_clearance_mm: float = 0.2
    unit: str = "mm"

    @property
    def print_hole_diameter_mm(self) -> float:
        return self.hole_diameter_mm + self.hole_clearance_mm


EXPECTED = {"bbox_mm": [24.0, 16.0, 17.5], "solids": 1}


def build(ctx, params: PrintBracketParams | None = None) -> None:
    p = params or PrintBracketParams()
    ctx.params_from(p)
    ctx.param("print_hole_diameter_mm", p.print_hole_diameter_mm, "mm")
    hole = p.print_hole_diameter_mm
    base = ctx.box(p.length_mm, p.width_mm, p.thickness_mm, center_mm=(0.0, 0.0, 0.0), name="bracket")
    ctx.box(
        p.thickness_mm,
        p.width_mm,
        p.height_mm,
        center_mm=(p.length_mm / 2.0 - p.thickness_mm / 2.0, 0.0, p.height_mm / 2.0),
        join=base,
    )
    ctx.cut_cylinder(
        base,
        hole,
        p.thickness_mm + 2.0,
        (-p.length_mm / 4.0, 0.0, 0.0),
        axis="z",
        diameter_expr="print_hole_diameter_mm",
    )
    ctx.cut_cylinder(
        base,
        hole,
        p.width_mm + 2.0,
        (p.length_mm / 2.0 - p.thickness_mm / 2.0, 0.0, p.height_mm / 2.0),
        axis="x",
        diameter_expr="print_hole_diameter_mm",
    )
    ctx.show(base, "print_bracket")
