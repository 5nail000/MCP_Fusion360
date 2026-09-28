"""Operation router. Success prints one FCA>> line. Failure puts the same line in the exception."""

from __future__ import annotations

import json
import os
import traceback

from fca_rt.errors import RtError
from fca_rt.log import log

_MAX_INLINE = 100_000


def handle(op: str, params_json: str, request_id: str) -> None:
    from fca_rt import session

    log(f"op {op} id {request_id}")
    try:
        params = json.loads(params_json) if params_json else {}
        fn = OPS.get(op)
        if fn is None:
            raise RtError("FUSION_API_ERROR", f"Неизвестная операция {op}")
        result = fn(params)
        _emit(True, request_id, result if isinstance(result, dict) else {"value": result})
    except RtError as exc:
        session.STATE.last_error = exc.message
        _emit(False, request_id, {"code": exc.code, "message": exc.message, "hint": exc.hint})
    except Exception as exc:
        session.STATE.last_error = traceback.format_exc()[-2000:]
        message = str(exc).splitlines()[-1][:500] if str(exc) else exc.__class__.__name__
        code = "LICENSE_BLOCKED" if "license" in message.lower() else "FUSION_API_ERROR"
        _emit(False, request_id, {"code": code, "message": message, "hint": ""})


def _emit(ok: bool, request_id: str, result: dict) -> None:
    payload = {"v": 1, "id": request_id, "ok": ok, "result": result}
    text = "FCA>>" + json.dumps(payload, ensure_ascii=False) + "<<FCA"
    if len(text) > _MAX_INLINE:
        path = _spill(request_id, payload)
        text = "FCA>>" + json.dumps(
            {"v": 1, "id": request_id, "ok": ok, "result": {"spilled_path": path}},
            ensure_ascii=False,
        ) + "<<FCA"
    print(text)
    if not ok:
        raise RuntimeError(text)


def _spill(request_id: str, payload: dict) -> str:
    folder = os.path.join(os.path.dirname(__file__), "..", "..", ".runtime", "results")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{request_id}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return os.path.abspath(path)


def op_health(params: dict) -> dict:
    del params
    from fca_rt import session
    from fca_rt.doc import application

    app = application()
    import fca_rt

    document = app.activeDocument
    return {
        "envelope_v": 1,
        "fusion_build": str(app.version),
        "runtime_sha": str(getattr(fca_rt, "SOURCE_SHA", "")),
        "document_count": int(app.documents.count),
        "active_document": document.name if document is not None else "",
        "namespace_keys": sorted(key for key in session.STATE.namespace if not str(key).startswith("_")),
    }


def op_session_state(params: dict) -> dict:
    del params
    from fca_rt import session
    from fca_rt.doc import application

    app = application()
    document = app.activeDocument
    timeline_count = 0
    try:
        from fca_rt.doc import active_design

        _app, design = active_design()
        timeline_count = int(design.timeline.count)
    except Exception:
        timeline_count = 0
    return {
        "document": document.name if document is not None else "",
        "bodies": list(session.STATE.names),
        "timeline_count": timeline_count,
        "active_component": session.STATE.active_component,
        "namespace_keys": sorted(key for key in session.STATE.namespace if not str(key).startswith("_")),
    }


def op_new_design(params: dict) -> dict:
    from fca_rt.doc import new_design

    return new_design(str(params.get("name") or "model"), str(params.get("design_intent") or "hybrid"))


def op_reset(params: dict) -> dict:
    from fca_rt.doc import reset

    return reset(bool(params.get("confirm")))


def op_execute(params: dict) -> dict:
    from fca_rt import session
    from fca_rt.features import summaries
    from fca_rt.sandbox import check_ast

    code = str(params.get("code") or "")
    check_ast(code)
    namespace = session.STATE.namespace
    namespace.update(_helpers())
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exec(compile(code, "<fca_execute>", "exec"), namespace, namespace)  # noqa: S102
    session.STATE.script_log.append(code)
    result = namespace.get("result")
    try:
        json.dumps(result)
    except TypeError:
        result = str(result)
    return {"stdout": buffer.getvalue(), "result": result, "shapes": summaries()}


