"""One model file for the CLI and for MCP. adsk stays inside this runtime."""

from __future__ import annotations

import hashlib
import importlib.util
import json

from fca_rt.doc import require_fca
from fca_rt.errors import RtError
from fca_rt.features import box, chamfer_z, cut_box, cut_cylinder, cylinder, fillet_z, remember
from fca_rt.measure import measure
from fca_rt.params import sync_object, upsert_one
from fca_rt.snapshots import capture, restore
from fca_rt.validate import validate


class FusionContext:
    def params_from(self, obj):
        sync_object(obj)
        return obj

    def param(self, name: str, value: float, unit: str) -> None:
        upsert_one(name, value, unit)

    def component(self, name: str) -> str:
        from fca_rt.assembly import add_component

        return add_component(name)

    def box(self, size_x_mm, size_y_mm, size_z_mm, **kwargs) -> str:
        return box(size_x_mm, size_y_mm, size_z_mm, **kwargs)

    def cylinder(self, diameter_mm, height_mm, **kwargs) -> str:
        return cylinder(diameter_mm, height_mm, **kwargs)

    def cut_cylinder(self, target, diameter_mm, height_mm, center_mm=(0, 0, 0), **kwargs) -> str:
        return cut_cylinder(target, diameter_mm, height_mm, center_mm, **kwargs)

    def cut_box(self, target, size_mm, center_mm=(0, 0, 0), **kwargs) -> str:
        return cut_box(target, size_mm, center_mm)

    def fillet_z(self, target, which, radius_mm, **kwargs) -> str:
        return fillet_z(target, which, radius_mm, **kwargs)

    def chamfer_z(self, target, which, distance_mm, **kwargs) -> str:
        return chamfer_z(target, which, distance_mm, **kwargs)

    def show(self, target, name: str) -> str:
        body = _body(target)
        return remember(name, body)

    def joint(self, kind: str, a: str, b: str, limits=None, collision_at_deg=None) -> dict:
        from fca_rt.assembly import create_joint

        del collision_at_deg
        return create_joint(kind, a, b, limits or {})


def execute_model(path: str, params_json: str = "", result_name: str = "") -> dict:
    require_fca()
    capture("fca_auto_before_file")
    try:
        module = _load(path)
        params = _build_params(module, params_json)
        module.build(FusionContext(), params)
        if result_name:
            from fca_rt import session

            session.STATE.names.setdefault(result_name, {"token": "", "component": ""})
        report = validate()
        metrics = measure()
    except Exception:
        restore("fca_auto_before_file")
        raise
    from fca_rt import session

    session.STATE.model_path = path
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    fields = {}
    if params is not None:
        fields = {key: getattr(params, key) for key in getattr(params, "__dataclass_fields__", {})}
    return {
        "source_sha256": digest,
        "params": fields,
        "metrics": metrics,
        "timeline_health": report["timeline_health"],
    }


def _load(path: str):
    spec = importlib.util.spec_from_file_location("fca_user_model", path)
    if spec is None or spec.loader is None:
        raise RtError("FUSION_API_ERROR", "Файл модели не открывается")
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise RtError("FUSION_API_ERROR", "В модели нет функции build(ctx, params)")
    return module


def _build_params(module, params_json: str):
    from dataclasses import replace

    params_cls = None
    for value in vars(module).values():
        fields = getattr(value, "__dataclass_fields__", None)
        if fields and "unit" in fields:
            params_cls = value
            break
    if params_cls is None:
        raise RtError("FUSION_API_ERROR", "В модели нет dataclass с полем unit")
    params = params_cls()
    if not params_json:
        return params
    data = json.loads(params_json)
    updates = {}
    for key, value in data.items():
        if key not in params.__dataclass_fields__:
            continue
        if isinstance(value, dict):
            if "unit" not in value:
                raise RtError("UNIT_AMBIGUOUS", f"{key} без единиц")
            updates[key] = value["value"]
        else:
            updates[key] = value
    return replace(params, **updates) if updates else params


def _body(name: str):
    from fca_rt.features import body_by_name

    return body_by_name(name)
