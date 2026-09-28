from __future__ import annotations

import sys
from pathlib import Path

from fusion_runtime.fca_rt.loader import load_runtime


def test_reload_keeps_session_object(tmp_path: Path) -> None:
    package = tmp_path / "fca_rt"
    package.mkdir()
    (package / "__init__.py").write_text(
        "SOURCE_SHA = ''\n"
        "from fca_rt import session\n"
        "def handle(op, params_json, request_id):\n"
        "    return session.STATE.marker\n",
        encoding="utf-8",
    )
    (package / "session.py").write_text(
        "class State:\n"
        "    def __init__(self):\n"
        "        self.marker = 0\n"
        "STATE = State()\n",
        encoding="utf-8",
    )
    (package / "loader.py").write_text("", encoding="utf-8")
    for name in list(sys.modules):
        if name == "fca_rt" or name.startswith("fca_rt."):
            del sys.modules[name]
    first = load_runtime(str(package), "sha-a")
    first.session.STATE.marker = 7
    (package / "__init__.py").write_text(
        "SOURCE_SHA = ''\n"
        "from fca_rt import session\n"
        "def handle(op, params_json, request_id):\n"
        "    return session.STATE.marker\n",
        encoding="utf-8",
    )
    second = load_runtime(str(package), "sha-b")
    assert second.session.STATE.marker == 7
    assert second.SOURCE_SHA == "sha-b"
    for name in list(sys.modules):
        if name == "fca_rt" or name.startswith("fca_rt."):
            del sys.modules[name]