def op_execute_file(params: dict) -> dict:
    from fca_rt.runner import execute_model

    return execute_model(str(params["path"]), str(params.get("params_json") or ""), str(params.get("result_name") or ""))


def op_measure(params: dict) -> dict:
    from fca_rt.measure import measure

    return measure(str(params.get("object_name") or ""), float(params.get("density_g_cm3") or 0))


def op_validate(params: dict) -> dict:
    from fca_rt.validate import validate

    report = validate(str(params.get("object_name") or ""))
    report["deep"] = bool(params.get("deep"))
    return report


def op_locate_defects(params: dict) -> dict:
    del params
    from fca_rt.doc import require_fca
    from fca_rt.measure import timeline_report

    health = timeline_report(require_fca())
    return {"defects": health["errors"], "timeline_errors": health["errors"]}


def op_inspect(params: dict) -> dict:
    from fca_rt.inspect import inspect_part

    return inspect_part(str(params.get("object_name") or ""), str(params.get("expected_json") or ""))


def op_cross_sections(params: dict) -> dict:
    from fca_rt.inspect import cross_sections

    return cross_sections(str(params.get("axis") or "Z"), int(params.get("num_slices") or 10))


def op_compare(params: dict) -> dict:
    from fca_rt.inspect import compare

    return compare(str(params.get("kind") or "shape"), str(params.get("a") or ""), str(params.get("b") or ""))


def op_export_files(params: dict) -> dict:
    from fca_rt.export import export_files

    return export_files(dict(params.get("targets") or {}), str(params.get("object_name") or ""))


def op_import_file(params: dict) -> dict:
    from fca_rt.importer import import_file

    return import_file(str(params["path"]), str(params.get("name") or ""))


def op_params_get(params: dict) -> dict:
    del params
    from fca_rt import session
    from fca_rt.params import read_all

    return {"parameters": read_all(), "model": session.STATE.model_path}


def op_params_set(params: dict) -> dict:
    from fca_rt.params import set_values

    return {"updated": set_values(dict(params.get("values") or {}))}


def op_save_snapshot(params: dict) -> dict:
    from fca_rt.snapshots import capture

    return capture(str(params["name"]))


def op_restore_snapshot(params: dict) -> dict:
    from fca_rt.snapshots import restore

    return restore(str(params["name"]))


def op_last_error(params: dict) -> dict:
    del params
    from fca_rt import session
    from fca_rt.doc import application

    fusion_message = ""
    try:
        err = application().getLastError()
        fusion_message = str(err) if err else ""
    except Exception:
        fusion_message = ""
    return {"message": session.STATE.last_error, "fusion_message": fusion_message}


def op_script_log(params: dict) -> dict:
    del params
    from fca_rt import session

    return {"entries": list(session.STATE.script_log)}


def op_job_status(params: dict) -> dict:
    from fca_rt import session

    job = session.STATE.jobs.get(str(params.get("job_id") or ""))
    if job is None:
        raise RtError("FUSION_API_ERROR", "Задача не найдена")
    if job.get("kind") == "render":
        from fca_rt.rendering import job_view

        view = job_view(job)
    else:
        from fca_rt.cam import job_view

        view = job_view(job)
    view["job_id"] = str(params.get("job_id"))
    return view


def op_find_features(params: dict) -> dict:
    from fca_rt.recognize import find_features

    return find_features(str(params.get("family") or "holes"))


def op_resolve(params: dict) -> dict:
    from fca_rt.recognize import resolve

    return resolve(str(params.get("object_name") or ""), str(params.get("selector") or ""), str(params.get("label") or ""))


def op_interference(params: dict) -> dict:
    from fca_rt.assembly import interference

    return interference(str(params.get("objects") or ""), bool(params.get("include_coincident")))


