"""fca:// resources."""

from __future__ import annotations

from pathlib import Path

from fusion_cad_ai.paths import DOCS
from fusion_cad_ai.service import printers, workflow_hints

_RESOURCES = Path(__file__).resolve().parents[1] / "resources"


def _static(body: str):
    def reader() -> str:
        return body

    return reader


def register(server) -> None:
    texts = {
        "fca://quickref": (_RESOURCES / "quickref.md").read_text(encoding="utf-8"),
        "fca://selectors": (_RESOURCES / "selectors.md").read_text(encoding="utf-8"),
        "fca://session": workflow_hints()["cycle"],
        "fca://units": "Длины в миллиметрах, углы в градусах. В Fusion внутри сантиметры. Поля ответа имеют суффикс _mm, _mm2, _mm3, _deg, _g.",
        "fca://license-limits": (DOCS / "license-limits.md").read_text(encoding="utf-8") if (DOCS / "license-limits.md").is_file() else "См. docs/license-limits.md",
        "fca://capabilities": (DOCS / "capability-matrix.md").read_text(encoding="utf-8") if (DOCS / "capability-matrix.md").is_file() else "См. docs/capability-matrix.md",
    }

    def add(uri: str, body: str) -> None:
        def reader() -> str:
            return body

        reader.__name__ = "resource_" + uri.replace("://", "_").replace("-", "_")
        server.resource(uri, mime_type="text/markdown")(reader)

    for uri, body in texts.items():
        add(uri, body)

    def printer_resource() -> str:
        import json

        return json.dumps(printers(), ensure_ascii=False, indent=2)

    server.resource("fca://printers", mime_type="application/json")(printer_resource)

    skills = _RESOURCES / "skills"
    if skills.is_dir():
        for path in sorted(skills.glob("*.md")):
            reader = _static(path.read_text(encoding="utf-8"))
            reader.__name__ = f"skill_{path.stem}"
            server.resource(f"fca://skills/{path.stem}", mime_type="text/markdown")(reader)
