"""Nominal, clearance, fit, print and manufacturing sizes. Stored in millimetres."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fusion_cad_ai.logger import log
from fusion_cad_ai.units import AmbiguousUnitError, require_explicit_unit

Kind = Literal["nominal", "manufacturing", "print", "hole", "shaft"]


@dataclass(frozen=True)
class LinearDim:
    """Drawing size plus clearance. Clearance is added to holes and print openings, subtracted from shafts."""

    name: str
    nominal_mm: float
    tolerance_mm: float = 0.0
    clearance_mm: float = 0.0
    kind: Kind = "nominal"
    unit: str = "mm"

    def __post_init__(self) -> None:
        if self.unit.lower() not in {"mm", "millimeter", "millimetre"}:
            raise AmbiguousUnitError(
                f"{self.name}: геометрия хранится в миллиметрах; получено unit={self.unit!r}"
            )
        if self.nominal_mm <= 0:
            raise ValueError(f"{self.name}: nominal_mm должен быть > 0, получено {self.nominal_mm}")

    @property
    def effective_mm(self) -> float:
        if self.kind in {"hole", "print"}:
            return self.nominal_mm + self.clearance_mm
        if self.kind == "shaft":
            return self.nominal_mm - self.clearance_mm
        return self.nominal_mm

    @property
    def manufacturing_mm(self) -> float:
        return self.nominal_mm

    @property
    def print_mm(self) -> float:
        return self.nominal_mm + self.clearance_mm

    @property
    def lower_mm(self) -> float:
        return self.effective_mm - abs(self.tolerance_mm)

    @property
    def upper_mm(self) -> float:
        return self.effective_mm + abs(self.tolerance_mm)


def describe_dims(dims: list[LinearDim]) -> dict[str, float]:
    table = {item.name: item.effective_mm for item in dims}
    log(f"Engineering dimensions (effective mm): {table}")
    return table


__all__ = ["AmbiguousUnitError", "LinearDim", "describe_dims", "require_explicit_unit"]
