"""Library washer. Thread standards come from Fusion ThreadDataQuery, not from this file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WasherParams:
    outer_diameter_mm: float = 12.0
    inner_diameter_mm: float = 6.4
    thickness_mm: float = 1.6
    unit: str = "mm"


def build(ctx, params: WasherParams | None = None) -> None:
    p = params or WasherParams()
    ctx.params_from(p)
    body = ctx.cylinder(
        p.outer_diameter_mm,
        p.thickness_mm,
        center_mm=(0.0, 0.0, p.thickness_mm / 2.0),
        name="washer",
    )
    ctx.cut_cylinder(
        body,
        p.inner_diameter_mm,
        p.thickness_mm + 1.0,
        (0.0, 0.0, p.thickness_mm / 2.0),
        diameter_expr="inner_diameter_mm",
    )
    ctx.show(body, "washer")
