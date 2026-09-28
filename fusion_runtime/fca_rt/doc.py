"""FCA documents. Other open designs are never activated, saved, or closed."""

from __future__ import annotations

from fca_rt.errors import RtError
from fca_rt.log import log


def application():
    import adsk.core

    app = adsk.core.Application.get()
    if app is None:
        raise RtError("FUSION_NOT_REACHABLE", "Application.get() вернул пусто")
    return app


def active_design():
    import adsk.fusion

    app = application()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RtError("FUSION_API_ERROR", "Активный документ не является дизайном Fusion")
    return app, design


def require_fca():
    _app, design = active_design()
    if not is_fca(design):
        name = design.parentDocument.name if design.parentDocument else ""
        raise RtError(
            "NOT_FCA_DOCUMENT",
            f"Документ {name or '(без имени)'} не принадлежит fusion-cad-ai",
            hint="Создайте рабочий документ через new_design. Чужие документы не изменяются.",
        )
    return design


def _is_our_document(document, target: str, model_name: str) -> bool:
    if (document.name or "") == target:
        return True
    design = _design_of(document)
    if design is None:
        return False
    return _attr(design, "owner") == "fusion-cad-ai" and _attr(design, "model") == model_name


def _design_of(document):
    import adsk.fusion

    try:
        product = document.products.itemByProductType("DesignProductType")
    except Exception:
        return None
    if product is None:
        return None
    return adsk.fusion.Design.cast(product)


def is_fca(design) -> bool:
    document = design.parentDocument
    name = document.name if document is not None and document.name else ""
    if name.startswith("FCA_"):
        return True
    owner = _attr(design, "owner")
    return owner == "fusion-cad-ai"


def new_design(name: str, design_intent: str = "hybrid") -> dict:
    import adsk.core
    import adsk.fusion

    app = application()
    target = f"FCA_{name}"
    for index in range(app.documents.count):
        document = app.documents.item(index)
        if not _is_our_document(document, target, name):
            continue
        document.activate()
        _app, design = active_design()
        clear_timeline(design)
        _reset_session_geometry()
        _mark(design, name)
        log(f"new_design reuse {target}")
        return {"name": target, "reused": True, "design_type": "parametric", "design_intent": design_intent, "units": "mm"}
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    try:
        document.name = target
    except Exception as exc:
        log(f"rename FCA document failed: {exc}", "WARN")
    _app, design = active_design()
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    intent = {
        "part": adsk.fusion.DesignIntentTypes.PartDesignIntentType,
        "assembly": adsk.fusion.DesignIntentTypes.AssemblyDesignIntentType,
        "hybrid": adsk.fusion.DesignIntentTypes.HybridDesignIntentType,
    }.get(design_intent, adsk.fusion.DesignIntentTypes.HybridDesignIntentType)
    try:
        design.designIntent = intent
    except Exception as exc:
        log(f"designIntent: {exc}", "WARN")
    try:
        design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    except Exception as exc:
        log(f"distance units: {exc}", "WARN")
    _mark(design, name)
    _reset_session_geometry()
    from fca_rt import session

    session.STATE.document_name = target
    log(f"new_design create {target}")
    return {
        "name": document.name or target,
        "reused": False,
        "design_type": "parametric",
        "design_intent": design_intent,
        "units": "mm",
    }


def reset(confirm: bool) -> dict:
    if not confirm:
        raise RtError("CONFIRMATION_REQUIRED", "reset требует confirm=true")
    design = require_fca()
    clear_timeline(design)
    from fca_rt import session

    session.STATE.namespace.clear()
    session.STATE.names.clear()
    log(f"reset {design.parentDocument.name}")
    return {"reset": True, "document": design.parentDocument.name}


def _reset_session_geometry() -> None:
    from fca_rt import session

    session.STATE.names.clear()
    session.STATE.active_component = ""


def clear_timeline(design) -> None:
    guard = 0
    while design.timeline.count > 0 and guard < 800:
        guard += 1
        item = design.timeline.item(design.timeline.count - 1)
        entity = item.entity
        if entity is None or not hasattr(entity, "deleteMe"):
            break
        entity.deleteMe()


def root_component(design=None):
    if design is None:
        _app, design = active_design()
    from fca_rt import session

    name = session.STATE.active_component
    if name:
        found = _find_component(design.rootComponent, name)
        if found is not None:
            return found
    return design.rootComponent


def _find_component(component, name: str):
    if component.name == name:
        return component
    for index in range(component.occurrences.count):
        child = component.occurrences.item(index).component
        found = _find_component(child, name)
        if found is not None:
            return found
    return None


def _mark(design, model_name: str) -> None:
    _set_attr(design, "owner", "fusion-cad-ai")
    _set_attr(design, "model", model_name)


def _attr(design, name: str) -> str:
    try:
        item = design.attributes.itemByName("fca", name)
    except Exception:
        return ""
    if item is None:
        return ""
    return str(item.value or "")


def _set_attr(design, name: str, value: str) -> None:
    try:
        existing = design.attributes.itemByName("fca", name)
        if existing is not None:
            existing.value = value
            return
        design.attributes.add("fca", name, value)
    except Exception as exc:
        log(f"attribute fca.{name}: {exc}", "WARN")
