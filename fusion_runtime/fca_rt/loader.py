"""Load fca_rt without touching sys.path. A changed source hash reloads the code and keeps the session."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_runtime(root: str, sha: str):
    root_path = Path(root)
    existing = sys.modules.get("fca_rt")
    saved = None
    if existing is not None and getattr(existing, "SOURCE_SHA", None) == sha:
        return existing
    if existing is not None:
        session = getattr(existing, "session", None)
        saved = getattr(session, "STATE", None)
        for name in list(sys.modules):
            if name == "fca_rt" or name.startswith("fca_rt."):
                del sys.modules[name]
    init = root_path / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "fca_rt",
        str(init),
        submodule_search_locations=[str(root_path)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("fca_rt/__init__.py не найден")
    module = importlib.util.module_from_spec(spec)
    sys.modules["fca_rt"] = module
    spec.loader.exec_module(module)
    module.SOURCE_SHA = sha
    session_mod = importlib.import_module("fca_rt.session")
    module.session = session_mod
    if saved is not None:
        session_mod.STATE = saved
    return module
