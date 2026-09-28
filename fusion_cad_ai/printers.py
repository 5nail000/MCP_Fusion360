"""FDM printer profiles used by analyze_printability."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrinterProfile:
    name: str
    bed_x_mm: float
    bed_y_mm: float
    bed_z_mm: float
    nozzle_mm: float


PRINTERS: dict[str, PrinterProfile] = {
    "bambu_a1": PrinterProfile("bambu_a1", 256.0, 256.0, 256.0, 0.4),
    "bambu_a1_mini": PrinterProfile("bambu_a1_mini", 180.0, 180.0, 180.0, 0.4),
}


def get_printer(name: str) -> PrinterProfile:
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "a1": "bambu_a1",
        "a1_mini": "bambu_a1_mini",
        "a1mini": "bambu_a1_mini",
        "bambu_lab_a1": "bambu_a1",
        "bambu_lab_a1_mini": "bambu_a1_mini",
    }
    key = aliases.get(key, key)
    if key not in PRINTERS:
        known = ", ".join(sorted(PRINTERS))
        raise KeyError(f"Неизвестный принтер {name!r}. Известные: {known}")
    return PRINTERS[key]
