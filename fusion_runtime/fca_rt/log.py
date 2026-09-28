"""Runtime log. The only stdout line is the envelope, written by dispatch."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _log_file() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "fca_rt.log"


def log(message: str, level: str = "INFO") -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] [{level}] {message}"
    path = _log_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    try:
        import adsk.core

        app = adsk.core.Application.get()
        if app is not None:
            app.log(line)
    except Exception:
        pass
