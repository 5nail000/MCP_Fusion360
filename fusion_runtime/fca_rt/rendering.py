"""Local render as a job. The future stays on the session until job_status."""

from __future__ import annotations

import os
import uuid

from fca_rt.doc import require_fca
from fca_rt.errors import RtError


def start(path: str) -> dict:
    design = require_fca()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    try:
        manager = design.renderManager
        future = manager.startLocalRender(path)
    except Exception as exc:
        message = str(exc).splitlines()[-1][:300]
        if "license" in message.lower():
            raise RtError("LICENSE_BLOCKED", message) from exc
        raise RtError("FUSION_API_ERROR", message) from exc
    job_id = uuid.uuid4().hex[:12]
    from fca_rt import session

    session.STATE.jobs[job_id] = {"kind": "render", "future": future, "path": path}
    return {"job_id": job_id, "path": path}


def job_view(job: dict) -> dict:
    future = job.get("future")
    state = "running"
    if future is not None:
        for attr in ("isComplete", "isCompleted", "state"):
            if hasattr(future, attr):
                value = getattr(future, attr)
                state = "done" if value in (True, "done") else "running"
                break
    size = os.path.getsize(job["path"]) if job.get("path") and os.path.isfile(job["path"]) else 0
    if size > 32:
        state = "done"
    return {"kind": "render", "state": state, "path": job.get("path") or "", "bytes": int(size)}
