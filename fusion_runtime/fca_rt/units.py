"""Length conversion at the Fusion boundary. Callers outside see millimetres."""

from __future__ import annotations

CM_PER_MM = 0.1
MM_PER_CM = 10.0


def mm_to_cm(value_mm: float) -> float:
    return float(value_mm) * CM_PER_MM


def cm_to_mm(value_cm: float) -> float:
    return float(value_cm) * MM_PER_CM


def cm3_to_mm3(value_cm3: float) -> float:
    return float(value_cm3) * 1000.0


def cm2_to_mm2(value_cm2: float) -> float:
    return float(value_cm2) * 100.0


def kg_to_g(value_kg: float) -> float:
    return float(value_kg) * 1000.0


def expr_mm(value: float | str | None, expression: str | None = None) -> str:
    if expression:
        text = str(expression).strip()
        if any(char.isalpha() for char in text):
            return text
        return f"{text} mm"
    return f"{float(value)} mm"
