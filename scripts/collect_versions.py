"""Write docs/versions.lock. User profile paths become environment-variable prefixes."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fusion_cad_ai.logger import log


def _run(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return f"unavailable ({exc.__class__.__name__})"
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0] if text else "unavailable"


def _sanitize(text: str) -> str:
    replacements = {
        os.environ.get("USERPROFILE", ""): "%USERPROFILE%",
        os.environ.get("LOCALAPPDATA", ""): "%LOCALAPPDATA%",
        os.environ.get("APPDATA", ""): "%APPDATA%",
    }
    for raw, token in replacements.items():
        if raw:
            text = text.replace(raw, token)
    return text


def _fusion_exe() -> str:
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Autodesk" / "webdeploy" / "production"
    if not root.is_dir():
        return "not-found"
    found = sorted(root.glob("*/Fusion360.exe"))
    return str(found[-1]) if found else "not-found"


def main() -> int:
    uv = shutil.which("uv") or str(Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "uv.exe")
    lines = [
        "fusion-cad-ai 2.0.0",
        f"python {platform.python_version()}",
        f"uv {_run([uv, '--version'])}",
        f"git {_run(['git', '--version'])}",
        f"platform {platform.platform()}",
        f"fusion_exe {_sanitize(_fusion_exe())}",
    ]
    try:
        from importlib.metadata import version

        lines.append(f"mcp {version('mcp')}")
    except Exception:
        lines.append("mcp unavailable")
    try:
        from fusion_cad_ai.transport.official_mcp import OfficialMcpTransport

        health = OfficialMcpTransport().call("health", {}, read_only=True)
        build = str(health.get("fusion_build") or "")
        if build:
            lines.append(f"fusion_build {build}")
    except Exception as exc:
        lines.append(f"fusion_build unavailable ({exc.__class__.__name__})")
    dest = ROOT / "docs" / "versions.lock"
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        log(line)
    log(f"записал {dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
