"""Parameter expressions, timeline marker and suppress flags."""

from __future__ import annotations

import json
import os

from fca_rt.doc import active_design, require_fca
from fca_rt.errors import RtError
from fca_rt.log import log
from fca_rt.measure import measure
from fca_rt.params import read_all


def capture(name: str) -> dict:
    design = require_fca()
    suppressed = []
    for index in range(design.timeline.count):
        item = design.timeline.item(index)
        if bool(getattr(item, "isSuppressed", False)):
            suppressed.append(index)
    try:
        metrics = measure()
    except RtError:
        metrics = {}
    blob = {
        "name": name,
        "parameters": read_all(),
        "marker": int(design.timeline.markerPosition),
        "timeline_count": int(design.timeline.count),
        "suppressed": suppressed,
        "metrics": metrics,
    }
    from fca_rt import session

    blob["names"] = {key: dict(value) for key, value in session.STATE.names.items()}
    blob["active_component"] = session.STATE.active_component
    session.STATE.snapshots[name] = blob
    folder = os.path.join(os.path.dirname(__file__), "..", "..", ".runtime", "snapshots")
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, f"{_safe(name)}.json"), "w", encoding="utf-8") as handle:
            json.dump(blob, handle)
    except OSError as exc:
        log(f"snapshot file: {exc}", "WARN")
    return {"name": name, "parameters": len(blob["parameters"]), "marker": blob["marker"]}


def restore(name: str) -> dict:
    design = require_fca()
    from fca_rt import session

    blob = session.STATE.snapshots.get(name)
    if blob is None:
        raise RtError("FUSION_API_ERROR", f"Снимок {name} не найден")
    for param_name, spec in blob.get("parameters", {}).items():
        item = _find(design, param_name)
        if item is not None:
            item.expression = spec.get("expression") or item.expression
    target_count = int(blob.get("timeline_count") or 0)
    guard = 0
    while design.timeline.count > target_count and guard < 800:
        guard += 1
        item = design.timeline.item(design.timeline.count - 1)
        entity = item.entity
        if entity is None or not hasattr(entity, "deleteMe"):
            break
        entity.deleteMe()
    try:
        design.timeline.markerPosition = int(blob.get("marker") or design.timeline.count)
    except Exception as exc:
        log(f"marker restore: {exc}", "WARN")
    session.STATE.names.clear()
    session.STATE.names.update({key: dict(value) for key, value in (blob.get("names") or {}).items()})
    session.STATE.active_component = str(blob.get("active_component") or "")
    log(f"restore snapshot {name}")
    return {"name": name, "restored": True}


def _find(design, name: str):
    for index in range(design.userParameters.count):
        item = design.userParameters.item(index)
        if item.name == name:
            return item
    return None


def _safe(name: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in name)[:80]
