"""Millimetre boundary. Fusion stores lengths in centimetres; callers never see that."""

from __future__ import annotations

import math

CM_PER_MM = 0.1
MM_PER_CM = 10.0
MM3_PER_CM3 = 1000.0
MM2_PER_CM2 = 100.0

_LENGTH = {"mm": 1.0, "millimeter": 1.0, "millimetre": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "inch": 25.4, "inches": 25.4}
_ANGLE = {"deg": 1.0, "degree": 1.0, "degrees": 1.0, "rad": 180.0 / math.pi, "radian": 180.0 / math.pi}


class AmbiguousUnitError(ValueError):
    """A size arrived without an explicit unit."""


def require_explicit_unit(raw_value: str | float | int, unit: str | None) -> float:
    """Convert a length to millimetres. Unitless values are rejected."""
    if unit is None or str(unit).strip() == "":
        raise AmbiguousUnitError(f"Размер {raw_value!r} без единиц. Укажите mm, cm или inch.")
    key = str(unit).strip().lower()
    if key not in _LENGTH:
        raise AmbiguousUnitError(f"Неизвестные единицы {unit!r} для размера {raw_value!r}")
    return float(raw_value) * _LENGTH[key]


def require_angle_deg(raw_value: str | float | int, unit: str | None) -> float:
    if unit is None or str(unit).strip() == "":
        raise AmbiguousUnitError(f"Угол {raw_value!r} без единиц. Укажите deg или rad.")
    key = str(unit).strip().lower()
    if key not in _ANGLE:
        raise AmbiguousUnitError(f"Неизвестные единицы угла {unit!r}")
    return float(raw_value) * _ANGLE[key]


def mm_to_cm(value_mm: float) -> float:
    return float(value_mm) * CM_PER_MM


def cm_to_mm(value_cm: float) -> float:
    return float(value_cm) * MM_PER_CM


def cm3_to_mm3(value_cm3: float) -> float:
    return float(value_cm3) * MM3_PER_CM3


def cm2_to_mm2(value_cm2: float) -> float:
    return float(value_cm2) * MM2_PER_CM2


def kg_to_g(value_kg: float) -> float:
    return float(value_kg) * 1000.0


def rad_to_deg(value_rad: float) -> float:
    return float(value_rad) * 180.0 / math.pi


def assert_public_keys(payload: dict) -> None:
    """Reject length-like public fields that forgot a unit suffix."""
    bare = {"volume", "area", "length", "width", "height", "diameter", "radius", "bbox", "mass"}
    for key in payload:
        if key in bare:
            raise AmbiguousUnitError(f"Поле {key!r} без суффикса единиц")
