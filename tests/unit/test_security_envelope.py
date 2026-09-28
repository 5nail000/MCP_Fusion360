from __future__ import annotations

import json

import pytest

from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.security import check_ast
from fusion_cad_ai.transport.envelope import build_script, extract_payload, payload_or_raise


def test_import_os_blocked() -> None:
    with pytest.raises(FcaError) as caught:
        check_ast("import os\n")
    assert caught.value.code == "SANDBOX_VIOLATION"


def test_open_call_blocked() -> None:
    with pytest.raises(FcaError) as caught:
        check_ast("open('x')\n")
    assert caught.value.code == "SANDBOX_VIOLATION"


def test_envelope_embeds_json_not_code() -> None:
    script = build_script("execute", {"code": "print(1)"}, "abc")
    assert "def run(_context: str):" in script
    assert "print(1)" not in script.split("json.loads", 1)[0]


def test_script_json_is_one_python_literal() -> None:
    script = build_script("health", {"name": "a\\b"}, "id1")
    line = next(item for item in script.splitlines() if "_raw = json.loads" in item).strip()
    namespace = {"json": json}
    exec(line, namespace)
    assert namespace["_raw"]["op"] == "health"
    assert namespace["_raw"]["params"]["name"] == "a\\b"
    assert "json.loads(json.loads" not in script


def test_payload_roundtrip() -> None:
    raw = 'prefix\nFCA>>{"v":1,"id":"abc","ok":true,"result":{"volume_mm3":1000}}<<FCA\n'
    assert payload_or_raise(raw)["volume_mm3"] == 1000


def test_error_payload_raises() -> None:
    body = json.dumps({"v": 1, "id": "abc", "ok": False, "result": {"code": "NOT_FCA_DOCUMENT", "message": "нет"}})
    with pytest.raises(FcaError) as caught:
        payload_or_raise(f"FCA>>{body}<<FCA")
    assert caught.value.code == "NOT_FCA_DOCUMENT"


def test_extract_from_traceback_wrapper() -> None:
    inner = json.dumps({"v": 1, "id": "z", "ok": True, "result": {"solid_count": 1}})
    wrapped = json.dumps({"error": f"Traceback\nRuntimeError: FCA>>{inner}<<FCA"})
    assert extract_payload(wrapped)["ok"] is True
