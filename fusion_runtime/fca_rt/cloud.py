"""Cloud list, open and save. Nothing is deleted. Writes require confirm=true."""

from __future__ import annotations

from fca_rt.doc import application, require_fca
from fca_rt.errors import RtError

SANDBOX_PROJECT = "MCP_Fusion360_Sandbox"


def cloud_list() -> dict:
    app = application()
    projects = []
    try:
        hub = app.data.activeHub
        if hub is None:
            return {"projects": [], "note": "активный хаб Autodesk не выбран"}
        for index in range(hub.dataProjects.count):
            project = hub.dataProjects.item(index)
            projects.append({"name": project.name, "id": getattr(project, "id", "")})
    except Exception as exc:
        return {"projects": [], "error": str(exc).splitlines()[-1][:240]}
    return {"projects": projects}


def cloud_open(confirm: bool, file_id: str = "") -> dict:
    if not confirm:
        raise RtError("CONFIRMATION_REQUIRED", "Открытие облачного файла требует confirm=true")
    if not file_id:
        raise RtError("FUSION_API_ERROR", "Нужен file_id")
    app = application()
    try:
        document = app.documents.open(file_id)
    except Exception as exc:
        raise RtError("FUSION_API_ERROR", str(exc).splitlines()[-1][:240]) from exc
    return {"opened": document.name if document is not None else file_id}


def cloud_save(confirm: bool) -> dict:
    if not confirm:
        raise RtError(
            "CONFIRMATION_REQUIRED",
            "Сохранение в облако требует confirm=true",
            hint=f"Проект-песочница называется {SANDBOX_PROJECT}. Удалений нет.",
        )
    design = require_fca()
    document = design.parentDocument
    try:
        ok = bool(document.save(SANDBOX_PROJECT))
    except Exception as exc:
        message = str(exc).splitlines()[-1][:300]
        raise RtError(
            "FUSION_API_ERROR",
            message,
            hint="Проект создаётся только если Fusion сам предложит его при save. Удалять проекты этот инструмент не умеет.",
        ) from exc
    return {"saved": ok, "project": SANDBOX_PROJECT, "document": document.name}
