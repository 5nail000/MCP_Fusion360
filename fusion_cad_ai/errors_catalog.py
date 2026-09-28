"""Hints for Fusion API failures. repair_hints looks here before guessing."""

from __future__ import annotations

CATALOG: tuple[tuple[str, str, str], ...] = (
    ("command dialog", "COMMAND_DIALOG_OPEN", "Закройте диалог команды в Fusion и повторите вызов."),
    ("invalid argument geometry", "FUSION_API_ERROR", "STEP и F3D ждут компонент, STL и 3MF — тело."),
    ("license", "LICENSE_BLOCKED", "Операция закрыта лицензией. Смотрите docs/license-limits.md."),
    ("personal use", "LICENSE_BLOCKED", "Лимит Personal Use. Смотрите docs/license-limits.md."),
    ("not a sheet metal", "FUSION_API_ERROR", "Развёртка строится только по листовому телу, не по обычному бруску."),
    ("fully constrained", "VALIDATION_FAILED", "Эскиз не полностью определён. Это предупреждение, не запрет экспорта."),
    ("unit", "UNIT_AMBIGUOUS", "Укажите единицы: mm, cm, inch или deg."),
    ("no active product", "FUSION_API_ERROR", "Нет активного дизайна. Вызовите new_design."),
)


def repair_hints(error_text: str, goal: str = "") -> dict:
    text = (error_text or "").lower()
    hits = []
    for needle, code, hint in CATALOG:
        if needle in text:
            hits.append({"code": code, "hint": hint})
    if not hits:
        hits.append({"code": "FUSION_API_ERROR", "hint": "Сверьте текст с журналом Fusion и повторите шаг пайплайна."})
    return {"goal": goal, "hints": hits}