def op_design_audit(params: dict) -> dict:
    from fca_rt.inspect import design_audit

    return design_audit(float(params.get("epsilon") or 0.1), int(params.get("max_params") or 8))


def op_render_custom(params: dict) -> dict:
    from fca_rt.render import save_view

    return save_view(
        str(params["path"]),
        int(params.get("width_px") or 1200),
        int(params.get("height_px") or 900),
        float(params.get("azimuth_deg") or 0),
        float(params.get("elevation_deg") or 0),
    )


def op_assembly_add(params: dict) -> dict:
    from fca_rt.assembly import add_component

    name = add_component(str(params["name"]))
    return {"component": name, "role": params.get("role") or "part"}


def op_joint_create(params: dict) -> dict:
    from fca_rt.assembly import create_joint

    return create_joint(str(params.get("kind") or "rigid"), str(params.get("a") or ""), str(params.get("b") or ""), params.get("limits") or {})


def op_motion_sweep(params: dict) -> dict:
    from fca_rt.assembly import motion_sweep

    return motion_sweep(
        int(params.get("joint") or 0),
        float(params.get("start_deg") or 0),
        float(params.get("stop_deg") or 90),
        int(params.get("steps") or 8),
    )


def op_cam_setup(params: dict) -> dict:
    from fca_rt.cam import setup

    return setup(str(params.get("template") or ""))


def op_cam_generate(params: dict) -> dict:
    del params
    from fca_rt.cam import generate

    return generate()


def op_cam_post(params: dict) -> dict:
    from fca_rt.cam import post

    return post(str(params["path"]))


def op_cam_recognize(params: dict) -> dict:
    del params
    from fca_rt.cam import recognize

    return recognize()


def op_sheet_rules(params: dict) -> dict:
    del params
    from fca_rt.sheet_metal import rules

    return rules()


def op_sheet_flat(params: dict) -> dict:
    from fca_rt.sheet_metal import flat_pattern

    return flat_pattern(str(params["path"]), float(params.get("thickness_mm") or 1))


def op_render_photo(params: dict) -> dict:
    from fca_rt.rendering import start

    return start(str(params["path"]))


def op_config_get(params: dict) -> dict:
    del params
    from fca_rt.configs import read

    return read()


def op_config_set(params: dict) -> dict:
    from fca_rt.configs import activate

    return activate(str(params.get("row") or ""))


def op_volumetric(params: dict) -> dict:
    from fca_rt.volume import apply

    return apply(float(params.get("cell_mm") or 4), float(params.get("radius_mm") or 0.6))


def op_drawing(params: dict) -> dict:
    from fca_rt.drawings import export_drawing

    return export_drawing(bool(params.get("confirm")), str(params.get("path") or ""))


def op_visual_analyses(params: dict) -> dict:
    del params
    import adsk.fusion

    from fca_rt.doc import require_fca

    design = require_fca()
    available = []
    for name in ("SectionAnalyses", "CurvatureCombAnalyses", "ZebraAnalyses", "DraftAnalyses", "AccessibilityAnalyses"):
        if hasattr(adsk.fusion, name) or hasattr(design, name[:1].lower() + name[1:]):
            available.append(name)
    return {
        "available": available,
        "created": "",
        "removed_after": True,
        "note": "Коллекции анализов есть в API билда. Постоянный анализ в документ не записывается.",
    }


def op_cloud_list(params: dict) -> dict:
    del params
    from fca_rt.cloud import cloud_list

    return cloud_list()


def op_cloud_open(params: dict) -> dict:
    from fca_rt.cloud import cloud_open

    return cloud_open(bool(params.get("confirm")), str(params.get("file_id") or ""))


def op_cloud_save(params: dict) -> dict:
    from fca_rt.cloud import cloud_save

    return cloud_save(bool(params.get("confirm")))


