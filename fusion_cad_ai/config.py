"""Runtime configuration from the environment. Nothing here is a secret path with a username."""

from __future__ import annotations

import os

from fusion_cad_ai.paths import ROOT

FUSION_MCP_URL = os.environ.get("FCA_FUSION_URL", "http://127.0.0.1:27182/mcp")
EXEC_TIMEOUT_S = int(os.environ.get("FCA_EXEC_TIMEOUT", "120"))
TRANSPORT = os.environ.get("FCA_TRANSPORT", "official").strip().lower()
TOOL_GROUPS = tuple(
    item.strip()
    for item in os.environ.get("FCA_TOOL_GROUPS", "core,assembly").split(",")
    if item.strip()
)
TOOL_ALLOWLIST = tuple(
    item.strip() for item in os.environ.get("FCA_TOOLS", "").split(",") if item.strip()
)
PROTOCOL_VERSION = "2025-06-18"
ENVELOPE_MARK_OPEN = "FCA>>"
ENVELOPE_MARK_CLOSE = "<<FCA"


def fusion_host_port() -> tuple[str, int]:
    url = FUSION_MCP_URL
    rest = url.split("://", 1)[-1]
    host_port = rest.split("/", 1)[0]
    if ":" in host_port:
        host, port_s = host_port.rsplit(":", 1)
        return host, int(port_s)
    return host_port, 80


def allowed_write_roots() -> tuple[str, ...]:
    return tuple(
        str(path)
        for path in (
            ROOT / "exports",
            ROOT / "renders",
            ROOT / ".runtime",
        )
    )
