"""CLI: BUILD → VERIFY for a model in models/."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fusion_cad_ai.logger import log
from fusion_cad_ai.pipeline import find_model, run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Собрать модель Fusion и проверить экспорт")
    parser.add_argument("model", nargs="?", help="Имя модели без .py")
    parser.add_argument("--formats", default="step,stl,3mf,f3d")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if args.list or not args.model:
        for folder in ("parts", "assemblies", "lib"):
            for path in sorted((ROOT / "models" / folder).glob("*.py")):
                if path.name != "__init__.py":
                    log(f"{folder}/{path.stem}")
        return 0 if args.list else 1
    try:
        find_model(args.model)
    except FileNotFoundError as exc:
        log(str(exc), "ERROR")
        return 1
    started = datetime.now()
    result = run_pipeline(args.model, [item.strip() for item in args.formats.split(",") if item.strip()])
    log(f"готово за {(datetime.now() - started).total_seconds():.1f} с, ok={result.ok}")
    for item in result.files:
        log(item)
    for warning in result.warnings:
        log(warning, "WARN")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
