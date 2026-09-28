"""Script envelope sent through the official Fusion MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fusion_cad_ai.paths import FUSION_RUNTIME

ENVELOPE_VERSION = 1


def runtime_sha(root: Path | None = None) -> str:
    folder = root or FUSION_RUNTIME
    digest = hashlib.sha256()
    files = sorted(folder.rglob("*.py"))
    for path in files:
        digest.update(path.relative_to(folder).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_script(op: str, params: dict, request_id: str, *, root: Path | None = None, sha: str | None = None) -> str:
    """Return a Fusion script. User data is embedded as JSON, not interpolated as code."""
    runtime = root or FUSION_RUNTIME
    payload = {
        "v": ENVELOPE_VERSION,
        "op": op,
        "params": params,
        "id": request_id,
        "root": str(runtime),
        "sha": sha or runtime_sha(runtime),
    }
    quoted = json.dumps(json.dumps(payload, ensure_ascii=False), ensure_ascii=False)
    return (
        "def run(_context: str):\n"
        "    import importlib.util, json\n"
        "    from pathlib import Path\n"
        f"    _raw = json.loads({quoted})\n"
        "    _root = Path(_raw['root'])\n"
        "    _spec = importlib.util.spec_from_file_location('_fca_loader', str(_root / 'loader.py'))\n"
        "    if _spec is None or _spec.loader is None:\n"
        "        raise RuntimeError('FCA>>{\"v\":1,\"id\":\"boot\",\"ok\":false,\"result\":{\"code\":\"FUSION_API_ERROR\",\"message\":\"loader.py не найден\"}}<<FCA')\n"
        "    _loader = importlib.util.module_from_spec(_spec)\n"
        "    _spec.loader.exec_module(_loader)\n"
        "    _rt = _loader.load_runtime(str(_root), _raw['sha'])\n"
        "    _rt.handle(_raw['op'], json.dumps(_raw['params'], ensure_ascii=False), _raw['id'])\n"
    )


def extract_payload(text: str) -> dict:
    """Pull the last FCA>>json<<FCA object out of a tool reply or a traceback."""
    from fusion_cad_ai.config import ENVELOPE_MARK_CLOSE, ENVELOPE_MARK_OPEN
    from fusion_cad_ai.errors import FcaError

    raw = _unwrap_tool_text(text)
    open_at = raw.rfind(ENVELOPE_MARK_OPEN)
    if open_at < 0:
        raise FcaError("FUSION_API_ERROR", raw.strip()[:1500] or "пустой ответ Fusion", hint="Конверт FCA>> не найден")
    close_at = raw.find(ENVELOPE_MARK_CLOSE, open_at)
    if close_at < 0:
        raise FcaError("FUSION_API_ERROR", "Конверт оборван", hint=raw[open_at:open_at + 400])
    body = raw[open_at + len(ENVELOPE_MARK_OPEN) : close_at]
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise FcaError("FUSION_API_ERROR", f"Конверт не JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("v") != ENVELOPE_VERSION:
        raise FcaError("CONTRACT_CHANGED", "Версия конверта не совпала с v=1", hint=str(payload)[:400])
    return payload


def payload_or_raise(text: str) -> dict:
    from fusion_cad_ai.errors import FcaError

    payload = extract_payload(text)
    if payload.get("ok"):
        result = payload.get("result")
        return result if isinstance(result, dict) else {"value": result}
    err = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    raise FcaError(
        str(err.get("code") or "FUSION_API_ERROR"),
        str(err.get("message") or "операция не выполнена"),
        hint=str(err.get("hint") or ""),
        fusion_error=err.get("fusion_error") if isinstance(err.get("fusion_error"), dict) else None,
    )


def _unwrap_tool_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    try:
        outer = json.loads(stripped)
    except json.JSONDecodeError:
        return text
    if isinstance(outer, dict):
        for key in ("message", "error", "text"):
            value = outer.get(key)
            if isinstance(value, str) and value.strip():
                return value
        if "result" in outer and isinstance(outer["result"], str):
            return outer["result"]
    return text