def op_thread_library(params: dict) -> dict:
    del params
    import adsk.fusion

    try:
        query = adsk.fusion.ThreadDataQuery.create()
        types = list(query.allThreadTypes)[:20] if hasattr(query, "allThreadTypes") else []
    except Exception as exc:
        return {"threads": [], "error": str(exc).splitlines()[-1][:200]}
    return {"threads": [{"designation": str(item)} for item in types]}


def _helpers() -> dict:
    from fca_rt.features import box, summaries

    def make_box_mm(x_mm: float, y_mm: float, z_mm: float, name: str = "box") -> str:
        return box(x_mm, y_mm, z_mm, center_mm=(x_mm / 2.0, y_mm / 2.0, z_mm / 2.0), name=name)

    def mm(value: float, unit: str | None = None) -> float:
        if unit is None or str(unit).strip() == "":
            raise RtError("UNIT_AMBIGUOUS", f"Размер {value!r} без единиц")
        factors = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "inch": 25.4}
        key = str(unit).strip().lower()
        if key not in factors:
            raise RtError("UNIT_AMBIGUOUS", f"Единицы {unit!r} не поддержаны")
        return float(value) * factors[key]

    def show(entity: str, name: str) -> str:
        from fca_rt.features import body_by_name, remember

        return remember(name, body_by_name(entity))

    def measure() -> dict:
        from fca_rt.measure import measure as _measure

        return _measure()

    def save_json(path: str, payload: dict) -> str:
        _guard_write(path)
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return path

    return {
        "make_box_mm": make_box_mm,
        "mm": mm,
        "show": show,
        "measure": measure,
        "find_features": lambda family="holes": op_find_features({"family": family}),
        "clearance": lambda a, b: op_interference({"objects": f"{a},{b}"}),
        "section": lambda: op_cross_sections({}),
        "save_json": save_json,
        "P": lambda *coords: tuple(float(item) for item in coords),
        "shapes": summaries,
    }


def _guard_write(path: str) -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    target = os.path.abspath(path)
    for name in ("exports", "renders", ".runtime"):
        folder = os.path.abspath(os.path.join(root, name))
        if target == folder or target.startswith(folder + os.sep):
            return
    raise RtError("SANDBOX_VIOLATION", "Запись разрешена только в exports, renders и .runtime")


OPS = {
    "health": op_health,
    "session_state": op_session_state,
    "new_design": op_new_design,
    "reset": op_reset,
    "execute": op_execute,
    "execute_file": op_execute_file,
    "measure": op_measure,
    "validate": op_validate,
    "locate_defects": op_locate_defects,
    "inspect": op_inspect,
    "cross_sections": op_cross_sections,
    "compare": op_compare,
    "export_files": op_export_files,
    "import_file": op_import_file,
    "params_get": op_params_get,
    "params_set": op_params_set,
    "save_snapshot": op_save_snapshot,
    "restore_snapshot": op_restore_snapshot,
    "last_error": op_last_error,
    "script_log": op_script_log,
    "job_status": op_job_status,
    "find_features": op_find_features,
    "resolve": op_resolve,
    "interference": op_interference,
    "design_audit": op_design_audit,
    "render_custom": op_render_custom,
    "assembly_add": op_assembly_add,
    "joint_create": op_joint_create,
    "motion_sweep": op_motion_sweep,
    "cam_setup": op_cam_setup,
    "cam_generate": op_cam_generate,
    "cam_post": op_cam_post,
    "cam_recognize": op_cam_recognize,
    "sheet_rules": op_sheet_rules,
    "sheet_flat": op_sheet_flat,
    "render_photo": op_render_photo,
    "config_get": op_config_get,
    "config_set": op_config_set,
    "volumetric": op_volumetric,
    "drawing": op_drawing,
    "visual_analyses": op_visual_analyses,
    "cloud_list": op_cloud_list,
    "cloud_open": op_cloud_open,
    "cloud_save": op_cloud_save,
    "thread_library": op_thread_library,
}
