"""Base with a pin and a cap whose hole is larger by clearance_mm."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PinJointParams:
    plate_size_mm: float = 30.0
    plate_height_mm: float = 6.0
    pin_diameter_mm: float = 8.0
    pin_height_mm: float = 12.0
    clearance_mm: float = 0.2
    seat_gap_mm: float = 0.2
    unit: str = "mm"

    @property
    def hole_diameter_mm(self) -> float:
        return self.pin_diameter_mm + self.clearance_mm


def build(ctx, params: PinJointParams | None = None) -> None:
    p = params or PinJointParams()
    ctx.params_from(p)
    ctx.param("hole_diameter_mm", p.hole_diameter_mm, "mm")
    ctx.component("Part_001_base")
    base = ctx.box(
        p.plate_size_mm,
        p.plate_size_mm,
        p.plate_height_mm,
        center_mm=(0.0, 0.0, p.plate_height_mm / 2.0),
        name="base_plate",
    )
    ctx.cylinder(
        p.pin_diameter_mm,
        p.pin_height_mm,
        center_mm=(0.0, 0.0, p.plate_height_mm + p.pin_height_mm / 2.0),
        join=base,
        diameter_expr="pin_diameter_mm",
        height_expr="pin_height_mm",
    )
    ctx.show(base, "Part_001_base")
    ctx.component("Part_002_cap")
    cap_center_z = p.plate_height_mm + p.seat_gap_mm + p.plate_height_mm / 2.0
    cap = ctx.box(
        p.plate_size_mm,
        p.plate_size_mm,
        p.plate_height_mm,
        center_mm=(0.0, 0.0, cap_center_z),
        name="cap_plate",
    )
    ctx.cut_cylinder(
        cap,
        p.hole_diameter_mm,
        p.plate_height_mm + 2.0,
        (0.0, 0.0, cap_center_z),
        diameter_expr="hole_diameter_mm",
    )
    ctx.show(cap, "Part_002_cap")
    ctx.component("Hardware_pin")
    pin = ctx.cylinder(
        p.pin_diameter_mm,
        p.pin_height_mm,
        center_mm=(0.0, 0.0, p.plate_height_mm + p.pin_height_mm / 2.0),
        diameter_expr="pin_diameter_mm",
        name="hardware_pin",
    )
    ctx.show(pin, "Hardware_pin")
    ctx.joint("revolute", "Part_001_base", "Part_002_cap", {"min_deg": -5.0, "max_deg": 5.0})
