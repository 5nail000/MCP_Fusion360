"""Fusion drawings need a saved DataFile. Without confirm the call stops."""

from __future__ import annotations

from fca_rt.doc import application, require_fca
from fca_rt.errors import RtError


def export_drawing(confirm: bool = False, path: str = "") -> dict:
    design = require_fca()
    document = design.parentDocument
    if not confirm:
        raise RtError(
            "CONFIRMATION_REQUIRED",
            "Чертёж Fusion создаётся из сохранённого документа",
            hint="Повторите с confirm=true. Иначе сервер строит SVG-проекцию из STEP.",
        )
    if document is None or not document.isSaved:
        raise RtError(
            "CONFIRMATION_REQUIRED",
            "Документ ещё не сохранён, createDrawing не получит DataFile",
            hint="Сохраните FCA-документ вручную и повторите. Автосохранение в облако отсюда не делается.",
        )
    try:
        import adsk.drawing

        app = application()
        # The live signature needs a DataFile. We pass the document data file when Fusion exposes it.
        data_file = getattr(document, "dataFile", None)
        if data_file is None:
            raise RtError("LICENSE_BLOCKED", "У документа нет DataFile для чертежа")
        drawing_doc = adsk.drawing.Drawing.create(data_file) if hasattr(adsk.drawing.Drawing, "create") else None
        if drawing_doc is None:
            raise RtError("FUSION_API_ERROR", "adsk.drawing.Drawing.create недоступен в этом билде")
    except RtError:
        raise
    except Exception as exc:
        message = str(exc).splitlines()[-1][:300]
        code = "LICENSE_BLOCKED" if "license" in message.lower() or "personal" in message.lower() else "FUSION_API_ERROR"
        raise RtError(code, message) from exc
    return {"fusion_drawing": True, "path": path}
