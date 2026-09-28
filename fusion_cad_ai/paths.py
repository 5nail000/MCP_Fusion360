"""Project directories. CAD outputs stay inside this workspace."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
EXPORTS = ROOT / "exports"
EXPORT_STEP = EXPORTS / "step"
EXPORT_STL = EXPORTS / "stl"
EXPORT_3MF = EXPORTS / "3mf"
EXPORT_F3D = EXPORTS / "f3d"
EXPORT_OBJ = EXPORTS / "obj"
EXPORT_DXF = EXPORTS / "dxf"
EXPORT_NC = EXPORTS / "nc"
EXPORT_PDF = EXPORTS / "pdf"
RENDERS = ROOT / "renders"
REFERENCES = ROOT / "references"
RUNTIME = ROOT / ".runtime"
VERIFY_DIR = RUNTIME / "verify"
SNAPSHOTS = RUNTIME / "snapshots"
RESULTS = RUNTIME / "results"
LOGS = ROOT / "logs"
FUSION_RUNTIME = ROOT / "fusion_runtime" / "fca_rt"
DOCS = ROOT / "docs"

EXPORT_DIRS = {
    "step": EXPORT_STEP,
    "stl": EXPORT_STL,
    "3mf": EXPORT_3MF,
    "f3d": EXPORT_F3D,
    "obj": EXPORT_OBJ,
    "dxf": EXPORT_DXF,
    "nc": EXPORT_NC,
    "pdf": EXPORT_PDF,
}


def ensure_output_dirs() -> None:
    for folder in (
        EXPORT_STEP,
        EXPORT_STL,
        EXPORT_3MF,
        EXPORT_F3D,
        EXPORT_OBJ,
        EXPORT_DXF,
        EXPORT_NC,
        EXPORT_PDF,
        RENDERS,
        VERIFY_DIR,
        SNAPSHOTS,
        RESULTS,
        LOGS,
        REFERENCES,
    ):
        folder.mkdir(parents=True, exist_ok=True)
