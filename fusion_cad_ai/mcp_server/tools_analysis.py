"""Optional analysis groups: library, refs, experimental."""

from __future__ import annotations

from fusion_cad_ai import service
from fusion_cad_ai.mcp_server.tools_core import MUT, RO

LIBRARY = [
    ("search_library", service.search_library, RO, "models/lib и резьбы ThreadDataQuery."),
    ("load_part", service.load_part, MUT, "Вставить деталь из models/lib."),
]
REFS = [
    ("prepare_drawing", service.prepare_drawing, RO, "Лист PNG с подписью. Fusion не нужен."),
    ("crop_drawing", service.crop_drawing, RO, "Обрезать поля листа."),
]
EXPERIMENTAL = [
    ("verify_spec", service.verify_spec, RO, "Сверить измерение со спецификацией JSON."),
    ("suggest_spec", service.suggest_spec, RO, "Черновик спецификации из measure."),
]
