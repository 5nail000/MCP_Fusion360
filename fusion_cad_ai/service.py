"""Tool implementations. Fusion work goes through FusionTransport."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

from fusion_cad_ai import __version__
from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.errors_catalog import repair_hints as catalog_hints
from fusion_cad_ai.logger import log
from fusion_cad_ai.paths import DOCS, EXPORT_DIRS, MODELS, RENDERS, RUNTIME, VERIFY_DIR, ensure_output_dirs
from fusion_cad_ai.printers import PRINTERS, get_printer
from fusion_cad_ai.transport import get_transport
from fusion_cad_ai.transport.envelope import runtime_sha
from fusion_cad_ai.units import require_explicit_unit
from fusion_cad_ai.verify.files import verify_files
from fusion_cad_ai.verify.printability import analyze

_DIRECTIONS = {
    "iso": "iso-top-right",
    "front": "front",
    "back": "back",
    "top": "top",
    "bottom": "bottom",
    "left": "left",
    "right": "right",
}


def health_check() -> dict:
    transport = get_transport()
    try:
        report = transport.call("health", {}, read_only=True)
    except FcaError:
        raise
    except OSError as exc:
        raise FcaError("FUSION_NOT_REACHABLE", str(exc)) from exc
    if hasattr(transport, "read"):
        try:
            report["license"] = transport.read({"queryType": "licensing"})
        except FcaError as exc:
            report["license_error"] = exc.to_dict()
    report["package"] = __version__
    report["runtime_sha_server"] = runtime_sha()
    _write_current_versions(report)
    lock = DOCS / "versions.lock"
    if lock.is_file():
        locked = lock.read_text(encoding="utf-8")
        build = str(report.get("fusion_build") or "")
        if build and build not in locked and build != "fake":
            report["version_warning"] = "Билд Fusion отличается от docs/versions.lock. Обновите lock через collect_versions."
    return report


def version() -> dict:
    return {"package": __version__, "envelope_v": 1, "name": "fusion-cad-ai"}


def workflow_hints() -> dict:
    return {
        "cycle": "BUILD → VALIDATE → INSPECT → PREVIEW → provisional EXPORT → VERIFY → exports/",
        "units": "Длины *_mm, углы *_deg. Размер без единиц отклоняется.",
        "documents": "Рабочий документ называется FCA_<модель>. Чужие документы не закрываются и не сохраняются.",
        "step": "STEP — мастер. STL и 3MF — производные для печати.",
    }


def session_state() -> dict:
    return get_transport().call("session_state", {}, read_only=True)


def new_design(name: str, design_intent: str = "hybrid") -> dict:
    if not name:
        raise FcaError("FUSION_API_ERROR", "Нужно имя модели")
    return get_transport().call("new_design", {"name": name, "design_intent": design_intent})


def reset(confirm: bool) -> dict:
    return get_transport().call("reset", {"confirm": confirm})


def job_status(job_id: str) -> dict:
    return get_transport().call("job_status", {"job_id": job_id}, read_only=True)


def execute(code: str, timeout_s: float = 120) -> dict:
    return get_transport().call("execute", {"code": code}, timeout_s=timeout_s, read_only=False)


def execute_file(path: str, params_json: str = "", result_name: str = "", snapshot: str = "") -> dict:
    del snapshot
    source = _model_path(path)
    return get_transport().call(
        "execute_file",
        {"path": str(source), "params_json": params_json, "result_name": result_name},
    )


def script() -> dict:
    return get_transport().call("script_log", {}, read_only=True)


def last_error() -> dict:
    return get_transport().call("last_error", {}, read_only=True)


def repair_hints(error_text: str, goal: str = "") -> dict:
    return catalog_hints(error_text, goal)


def params_get(model: str = "") -> dict:
    live = get_transport().call("params_get", {"model": model}, read_only=True)
    live["diff"] = _param_diff(model, live.get("parameters") or {})
    return live


def params_set(values: dict) -> dict:
    cleaned = {}
    for name, spec in values.items():
        if hasattr(spec, "model_dump"):
            spec = spec.model_dump()
        if not isinstance(spec, dict) or "unit" not in spec or "value" not in spec:
            raise FcaError("UNIT_AMBIGUOUS", f"{name} задаётся как {{value, unit}}")
        unit = str(spec["unit"])
        if unit in {"deg", "rad"}:
            from fusion_cad_ai.units import require_angle_deg

            number = require_angle_deg(spec["value"], unit)
            cleaned[name] = {"value": number, "unit": "deg"}
        else:
            cleaned[name] = {"value": require_explicit_unit(spec["value"], unit), "unit": "mm"}
    return get_transport().call("params_set", {"values": cleaned})


def save_snapshot(name: str) -> dict:
    return get_transport().call("save_snapshot", {"name": name})


def restore_snapshot(name: str) -> dict:
    return get_transport().call("restore_snapshot", {"name": name})


def measure(object_name: str = "", material: str = "", density_g_cm3: float = 0) -> dict:
    del material
    return get_transport().call(
        "measure",
        {"object_name": object_name, "density_g_cm3": density_g_cm3},
        read_only=True,
    )


def validate(object_name: str = "", deep: bool = False) -> dict:
    report = get_transport().call("validate", {"object_name": object_name, "deep": deep}, read_only=True)
    if deep:
        step = VERIFY_DIR / "deep.step"
        try:
            export("deep", "step", object_name, force=True)
            from fusion_cad_ai.verify.occ import deep_check

            report["brep"] = deep_check(step)
            if report["brep"].get("warning"):
                report.setdefault("warnings", []).append(report["brep"]["warning"])
        except FcaError as exc:
            report.setdefault("warnings", []).append(exc.message)
    return report


def locate_defects() -> dict:
    return get_transport().call("locate_defects", {}, read_only=True)


def inspect_part(object_name: str = "", expected_json: str = "") -> dict:
    return get_transport().call(
        "inspect",
        {"object_name": object_name, "expected_json": expected_json},
        read_only=True,
    )


def cross_sections(axis: str = "Z", num_slices: int = 10) -> dict:
    return get_transport().call("cross_sections", {"axis": axis, "num_slices": num_slices}, read_only=True)


def compare(a: str, b: str = "", kind: str = "shape") -> dict:
    return get_transport().call("compare", {"a": a, "b": b, "kind": kind}, read_only=True)


def design_audit(epsilon: float = 0.1, max_params: int = 8) -> dict:
    return get_transport().call("design_audit", {"epsilon": epsilon, "max_params": max_params})


def analyze_printability(printer: str = "bambu_a1_mini", support_angle_deg: float = 45, nozzle_mm: float = 0.4) -> dict:
    measured = measure()
    stl = VERIFY_DIR / "printability.stl"
    try:
        export("printability", "stl", "", force=True)
    except FcaError as exc:
        log(f"printability export: {exc.message}", "WARN")
        stl = None
    return analyze(measured["bbox_mm"], printer, support_angle_deg, nozzle_mm, stl if stl and stl.is_file() else None)


def find_features(family: str) -> dict:
    return get_transport().call("find_features", {"family": family}, read_only=True)


def resolve(object_name: str, selector: str, label: str = "") -> dict:
    return get_transport().call("resolve", {"object_name": object_name, "selector": selector, "label": label})


def render_view(
    direction: str = "iso",
    objects: str = "",
    width_px: int = 1200,
    height_px: int = 900,
    azimuth_deg: float = 0,
    elevation_deg: float = 0,
    clip_axis: str = "",
    clip_at_mm: float | None = None,
    highlights: list | None = None,
    colors: dict | None = None,
    save_to: str = "",
) -> dict:
    del objects, highlights, colors
    ensure_output_dirs()
    path = Path(save_to) if save_to else RENDERS / "view.png"
    if not path.is_absolute():
        path = RENDERS / path
    path.parent.mkdir(parents=True, exist_ok=True)
    custom = bool(azimuth_deg or elevation_deg or clip_axis or clip_at_mm is not None)
    if custom:
        shot = get_transport().call(
            "render_custom",
            {
                "path": str(path),
                "width_px": width_px,
                "height_px": height_px,
                "azimuth_deg": azimuth_deg,
                "elevation_deg": elevation_deg,
                "clip_axis": clip_axis,
                "clip_at_mm": clip_at_mm,
            },
            read_only=True,
        )
    else:
        official = _DIRECTIONS.get(direction, direction)
        raw = get_transport().screenshot(official, width_px, height_px)
        if not _write_shot(raw.get("raw") or "", path):
            shot = get_transport().call(
                "render_custom",
                {"path": str(path), "width_px": width_px, "height_px": height_px},
                read_only=True,
            )
        else:
            shot = {"path": str(path), "source": "official-screenshot"}
    encoded = base64.b64encode(path.read_bytes()).decode("ascii") if path.is_file() else ""
    shot["png_path"] = str(path)
    shot["png_base64"] = encoded
    return shot


def export(filename: str, formats: str = "step", object_name: str = "", force: bool = False) -> dict:
    ensure_output_dirs()
    chosen = [item.strip().lower() for item in formats.split(",") if item.strip()]
    targets = {fmt: VERIFY_DIR / f"{filename}.{fmt}" for fmt in chosen}
    written = get_transport().call("export_files", {"targets": {fmt: str(path) for fmt, path in targets.items()}, "object_name": object_name})
    checked = verify_files(targets)
    final = []
    if checked["ok"] or force:
        for fmt, src in targets.items():
            if not src.is_file():
                continue
            dest = EXPORT_DIRS[fmt] / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            final.append({"format": fmt, "path": str(dest), "bytes": dest.stat().st_size})
    elif not force:
        raise FcaError("VALIDATION_FAILED", "Проверочный экспорт не прошёл", hint=json.dumps(checked, ensure_ascii=False)[:500])
    return {"files": final, "provisional": written, "verify": checked, "forced": force}


def import_cad_file(path: str, name: str = "") -> dict:
    source = Path(path)
    if not source.is_file():
        raise FcaError("FUSION_API_ERROR", f"Файл не найден: {source.name}")
    return get_transport().call("import_file", {"path": str(source.resolve()), "name": name})


def assembly_add_part(name: str, source: str, placement_mm: list | None = None, rotation_deg: list | None = None, role: str = "part") -> dict:
    del placement_mm, rotation_deg
    created = get_transport().call("assembly_add", {"name": name, "role": role})
    if source:
        model = _model_path(source)
        get_transport().call("execute_file", {"path": str(model), "result_name": name})
    return created


def joint_create(kind: str, a: str, b: str, limits: dict | None = None) -> dict:
    return get_transport().call("joint_create", {"kind": kind, "a": a, "b": b, "limits": limits or {}})


def interference(objects: str = "", include_coincident: bool = False) -> dict:
    return get_transport().call(
        "interference",
        {"objects": objects, "include_coincident": include_coincident},
        read_only=True,
    )


def motion_sweep(joint: int, start: float, stop: float, steps: int = 24) -> dict:
    return get_transport().call(
        "motion_sweep",
        {"joint": joint, "start_deg": start, "stop_deg": stop, "steps": steps},
    )


def search_library(query: str) -> dict:
    hits = []
    needle = query.lower()
    for path in (MODELS / "lib").glob("*.py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if needle in path.stem.lower() or needle in text.lower():
            hits.append({"name": path.stem, "path": str(path)})
    threads = get_transport().call("thread_library", {}, read_only=True)
    for item in threads.get("threads") or []:
        label = str(item.get("designation") or "")
        if not needle or needle in label.lower():
            hits.append({"name": label, "source": "ThreadDataQuery"})
    return {"query": query, "hits": hits}


def load_part(name: str, params_json: str = "") -> dict:
    path = MODELS / "lib" / f"{name}.py"
    if not path.is_file():
        raise FcaError("FUSION_API_ERROR", f"В библиотеке нет {name}")
    return execute_file(str(path), params_json, name)


def prepare_drawing(title: str, image_path: str = "", width_px: int = 1600, height_px: int = 1100) -> dict:
    from PIL import Image, ImageDraw

    ensure_output_dirs()
    sheet = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((40, 40, width_px - 40, height_px - 40), outline="black", width=3)
    draw.text((60, 60), title or "fusion-cad-ai", fill="black")
    if image_path and Path(image_path).is_file():
        photo = Image.open(image_path).convert("RGB")
        photo.thumbnail((width_px - 200, height_px - 250))
        sheet.paste(photo, (80, 140))
    dest = RENDERS / "drawing_sheet.png"
    sheet.save(dest)
    return {"path": str(dest), "width_px": width_px, "height_px": height_px}


def crop_drawing(path: str, margin_px: int = 8) -> dict:
    from PIL import Image, ImageChops

    image = Image.open(path).convert("RGB")
    background = Image.new("RGB", image.size, "white")
    diff = ImageChops.difference(image, background)
    box = diff.getbbox()
    if box is None:
        raise FcaError("FUSION_API_ERROR", "На листе нет содержимого")
    left = max(box[0] - margin_px, 0)
    top = max(box[1] - margin_px, 0)
    right = min(box[2] + margin_px, image.width)
    bottom = min(box[3] + margin_px, image.height)
    cropped = image.crop((left, top, right, bottom))
    dest = Path(path).with_name(Path(path).stem + "_crop.png")
    cropped.save(dest)
    return {"path": str(dest), "width_px": cropped.width, "height_px": cropped.height}


def cam_setup(template: str = "") -> dict:
    return get_transport().call("cam_setup", {"template": template})


def cam_generate() -> dict:
    return get_transport().call("cam_generate", {}, timeout_s=300)


def cam_post(filename: str = "program.nc") -> dict:
    ensure_output_dirs()
    path = EXPORT_DIRS["nc"] / filename
    return get_transport().call("cam_post", {"path": str(path)})


def cam_recognize() -> dict:
    return get_transport().call("cam_recognize", {}, read_only=True)


def sheet_metal_rules() -> dict:
    return get_transport().call("sheet_rules", {}, read_only=True)


def sheet_metal_flat_pattern(filename: str = "flat.dxf", thickness_mm: float = 1.0) -> dict:
    ensure_output_dirs()
    path = EXPORT_DIRS["dxf"] / filename
    return get_transport().call("sheet_flat", {"path": str(path), "thickness_mm": thickness_mm})


def render_photo(filename: str = "photo.png") -> dict:
    ensure_output_dirs()
    path = RENDERS / filename
    return get_transport().call("render_photo", {"path": str(path)}, timeout_s=300)


def volumetric_apply(cell_mm: float = 4.0, radius_mm: float = 0.6) -> dict:
    return get_transport().call("volumetric", {"cell_mm": cell_mm, "radius_mm": radius_mm})


def config_get() -> dict:
    return get_transport().call("config_get", {}, read_only=True)


def config_set(row: str) -> dict:
    return get_transport().call("config_set", {"row": row})


def drawing_export(confirm: bool = False, filename: str = "drawing.pdf") -> dict:
    try:
        return get_transport().call("drawing", {"confirm": confirm, "path": str(EXPORT_DIRS["pdf"] / filename)})
    except FcaError as exc:
        if exc.code not in {"CONFIRMATION_REQUIRED", "LICENSE_BLOCKED"}:
            raise
        svg = _fallback_drawing(filename)
        return {"fusion_drawing": False, "fallback": svg, "error": exc.to_dict()}


def visual_note() -> dict:
    return get_transport().call("visual_analyses", {}, read_only=True)


def cloud_list() -> dict:
    return get_transport().call("cloud_list", {}, read_only=True)


def cloud_open(confirm: bool, file_id: str = "") -> dict:
    return get_transport().call("cloud_open", {"confirm": confirm, "file_id": file_id})


def cloud_save(confirm: bool) -> dict:
    return get_transport().call("cloud_save", {"confirm": confirm})


def verify_spec(spec_json: str) -> dict:
    spec = json.loads(spec_json)
    measured = measure(spec.get("object_name") or "")
    mismatches = []
    for key in ("volume_mm3", "bbox_mm"):
        if key not in spec:
            continue
        got = measured[key]
        want = spec[key]
        if isinstance(want, list):
            if any(abs(float(a) - float(b)) > 0.02 for a, b in zip(got, want, strict=False)):
                mismatches.append({"field": key, "got": got, "want": want})
        elif abs(float(got) - float(want)) / max(abs(float(want)), 1.0) > 0.002:
            mismatches.append({"field": key, "got": got, "want": want})
    return {"ok": not mismatches, "mismatches": mismatches}


def suggest_spec(object_name: str = "") -> dict:
    measured = measure(object_name)
    return {"volume_mm3": measured["volume_mm3"], "bbox_mm": measured["bbox_mm"], "object_name": object_name}


def printers() -> dict:
    return {
        name: {"bed_mm": [item.bed_x_mm, item.bed_y_mm, item.bed_z_mm], "nozzle_mm": item.nozzle_mm}
        for name, item in PRINTERS.items()
    }


def _model_path(path: str) -> Path:
    source = Path(path)
    if not source.is_file():
        candidate = MODELS / "parts" / f"{path}.py"
        if not candidate.is_file():
            candidate = MODELS / "assemblies" / f"{path}.py"
        if not candidate.is_file():
            candidate = MODELS / "lib" / f"{path}.py"
        source = candidate
    resolved = source.resolve()
    root = MODELS.resolve()
    if root not in resolved.parents and resolved.parent != root:
        raise FcaError("SANDBOX_VIOLATION", "execute_file читает только файлы из models/")
    return resolved


def _param_diff(model: str, live: dict) -> list[dict]:
    if not model:
        return []
    try:
        path = _model_path(model)
    except FcaError:
        return []
    import importlib.util

    spec = importlib.util.spec_from_file_location("diff_model", path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    params_cls = next(
        (value for value in vars(module).values() if getattr(value, "__dataclass_fields__", None) and "unit" in value.__dataclass_fields__),
        None,
    )
    if params_cls is None:
        return []
    defaults = params_cls()
    diff = []
    for name in defaults.__dataclass_fields__:
        if name == "unit":
            continue
        expected = getattr(defaults, name)
        current = live.get(name, {}).get("value")
        if current is None:
            continue
        try:
            if abs(float(current) - float(expected)) > 1e-6:
                diff.append({"name": name, "model": expected, "fusion": current})
        except (TypeError, ValueError):
            continue
    return diff


def _write_current_versions(report: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    payload = {
        "package": __version__,
        "fusion_build": report.get("fusion_build"),
        "runtime_sha": report.get("runtime_sha"),
    }
    (RUNTIME / "versions.current.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_shot(raw: str, path: Path) -> bool:
    data = ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if isinstance(payload, dict):
        data = str(payload.get("data") or "")
        if not data and isinstance(payload.get("message"), str):
            try:
                inner = json.loads(payload["message"])
                data = str(inner.get("data") or "")
            except json.JSONDecodeError:
                data = ""
    if not data:
        return False
    path.write_bytes(base64.b64decode(data))
    return path.stat().st_size > 32


def _fallback_drawing(filename: str) -> str:
    measured = {}
    try:
        measured = measure()
    except FcaError:
        measured = {}
    dest = EXPORT_DIRS["dxf"] / (Path(filename).stem + ".svg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    bbox = measured.get("bbox_mm") or [60, 40, 6]
    dest.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='300'>"
        f"<text x='20' y='30'>fusion-cad-ai fallback {bbox[0]} x {bbox[1]} x {bbox[2]} mm</text>"
        "<rect x='40' y='50' width='300' height='180' fill='none' stroke='black'/>"
        "</svg>\n",
        encoding="utf-8",
    )
    return str(dest)


def known_printer(name: str) -> dict:
    item = get_printer(name)
    return {"name": item.name, "bed_mm": [item.bed_x_mm, item.bed_y_mm, item.bed_z_mm], "nozzle_mm": item.nozzle_mm}
