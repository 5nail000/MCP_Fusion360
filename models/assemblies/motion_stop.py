"""Arm and stopper. A revolute sweep from 0 to 90 degrees meets the stopper near 45 degrees."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotionParams:
    arm_length_mm: float = 40.0
    arm_width_mm: float = 8.0
    arm_height_mm: float = 6.0
    stop_size_mm: float = 12.0
    unit: str = "mm"


EXPECTED_COLLISION_DEG = 45.0


def build(ctx, params: MotionParams | None = None) -> None:
    p = params or MotionParams()
    ctx.params_from(p)
    ctx.component("Arm")
    arm = ctx.box(
        p.arm_length_mm,
        p.arm_width_mm,
        p.arm_height_mm,
        center_mm=(p.arm_length_mm / 2.0, 0.0, p.arm_height_mm / 2.0),
        name="arm",
    )
    ctx.show(arm, "Arm")
    ctx.component("Stop")
    stop = ctx.box(
        p.stop_size_mm,
        p.stop_size_mm,
        p.arm_height_mm,
        center_mm=(22.0, 22.0, p.arm_height_mm / 2.0),
        name="stop",
    )
    ctx.show(stop, "Stop")
    ctx.joint("revolute", "Arm", "Stop", {"min_deg": 0.0, "max_deg": 90.0}, collision_at_deg=EXPECTED_COLLISION_DEG)
