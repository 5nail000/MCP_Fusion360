"""Read-only volume and bbox from MCP_FreeCAD. Writes nothing in that repository."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREE_ROOT = Path(os.environ.get("FCA_FREECAD_ROOT", r"C:\Cursor_Projects\MCP_FreeCAD"))
FREE_PYTHON = FREE_ROOT / ".venv" / "Scripts" / "python.exe"
OUT = ROOT / "tests" / "golden" / "parity_freecad.json"

PROBE = r"""
import json, sys
sys.path.insert(0, r"__ROOT__")
from models.parts.flange import build as flange_build
from models.parts.enclosure import build as enclosure_build
from models.parts.print_bracket import build as bracket_build
from models.assemblies.pin_joint import build_base, build_cap, place_cap_on_base

def pack(shape):
    box = shape.bounding_box()
    size = box.size
    return {
        "volume_mm3": float(shape.volume),
        "bbox_mm": [float(size.X), float(size.Y), float(size.Z)],
    }

report = {
    "flange": pack(flange_build()),
    "enclosure": pack(enclosure_build()),
    "print_bracket": pack(bracket_build()),
    "pin_base": pack(build_base()),
    "pin_cap": pack(place_cap_on_base(build_cap())),
}
sys.stdout.write("GOLDEN|" + json.dumps(report))
"""


def log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] [INFO] {message}", file=sys.stderr, flush=True)


def main() -> int:
    if not FREE_PYTHON.is_file():
        log(f"Нет интерпретатора MCP_FreeCAD: {FREE_PYTHON}")
        return 1
    code = PROBE.replace("__ROOT__", str(FREE_ROOT))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    log("Считаю golden только чтением MCP_FreeCAD")
    completed = subprocess.run(
        [str(FREE_PYTHON), "-B", "-c", code],
        cwd=str(FREE_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        log(completed.stderr[-1500:])
        log(completed.stdout[-500:])
        return completed.returncode
    line = next(item for item in completed.stdout.splitlines() if item.startswith("GOLDEN|"))
    payload = json.loads(line.split("|", 1)[1])
    payload["source"] = "MCP_FreeCAD read-only"
    payload["tolerances"] = {"volume_ratio": 0.002, "bbox_mm": 0.02}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(f"Записал {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
