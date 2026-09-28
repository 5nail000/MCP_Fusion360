"""CAM setups, toolpath jobs and NC post. Personal Use has no rapids and no tool changer."""

from __future__ import annotations

import os
import uuid

PU_WARNING = (
    "Лицензия может ограничить CAM: без быстрых перемещений и без автосмены инструмента. "
    "FFF для Bambu в этом билде не постпроцессится: аддитивный сетап есть в API, "
    "но машинный пост Bambu зависит от локальной библиотеки постов и здесь не подменяется."
)


def setup(template: str = "") -> dict:
    cam = _cam()
    created = ""
    if template:
        if not os.path.isfile(template):
            from fca_rt.errors import RtError

            raise RtError("FUSION_API_ERROR", "Файл шаблона CAM не найден")
        try:
            import adsk.cam

            item = adsk.cam.CAMTemplate.createFromFile(template)
            item.apply(cam)
            created = os.path.basename(template)
        except Exception as exc:
            from fca_rt.errors import RtError

            raise RtError("FUSION_API_ERROR", str(exc).splitlines()[-1][:300]) from exc
    return {"setups": int(cam.setups.count) if hasattr(cam, "setups") else 0, "template": created, "warning": PU_WARNING}


def generate() -> dict:
    cam = _cam()
    try:
        future = cam.generateAllToolpaths(False)
    except Exception as exc:
        from fca_rt.errors import RtError

        message = str(exc).splitlines()[-1][:300]
        if "license" in message.lower():
            raise RtError("LICENSE_BLOCKED", message) from exc
        raise RtError("FUSION_API_ERROR", message, hint="Нужен сетап. Пустой дизайн не считает траектории.") from exc
    job_id = uuid.uuid4().hex[:12]
    from fca_rt import session

    session.STATE.jobs[job_id] = {"kind": "cam", "future": future, "warning": PU_WARNING}
    return {"job_id": job_id, "warning": PU_WARNING}


def post(path: str) -> dict:
    cam = _cam()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    try:
        import adsk.cam

        options = adsk.cam.NCProgramPostProcessOptions.create() if hasattr(adsk.cam, "NCProgramPostProcessOptions") else None
        if options is None or not hasattr(cam, "ncPrograms") or cam.ncPrograms.count == 0:
            from fca_rt.errors import RtError

            raise RtError(
                "FUSION_API_ERROR",
                "Нет NC-программы для поста",
                hint="Сначала cam_setup из шаблона и cam_generate. Пост пишет только в exports/nc.",
            )
        program = cam.ncPrograms.item(0)
        ok = bool(program.postProcess(options))
    except Exception as exc:
        from fca_rt.errors import RtError

        if isinstance(exc, RtError):
            raise
        raise RtError("FUSION_API_ERROR", str(exc).splitlines()[-1][:300]) from exc
    size = os.path.getsize(path) if os.path.isfile(path) else 0
    return {"ok": ok, "path": path, "bytes": int(size), "warning": PU_WARNING}


def recognize() -> dict:
    _cam()
    from fca_rt.recognize import find_features

    features = find_features("holes")
    pockets = []
    try:
        import adsk.cam

        pockets.append({"api": hasattr(adsk.cam, "RecognizedPocket")})
    except Exception as exc:
        pockets.append({"error": str(exc).splitlines()[-1][:180]})
    return {"holes": features["holes"], "pockets": pockets, "warning": PU_WARNING}


def job_view(job: dict) -> dict:
    future = job.get("future")
    state = "done"
    if future is not None:
        for attr in ("isGenerationCompleted", "isCompleted", "state"):
            if hasattr(future, attr):
                value = getattr(future, attr)
                state = "done" if value in (True, "done", 0) else "running"
                break
    return {"kind": "cam", "state": state, "warning": job.get("warning") or PU_WARNING}


def _cam():
    import adsk.cam

    from fca_rt.doc import application, require_fca

    require_fca()
    app = application()
    document = app.activeDocument
    for index in range(document.products.count):
        cam = adsk.cam.CAM.cast(document.products.item(index))
        if cam is not None:
            return cam
    from fca_rt.errors import RtError

    raise RtError("FUSION_API_ERROR", "В документе нет CAM-продукта", hint="Откройте рабочее пространство Manufacture один раз вручную.")
