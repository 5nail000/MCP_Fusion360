"""Refresh the official Fusion MCP tool snapshot. Paths with a user profile are rewritten."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fusion_cad_ai.logger import log
from fusion_cad_ai.transport.official_mcp import OfficialMcpTransport


def _sanitize(value: str) -> str:
    for key in ("USERPROFILE", "LOCALAPPDATA", "APPDATA"):
        raw = os.environ.get(key, "")
        if raw:
            value = value.replace(raw, f"%{key}%")
    return value


def main() -> int:
    transport = OfficialMcpTransport()
    tools = transport.list_tools()
    health = transport.call("health", {}, read_only=True)
    build = str(health.get("fusion_build") or "unknown").replace(" ", "_")
    payload = {
        "fusion_build": health.get("fusion_build"),
        "tool_names": [item.get("name") for item in tools],
        "tools": tools,
    }
    text = _sanitize(json.dumps(payload, indent=2, ensure_ascii=False))
    dest = ROOT / "docs" / "official-fusion-mcp" / f"{build}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text + "\n", encoding="utf-8")
    log(f"инструменты: {', '.join(payload['tool_names'])}")
    log(f"снимок {dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
