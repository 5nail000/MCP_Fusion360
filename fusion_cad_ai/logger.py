"""Logger. MCP stdio owns stdout, so every line goes to stderr and starts with local time."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


def log(message: str, level: str = "INFO") -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] [{level}] {message}"
    print(line, file=sys.stderr, flush=True)


def log_path(path: Path, message: str, level: str = "INFO") -> None:
    log(message, level)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] [{level}] {message}\n")
