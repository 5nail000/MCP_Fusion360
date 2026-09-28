"""Configurations. A null top table is reported, not invented."""

from __future__ import annotations

from fca_rt.doc import require_fca
from fca_rt.errors import RtError


def read() -> dict:
    design = require_fca()
    try:
        table = design.configurationTopTable
    except Exception as exc:
        return {"configured": False, "rows": [], "error": str(exc).splitlines()[-1][:200]}
    if table is None:
        return {
            "configured": False,
            "rows": [],
            "hint": "configurationTopTable пуст, пока в дизайне нет таблицы конфигураций",
        }
    rows = []
    for index in range(table.rows.count):
        row = table.rows.item(index)
        rows.append({"index": index, "name": getattr(row, "name", str(index))})
    return {"configured": True, "rows": rows}


def activate(row: str) -> dict:
    design = require_fca()
    table = design.configurationTopTable
    if table is None:
        raise RtError("FUSION_API_ERROR", "Таблицы конфигураций нет", hint="Создайте конфигурацию в UI или дождитесь строки.")
    for index in range(table.rows.count):
        item = table.rows.item(index)
        if str(index) == str(row) or getattr(item, "name", "") == row:
            if hasattr(table, "activeRow"):
                table.activeRow = item
            return {"row": row, "active": True}
    raise RtError("FUSION_API_ERROR", f"Строка конфигурации {row} не найдена")
