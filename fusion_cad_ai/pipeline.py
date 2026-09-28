"""BUILD → VALIDATE → INSPECT → PREVIEW → provisional export → VERIFY → exports/."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from fusion_cad_ai.logger import log
from fusion_cad_ai.paths import EXPORT_DIRS, MODELS, RENDERS, VERIFY_DIR, ensure_output_dirs
from fusion_cad_ai.transport import get_transport
from fusion_cad_ai.verify.files import verify_files


@dataclass
class PipelineResult:
    name: str
    ok: bool
    stages: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def find_model(name: str) -> Path:
    for folder in (MODELS / "parts", MODELS / "assemblies", MODELS / "lib"):
        path = folder / f"{name}.py"
        if path.is_file():
            return path
    raise FileNotFoundError(f"Модель {name} не найдена в models/")


def run_pipeline(name: str, formats: list[str] | None = None, transport=None) -> PipelineResult:
    ensure_output_dirs()
    formats = formats or ["step", "stl", "3mf", "f3d"]
    path = find_model(name)
    cad = transport or get_transport()
    result = PipelineResult(name=name, ok=False)
    log(f"BUILD {name}")
    result.stages["build"] = cad.call("new_design", {"name": name, "design_intent": "hybrid"})
    result.stages["execute_file"] = cad.call("execute_file", {"path": str(path)})
    log("VALIDATE")
    result.stages["validate"] = cad.call("validate", {"deep": False}, read_only=True)
    expected = _expected(path)
    log("INSPECT")
    result.stages["inspect"] = cad.call(
        "inspect",
        {"expected_json": json.dumps(expected) if expected else ""},
        read_only=True,
    )
    preview = RENDERS / f"{name}_preview.png"
    log("PREVIEW")
    try:
        result.stages["preview"] = _preview(cad, preview)
    except Exception as exc:
        result.warnings.append(f"preview: {exc}")
        result.stages["preview"] = {"error": str(exc)}
    log("EXPORT provisional")
    targets = {fmt: VERIFY_DIR / f"{name}.{fmt}" for fmt in formats}
    result.stages["provisional"] = cad.call(
        "export_files",
        {"targets": {fmt: str(item) for fmt, item in targets.items()}},
    )
    verified = verify_files(targets)
    result.stages["verify"] = verified
    result.warnings.extend(verified.get("warnings") or [])
    if result.stages["validate"].get("ok") and verified.get("ok") and result.stages["inspect"].get("ok", True):
        for fmt, src in targets.items():
            dest = EXPORT_DIRS[fmt] / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            result.files.append(str(dest))
        result.ok = True
        log(f"VERIFY PASS {name}")
    else:
        log(f"VERIFY FAIL {name}", "ERROR")
    return result


def _expected(path: Path) -> dict:
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"expected_{path.stem}", path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return dict(getattr(module, "EXPECTED", {}) or {})


def _preview(cad, path: Path) -> dict:
    if hasattr(cad, "screenshot"):
        shot = cad.screenshot("iso-top-right", 1200, 900)
        raw = shot.get("raw") or ""
        saved = _save_png_from_text(raw, path)
        if saved:
            return {"path": str(path), "source": "official-screenshot"}
    return cad.call(
        "render_custom",
        {"path": str(path), "width_px": 1200, "height_px": 900},
        read_only=True,
    )


def _save_png_from_text(raw: str, path: Path) -> bool:
    import base64
    import json

    data = ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("base64") or ""
        if not data and isinstance(payload.get("message"), str):
            try:
                inner = json.loads(payload["message"])
                data = inner.get("data") or ""
            except json.JSONDecodeError:
                data = ""
    if not data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(data))
    return path.stat().st_size > 32
