"""In-memory Fusion used by tests. Volumes of boxes and through-holes are exact; fillets are approximate."""

from __future__ import annotations

import hashlib
import io
import json
import math
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.security import check_ast


@dataclass
class Primitive:
    kind: str
    axis: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    radius_mm: float = 0.0
    negative: bool = False


@dataclass
class Body:
    name: str
    component: str
    volume_mm3: float
    min_mm: list[float]
    max_mm: list[float]
    faces: int = 6
    primitives: list[Primitive] = field(default_factory=list)
    token: str = ""


class FakeTransport:
    def __init__(self) -> None:
        self.doc_name = ""
        self.owner = ""
        self.bodies: dict[str, Body] = {}
        self.params: dict[str, dict] = {}
        self.namespace: dict = {}
        self.script_log: list[str] = []
        self.snapshots: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.last_error = ""
        self.timeline: list[dict] = []
        self.joints: list[dict] = []
        self.components: list[str] = []
        self.active_component = "root"
        self.model_path = ""
        self.dialog_open = False
        self._seq = 0

    def call(
        self,
        op: str,
        params: dict | None = None,
        *,
        timeout_s: float | None = None,
        read_only: bool = False,
    ) -> dict:
        del timeout_s, read_only
        params = dict(params or {})
        if self.dialog_open and op not in {"health", "session_state", "last_error"}:
            raise FcaError("COMMAND_DIALOG_OPEN", "В Fusion открыт диалог команды", hint="Закройте диалог.")
        method = getattr(self, f"op_{op}", None)
        if method is None:
            raise FcaError("FUSION_API_ERROR", f"Неизвестная операция {op}")
        return method(params)

    def screenshot(self, direction: str, width_px: int, height_px: int) -> dict:
        return {"direction": direction, "width_px": width_px, "height_px": height_px, "png_base64": ""}

    def op_health(self, params: dict) -> dict:
        del params
        return {
            "envelope_v": 1,
            "fusion_build": "fake",
            "runtime_sha": "fake",
            "document_count": 1 if self.doc_name else 0,
            "license": {"licenseTypeSummary": "Fake", "isTrial": False},
            "active_document": self.doc_name,
        }

    def op_session_state(self, params: dict) -> dict:
        del params
        return {
            "document": self.doc_name,
            "bodies": list(self.bodies),
            "parameters": list(self.params),
            "timeline_count": len(self.timeline),
            "active_component": self.active_component,
            "namespace_keys": sorted(k for k in self.namespace if not k.startswith("_")),
        }

    def op_new_design(self, params: dict) -> dict:
        name = str(params.get("name") or "model")
        self.doc_name = f"FCA_{name}"
        self.owner = "fusion-cad-ai"
        self.bodies.clear()
        self.timeline.clear()
        self.joints.clear()
        self.components = ["root"]
        self.active_component = "root"
        self.params.clear()
        return {"name": self.doc_name, "reused": False, "design_type": "parametric", "design_intent": params.get("design_intent") or "hybrid", "units": "mm"}

    def op_reset(self, params: dict) -> dict:
        self._require_fca()
        if not params.get("confirm"):
            raise FcaError("CONFIRMATION_REQUIRED", "reset требует confirm=true")
        self.bodies.clear()
        self.timeline.clear()
        self.joints.clear()
        self.namespace.clear()
        return {"reset": True, "document": self.doc_name}

    def op_execute(self, params: dict) -> dict:
        self._require_fca()
        code = str(params.get("code") or "")
        check_ast(code)
        ns = self.namespace
        ns.update(self._helpers())
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                exec(compile(code, "<fca_execute>", "exec"), ns, ns)  # noqa: S102
        except FcaError:
            raise
        except Exception as exc:
            self.last_error = str(exc)
            raise FcaError("FUSION_API_ERROR", str(exc)) from exc
        self.script_log.append(code)
        result = ns.get("result")
        return {"stdout": buffer.getvalue(), "result": result if _jsonable(result) else str(result), "shapes": self._shapes()}

    def op_execute_file(self, params: dict) -> dict:
        self._require_fca()
        path = Path(str(params["path"]))
        before = self._snapshot_blob("fca_auto_before_file")
        self.snapshots["fca_auto_before_file"] = before
        try:
            metrics = self._run_model(path, str(params.get("params_json") or ""))
        except Exception:
            self._restore_blob(before)
            raise
        return metrics

    def op_measure(self, params: dict) -> dict:
        self._require_fca()
        name = str(params.get("object_name") or "")
        bodies = [self.bodies[name]] if name else list(self.bodies.values())
        if not bodies:
            raise FcaError("VALIDATION_FAILED", "В документе нет тел")
        volume = sum(item.volume_mm3 for item in bodies)
        box = _union_bbox(bodies)
        density = float(params.get("density_g_cm3") or 0)
        mass = volume / 1000.0 * density if density else 0.0
        return {
            "volume_mm3": volume,
            "bbox_mm": [box[1][i] - box[0][i] for i in range(3)],
            "bbox_min_mm": box[0],
            "bbox_max_mm": box[1],
            "solid_count": len(bodies),
            "face_count": sum(item.faces for item in bodies),
            "center_of_mass_mm": [(box[0][i] + box[1][i]) / 2 for i in range(3)],
            "mass_g": mass,
            "area_mm2": 0.0,
        }

    def op_validate(self, params: dict) -> dict:
        self._require_fca()
        measured = self.op_measure({"object_name": params.get("object_name") or ""}) if self.bodies else None
        ok = bool(measured and measured["volume_mm3"] > 0 and measured["solid_count"] > 0)
        errors = [] if ok else ["нет твёрдого тела с объёмом > 0"]
        return {
            "ok": ok,
            "timeline_health": "healthy",
            "solid_count": 0 if measured is None else measured["solid_count"],
            "volume_mm3": 0 if measured is None else measured["volume_mm3"],
            "errors": errors,
            "warnings": [],
            "deep": bool(params.get("deep")),
        }

    def op_locate_defects(self, params: dict) -> dict:
        del params
        self._require_fca()
        return {"defects": [], "timeline_errors": []}

    def op_inspect(self, params: dict) -> dict:
        self._require_fca()
        measured = self.op_measure({"object_name": params.get("object_name") or ""})
        expected_raw = params.get("expected_json") or ""
        report = {"ok": True, "measured": measured, "mismatches": []}
        if expected_raw:
            expected = json.loads(expected_raw) if isinstance(expected_raw, str) else expected_raw
            mismatches = []
            if "bbox_mm" in expected:
                for got, want in zip(measured["bbox_mm"], expected["bbox_mm"], strict=False):
                    if abs(got - float(want)) > 0.02:
                        mismatches.append({"field": "bbox_mm", "got": got, "want": want})
            if "solids" in expected and measured["solid_count"] != int(expected["solids"]):
                mismatches.append({"field": "solids", "got": measured["solid_count"], "want": expected["solids"]})
            report["ok"] = not mismatches
            report["mismatches"] = mismatches
        return report

    def op_cross_sections(self, params: dict) -> dict:
        self._require_fca()
        count = int(params.get("num_slices") or 10)
        measured = self.op_measure({})
        return {"axis": params.get("axis") or "Z", "slices": count, "bbox_mm": measured["bbox_mm"]}

    def op_compare(self, params: dict) -> dict:
        self._require_fca()
        kind = params.get("kind") or "shape"
        if kind == "fit":
            return self.op_interference({"objects": params.get("a") or "", "include_coincident": False})
        if kind == "snapshot":
            name = str(params.get("b") or "")
            snap = self.snapshots.get(name)
            if snap is None:
                raise FcaError("FUSION_API_ERROR", f"Снимок {name} не найден")
            return {"kind": kind, "matches": True, "snapshot": name}
        return {"kind": kind, "volume_mm3": self.op_measure({})["volume_mm3"]}

    def op_export_files(self, params: dict) -> dict:
        self._require_fca()
        written = []
        for fmt, raw_path in (params.get("targets") or {}).items():
            path = Path(str(raw_path))
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_placeholder(path, fmt, self.bodies)
            written.append({"format": fmt, "path": str(path), "bytes": path.stat().st_size})
        return {"files": written}

    def op_import_file(self, params: dict) -> dict:
        self._require_fca()
        path = Path(str(params["path"]))
        if not path.is_file():
            raise FcaError("FUSION_API_ERROR", f"Файл не найден: {path.name}")
        name = str(params.get("name") or path.stem)
        self._add_box(name, 10, 10, 10, (5, 5, 5), self.active_component)
        return {"name": name, "imported": path.suffix.lower()}

    def op_params_get(self, params: dict) -> dict:
        del params
        self._require_fca()
        return {"parameters": self.params, "model": self.model_path}

    def op_params_set(self, params: dict) -> dict:
        self._require_fca()
        values = params.get("values") or {}
        for name, spec in values.items():
            if not isinstance(spec, dict) or "unit" not in spec:
                raise FcaError("UNIT_AMBIGUOUS", f"Параметр {name} без единиц")
            self.params[name] = {"value": spec["value"], "unit": spec["unit"], "expression": f"{spec['value']} {spec['unit']}"}
        return {"updated": list(values)}

    def op_save_snapshot(self, params: dict) -> dict:
        self._require_fca()
        name = str(params["name"])
        self.snapshots[name] = self._snapshot_blob(name)
        return {"name": name, "bodies": len(self.bodies)}

    def op_restore_snapshot(self, params: dict) -> dict:
        self._require_fca()
        name = str(params["name"])
        blob = self.snapshots.get(name)
        if blob is None:
            raise FcaError("FUSION_API_ERROR", f"Снимок {name} не найден")
        self._restore_blob(blob)
        return {"name": name, "restored": True}

    def op_last_error(self, params: dict) -> dict:
        del params
        return {"message": self.last_error}

    def op_script_log(self, params: dict) -> dict:
        del params
        return {"entries": list(self.script_log)}

    def op_job_status(self, params: dict) -> dict:
        job = self.jobs.get(str(params.get("job_id") or ""))
        if job is None:
            raise FcaError("FUSION_API_ERROR", "Задача не найдена")
        job["state"] = "done"
        return job

    def op_find_features(self, params: dict) -> dict:
        self._require_fca()
        family = params.get("family") or "holes"
        holes = []
        for body in self.bodies.values():
            for prim in body.primitives:
                if prim.negative and prim.kind == "cylinder":
                    holes.append({"diameter_mm": prim.radius_mm * 2, "center_mm": list(prim.center), "axis": prim.axis, "body": body.name})
        patterns = _bolt_circles(holes)
        return {"family": family, "holes": holes, "patterns": patterns}

    def op_resolve(self, params: dict) -> dict:
        self._require_fca()
        name = str(params.get("object_name") or "")
        body = self.bodies.get(name)
        if body is None:
            raise FcaError("FUSION_API_ERROR", f"Объект {name} не найден")
        label = str(params.get("label") or "resolved")
        return {"name": name, "label": label, "entity_token": body.token, "selector": params.get("selector") or ""}

    def op_interference(self, params: dict) -> dict:
        self._require_fca()
        names = [item.strip() for item in str(params.get("objects") or "").split(",") if item.strip()]
        chosen = [self.bodies[name] for name in names] if names else list(self.bodies.values())
        hits = []
        for index, left in enumerate(chosen):
            for right in chosen[index + 1 :]:
                volume = _overlap_volume(left, right)
                if volume > 1e-6:
                    hits.append({"a": left.name, "b": right.name, "volume_mm3": volume})
        return {"interference": bool(hits), "pairs": hits}

    def op_design_audit(self, params: dict) -> dict:
        self._require_fca()
        epsilon = float(params.get("epsilon") or 0.1)
        checked = []
        for name, spec in list(self.params.items()):
            if spec.get("unit") != "mm":
                continue
            original = float(spec["value"])
            if original - epsilon <= 0:
                checked.append({"name": name, "skipped": "значение стало бы неположительным"})
                continue
            checked.append({"name": name, "brittle": False, "epsilon_mm": epsilon})
        return {"ok": True, "parameters": checked[: int(params.get("max_params") or 8)]}

    def op_render_custom(self, params: dict) -> dict:
        self._require_fca()
        path = Path(str(params["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_tiny_png())
        return {"path": str(path), "width_px": int(params.get("width_px") or 320), "height_px": int(params.get("height_px") or 240)}

    def op_assembly_add(self, params: dict) -> dict:
        self._require_fca()
        name = str(params["name"])
        self.components.append(name)
        self.active_component = name
        return {"component": name, "role": params.get("role") or "part"}

    def op_joint_create(self, params: dict) -> dict:
        self._require_fca()
        joint = {
            "kind": params.get("kind") or "rigid",
            "a": params.get("a"),
            "b": params.get("b"),
            "limits": params.get("limits") or {},
            "angle_deg": 0.0,
            "collision_at_deg": params.get("collision_at_deg"),
        }
        self.joints.append(joint)
        return {"index": len(self.joints) - 1, "kind": joint["kind"]}

    def op_motion_sweep(self, params: dict) -> dict:
        self._require_fca()
        index = int(params.get("joint") or 0)
        if index >= len(self.joints):
            raise FcaError("FUSION_API_ERROR", "Шарнир не найден")
        start = float(params.get("start_deg") or 0)
        stop = float(params.get("stop_deg") or 90)
        steps = int(params.get("steps") or 8)
        collision_at = self.joints[index].get("collision_at_deg")
        hit = None
        if collision_at is not None:
            for step in range(steps + 1):
                angle = start + (stop - start) * step / max(steps, 1)
                if angle >= float(collision_at):
                    hit = angle
                    break
        self.joints[index]["angle_deg"] = start
        return {"collision": hit is not None, "angle_deg": hit, "restored": True}

    def op_cam_setup(self, params: dict) -> dict:
        self._require_fca()
        return {"setup": "fake-setup", "pu_warning": _PU_CAM, "template": params.get("template") or ""}

    def op_cam_generate(self, params: dict) -> dict:
        self._require_fca()
        job_id = f"job-{len(self.jobs) + 1}"
        self.jobs[job_id] = {"job_id": job_id, "kind": "cam", "state": "running", "warning": _PU_CAM}
        del params
        return {"job_id": job_id, "warning": _PU_CAM}

    def op_cam_post(self, params: dict) -> dict:
        self._require_fca()
        path = Path(str(params["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("(fake nc)\n", encoding="utf-8")
        return {"path": str(path), "warning": _PU_CAM, "bytes": path.stat().st_size}

    def op_cam_recognize(self, params: dict) -> dict:
        del params
        self._require_fca()
        features = self.op_find_features({"family": "holes"})
        return {"holes": features["holes"], "pockets": [], "warning": _PU_CAM}

    def op_sheet_rules(self, params: dict) -> dict:
        del params
        self._require_fca()
        return {"rules": ["fake-default"], "thickness_mm": 1.0}

    def op_sheet_flat(self, params: dict) -> dict:
        self._require_fca()
        path = Path(str(params["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("0\nSECTION\n", encoding="utf-8")
        return {"path": str(path), "bytes": path.stat().st_size}

    def op_render_photo(self, params: dict) -> dict:
        self._require_fca()
        job_id = f"job-{len(self.jobs) + 1}"
        path = str(params.get("path") or "")
        self.jobs[job_id] = {"job_id": job_id, "kind": "render", "state": "done", "path": path}
        return {"job_id": job_id, "path": path}

    def op_config_get(self, params: dict) -> dict:
        del params
        self._require_fca()
        return {"configured": False, "rows": [], "hint": "Таблица конфигураций ещё не создана"}

    def op_config_set(self, params: dict) -> dict:
        self._require_fca()
        return {"row": params.get("row") or "", "active": True}

    def op_volumetric(self, params: dict) -> dict:
        self._require_fca()
        return {"created": True, "cell_mm": float(params.get("cell_mm") or 4), "kind": "beam-lattice", "preview_api": True}

    def op_drawing(self, params: dict) -> dict:
        self._require_fca()
        if not params.get("confirm"):
            raise FcaError(
                "CONFIRMATION_REQUIRED",
                "Чертёж Fusion требует сохранённый документ",
                hint="Повторите с confirm=true или используйте fallback SVG.",
            )
        return {"fusion_drawing": False, "fallback": "svg", "reason": "fake transport"}

    def op_visual_analyses(self, params: dict) -> dict:
        del params
        self._require_fca()
        return {"available": ["section", "draft", "curvature", "zebra", "accessibility"], "created": "section", "removed_after": True}

    def op_cloud_list(self, params: dict) -> dict:
        del params
        return {"projects": [], "note": "fake transport не ходит в облако Autodesk"}

    def op_cloud_open(self, params: dict) -> dict:
        if not params.get("confirm"):
            raise FcaError("CONFIRMATION_REQUIRED", "Открытие облачного документа требует confirm=true")
        return {"opened": False, "reason": "fake"}

    def op_cloud_save(self, params: dict) -> dict:
        self._require_fca()
        if not params.get("confirm"):
            raise FcaError("CONFIRMATION_REQUIRED", "Сохранение в облако требует confirm=true")
        return {"saved": False, "project": "MCP_Fusion360_Sandbox", "reason": "fake transport не пишет в облако"}

    def op_thread_library(self, params: dict) -> dict:
        del params
        return {"threads": [{"designation": "M6x1", "source": "fake"}]}

    def op_search_library(self, params: dict) -> dict:
        return {"query": params.get("query") or "", "hits": []}

    def _require_fca(self) -> None:
        if not (self.doc_name.startswith("FCA_") or self.owner == "fusion-cad-ai"):
            raise FcaError("NOT_FCA_DOCUMENT", f"Активный документ {self.doc_name or '(нет)'} не принадлежит fusion-cad-ai")

    def _helpers(self) -> dict:
        ctx = _FakeContext(self)

        def make_box_mm(x_mm: float, y_mm: float, z_mm: float, name: str = "box") -> str:
            body = ctx.box(x_mm, y_mm, z_mm, center_mm=(x_mm / 2, y_mm / 2, z_mm / 2), name=name)
            ctx.show(body, name)
            return name

        def mm(value: float, unit: str = "mm") -> float:
            from fusion_cad_ai.units import require_explicit_unit

            return require_explicit_unit(value, unit)

        def show(entity: str, name: str) -> str:
            return ctx.show(entity, name)

        def measure() -> dict:
            return self.op_measure({})

        def save_json(path: str, payload: dict) -> str:
            target = Path(path)
            if not allowed_write(target):
                raise FcaError("SANDBOX_VIOLATION", "save_json пишет только в exports, renders и .runtime")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload), encoding="utf-8")
            return str(target)

        return {
            "make_box_mm": make_box_mm,
            "mm": mm,
            "show": show,
            "measure": measure,
            "find_features": lambda family="holes": self.op_find_features({"family": family}),
            "clearance": lambda a, b: self.op_interference({"objects": f"{a},{b}"}),
            "section": lambda: self.op_cross_sections({}),
            "save_json": save_json,
            "P": lambda *coords: tuple(coords),
        }

    def _shapes(self) -> list[dict]:
        return [
            {"name": body.name, "volume_mm3": body.volume_mm3, "faces": body.faces}
            for body in self.bodies.values()
        ]

    def _add_box(self, name: str, sx: float, sy: float, sz: float, center: tuple[float, float, float], component: str) -> Body:
        half = (sx / 2, sy / 2, sz / 2)
        body = Body(
            name=name,
            component=component,
            volume_mm3=sx * sy * sz,
            min_mm=[center[i] - half[i] for i in range(3)],
            max_mm=[center[i] + half[i] for i in range(3)],
            faces=6,
            token=f"fake-{name}-{self._seq}",
        )
        self._seq += 1
        body.primitives.append(Primitive("box", "z", center, (sx, sy, sz)))
        self.bodies[name] = body
        self.timeline.append({"op": "box", "name": name})
        return body

    def _run_model(self, path: Path, params_json: str) -> dict:
        import importlib.util

        spec = importlib.util.spec_from_file_location(f"fca_model_{path.stem}", path)
        if spec is None or spec.loader is None:
            raise FcaError("FUSION_API_ERROR", f"Не удалось загрузить {path.name}")
        module = importlib.util.module_from_spec(spec)
        import sys

        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        params_cls = _params_class(module)
        params = params_cls()
        if params_json:
            params = _apply_param_json(params, params_json)
        ctx = _FakeContext(self)
        module.build(ctx, params)
        self.model_path = str(path)
        measured = self.op_measure({})
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "source_sha256": digest,
            "params": {key: getattr(params, key) for key in params.__dataclass_fields__},
            "metrics": measured,
            "timeline_health": "healthy",
        }

    def _snapshot_blob(self, name: str) -> dict:
        return {
            "name": name,
            "params": json.loads(json.dumps(self.params)),
            "bodies": json.loads(json.dumps(self.bodies, default=_body_default)),
            "timeline": list(self.timeline),
        }

    def _restore_blob(self, blob: dict) -> None:
        self.params = blob["params"]
        self.timeline = list(blob["timeline"])
        self.bodies = {}
        for name, raw in blob["bodies"].items():
            self.bodies[name] = Body(
                name=raw["name"],
                component=raw["component"],
                volume_mm3=raw["volume_mm3"],
                min_mm=raw["min_mm"],
                max_mm=raw["max_mm"],
                faces=raw["faces"],
                token=raw["token"],
            )


class _FakeContext:
    def __init__(self, transport: FakeTransport) -> None:
        self.transport = transport

    def params_from(self, obj: object) -> object:
        fields = getattr(obj, "__dataclass_fields__", {})
        for name in fields:
            value = getattr(obj, name)
            if name.endswith("_mm"):
                self.transport.params[name] = {"value": float(value), "unit": "mm", "expression": f"{value} mm"}
            elif name.endswith("_deg"):
                self.transport.params[name] = {"value": float(value), "unit": "deg", "expression": f"{value} deg"}
            elif name == "unit":
                continue
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                self.transport.params[name] = {"value": value, "unit": "", "expression": str(value)}
        return obj

    def param(self, name: str, value: float, unit: str) -> None:
        self.transport.params[name] = {"value": value, "unit": unit, "expression": f"{value} {unit}".strip()}

    def component(self, name: str) -> str:
        if name not in self.transport.components:
            self.transport.components.append(name)
        self.transport.active_component = name
        return name

    def box(self, size_x_mm: float, size_y_mm: float, size_z_mm: float, *, center_mm=(0, 0, 0), join: str | None = None, name: str | None = None, **_extra) -> str:
        title = name or f"box-{len(self.transport.bodies) + 1}"
        if join and join in self.transport.bodies:
            return self._join_box(join, size_x_mm, size_y_mm, size_z_mm, center_mm)
        body = self.transport._add_box(title, size_x_mm, size_y_mm, size_z_mm, center_mm, self.transport.active_component)
        return body.name

    def cylinder(self, diameter_mm: float, height_mm: float, *, center_mm=(0, 0, 0), axis: str = "z", join: str | None = None, name: str | None = None, **_extra) -> str:
        radius = diameter_mm / 2
        volume = math.pi * radius * radius * height_mm
        title = name or f"cyl-{len(self.transport.bodies) + 1}"
        if join and join in self.transport.bodies:
            host = self.transport.bodies[join]
            host.volume_mm3 += volume
            host.primitives.append(Primitive("cylinder", axis, tuple(center_mm), (diameter_mm, diameter_mm, height_mm), radius))
            _expand_bbox(host, center_mm, axis, diameter_mm, height_mm)
            host.faces += 3
            return host.name
        half = _cylinder_half(axis, diameter_mm, height_mm)
        body = Body(
            name=title,
            component=self.transport.active_component,
            volume_mm3=volume,
            min_mm=[center_mm[i] - half[i] for i in range(3)],
            max_mm=[center_mm[i] + half[i] for i in range(3)],
            faces=3,
            token=f"fake-{title}",
        )
        body.primitives.append(Primitive("cylinder", axis, tuple(center_mm), (diameter_mm, diameter_mm, height_mm), radius))
        self.transport.bodies[title] = body
        self.transport.timeline.append({"op": "cylinder", "name": title})
        return title

    def cut_cylinder(self, target: str, diameter_mm: float, height_mm: float, center_mm=(0, 0, 0), *, axis: str = "z", **_extra) -> str:
        body = self.transport.bodies[target]
        radius = diameter_mm / 2
        length = _overlap_length(body, center_mm, axis, height_mm)
        removed = math.pi * radius * radius * length
        body.volume_mm3 = max(0.0, body.volume_mm3 - removed)
        body.primitives.append(Primitive("cylinder", axis, tuple(center_mm), (diameter_mm, diameter_mm, height_mm), radius, True))
        body.faces += 1
        self.transport.timeline.append({"op": "cut", "name": target})
        return target

    def cut_box(self, target: str, size_mm: tuple[float, float, float], center_mm=(0, 0, 0), **_extra) -> str:
        body = self.transport.bodies[target]
        removed = _box_overlap_volume(body, size_mm, center_mm)
        body.volume_mm3 = max(0.0, body.volume_mm3 - removed)
        body.primitives.append(Primitive("box", "z", tuple(center_mm), tuple(size_mm), negative=True))
        self.transport.timeline.append({"op": "cut_box", "name": target})
        return target

    def fillet_z(self, target: str, which: str, radius_mm: float, **_extra) -> str:
        body = self.transport.bodies[target]
        body.volume_mm3 = max(0.0, body.volume_mm3 - abs(radius_mm) * 0.01)
        self.transport.timeline.append({"op": "fillet", "which": which, "name": target})
        return target

    def chamfer_z(self, target: str, which: str, distance_mm: float, **_extra) -> str:
        body = self.transport.bodies[target]
        body.volume_mm3 = max(0.0, body.volume_mm3 - abs(distance_mm) * 0.01)
        self.transport.timeline.append({"op": "chamfer", "which": which, "name": target})
        return target

    def show(self, target: str, name: str) -> str:
        body = self.transport.bodies.pop(target)
        body.name = name
        self.transport.bodies[name] = body
        return name

    def joint(self, kind: str, a: str, b: str, limits: dict | None = None, collision_at_deg: float | None = None) -> dict:
        return self.transport.op_joint_create({"kind": kind, "a": a, "b": b, "limits": limits or {}, "collision_at_deg": collision_at_deg})

    def _join_box(self, target: str, sx: float, sy: float, sz: float, center: tuple[float, float, float]) -> str:
        host = self.transport.bodies[target]
        alone = sx * sy * sz
        overlap = _box_overlap_volume(host, (sx, sy, sz), center)
        host.volume_mm3 += alone - overlap
        host.primitives.append(Primitive("box", "z", center, (sx, sy, sz)))
        for index in range(3):
            host.min_mm[index] = min(host.min_mm[index], center[index] - (sx, sy, sz)[index] / 2)
            host.max_mm[index] = max(host.max_mm[index], center[index] + (sx, sy, sz)[index] / 2)
        return host.name


_PU_CAM = "Personal Use / Trial: без быстрых перемещений и без автосмены инструмента. FFF — отдельное исследование, пост в exports/nc не является программой для Bambu."


def _jsonable(value: object) -> bool:
    try:
        json.dumps(value)
    except TypeError:
        return False
    return True


def _union_bbox(bodies: list[Body]) -> tuple[list[float], list[float]]:
    low = [min(body.min_mm[i] for body in bodies) for i in range(3)]
    high = [max(body.max_mm[i] for body in bodies) for i in range(3)]
    return low, high


def _cylinder_half(axis: str, diameter: float, height: float) -> tuple[float, float, float]:
    radius = diameter / 2
    if axis == "x":
        return (height / 2, radius, radius)
    if axis == "y":
        return (radius, height / 2, radius)
    return (radius, radius, height / 2)


def _expand_bbox(body: Body, center: tuple[float, float, float], axis: str, diameter: float, height: float) -> None:
    half = _cylinder_half(axis, diameter, height)
    for index in range(3):
        body.min_mm[index] = min(body.min_mm[index], center[index] - half[index])
        body.max_mm[index] = max(body.max_mm[index], center[index] + half[index])


def _overlap_length(body: Body, center: tuple[float, float, float], axis: str, height: float) -> float:
    index = {"x": 0, "y": 1, "z": 2}[axis]
    start = center[index] - height / 2
    end = center[index] + height / 2
    low = max(start, body.min_mm[index])
    high = min(end, body.max_mm[index])
    return max(0.0, high - low)


def _box_overlap_volume(body: Body, size: tuple[float, float, float], center: tuple[float, float, float]) -> float:
    volume = 1.0
    for index in range(3):
        start = center[index] - size[index] / 2
        end = center[index] + size[index] / 2
        low = max(start, body.min_mm[index])
        high = min(end, body.max_mm[index])
        span = high - low
        if span <= 0:
            return 0.0
        volume *= span
    return volume


def _overlap_volume(left: Body, right: Body) -> float:
    pins = [prim for prim in left.primitives + right.primitives if prim.kind == "cylinder" and not prim.negative]
    holes = [prim for prim in left.primitives + right.primitives if prim.kind == "cylinder" and prim.negative]
    coaxial = False
    for pin in pins:
        for hole in holes:
            if pin.axis != hole.axis:
                continue
            axes = [index for index in range(3) if "xyz"[index] != pin.axis]
            if any(abs(pin.center[index] - hole.center[index]) > 0.2 for index in axes):
                continue
            coaxial = True
            if pin.radius_mm > hole.radius_mm + 1e-6:
                return math.pi * (pin.radius_mm**2 - hole.radius_mm**2)
    if coaxial:
        return 0.0
    volume = 1.0
    for index in range(3):
        low = max(left.min_mm[index], right.min_mm[index])
        high = min(left.max_mm[index], right.max_mm[index])
        if high - low <= 0.05:
            return 0.0
        volume *= high - low
    return volume if pins and not holes else 0.0


def _bolt_circles(holes: list[dict]) -> list[dict]:
    if len(holes) < 3:
        return []
    cx = sum(item["center_mm"][0] for item in holes) / len(holes)
    cy = sum(item["center_mm"][1] for item in holes) / len(holes)
    radii = [math.hypot(item["center_mm"][0] - cx, item["center_mm"][1] - cy) for item in holes]
    if max(radii) - min(radii) > 0.2:
        return []
    return [{"type": "bolt_circle", "holes": len(holes), "diameter_mm": (sum(radii) / len(radii)) * 2}]


def _params_class(module: object):
    for value in vars(module).values():
        fields = getattr(value, "__dataclass_fields__", None)
        if fields and "unit" in fields:
            return value
    raise FcaError("FUSION_API_ERROR", "В модели нет dataclass параметров")


def _apply_param_json(params: object, raw: str) -> object:
    from dataclasses import replace

    data = json.loads(raw)
    updates = {}
    fields = getattr(params, "__dataclass_fields__", {})
    for key, value in data.items():
        if key not in fields:
            continue
        if isinstance(value, dict):
            if "unit" not in value:
                raise FcaError("UNIT_AMBIGUOUS", f"{key} без единиц")
            updates[key] = value["value"]
        else:
            updates[key] = value
    return replace(params, **updates)


def _body_default(value: object):
    if isinstance(value, Body):
        return {
            "name": value.name,
            "component": value.component,
            "volume_mm3": value.volume_mm3,
            "min_mm": value.min_mm,
            "max_mm": value.max_mm,
            "faces": value.faces,
            "token": value.token,
        }
    if isinstance(value, Primitive):
        return value.__dict__
    raise TypeError(type(value))


def _write_placeholder(path: Path, fmt: str, bodies: dict[str, Body]) -> None:
    names = " ".join(bodies) or "empty"
    if fmt == "step":
        path.write_text(
            "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('fusion-cad-ai'),'2;1');\nENDSEC;\n"
            f"DATA;\n/* names {names} */\nENDSEC;\nEND-ISO-10303-21;\n",
            encoding="utf-8",
        )
        return
    if fmt == "stl":
        path.write_text(
            "solid fca\n"
            "  facet normal 0 0 1\n"
            "    outer loop\n"
            "      vertex 0 0 0\n"
            "      vertex 1 0 0\n"
            "      vertex 0 1 0\n"
            "    endloop\n"
            "  endfacet\n"
            "endsolid fca\n",
            encoding="utf-8",
        )
        return
    if fmt in {"3mf", "f3d"}:
        import zipfile

        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types></Types>")
            archive.writestr("3D/3dmodel.model", f"<model><name>{names}</name></model>")
        return
    path.write_text(f"fca {fmt} {names}\n", encoding="utf-8")


def _tiny_png() -> bytes:
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
        "0000000c4944415408d763f8ffff3f0005fe02fe0000000049454e44ae426082"
    )


def allowed_write(path: Path) -> bool:
    from fusion_cad_ai.paths import ROOT

    resolved = path.resolve()
    for folder in (ROOT / "exports", ROOT / "renders", ROOT / ".runtime"):
        try:
            resolved.relative_to(folder.resolve())
            return True
        except ValueError:
            continue
    return False
