"""Build the stdio server. Default groups are core and assembly."""

from __future__ import annotations

import json
from functools import wraps

from mcp.server.mcpserver import MCPServer

from fusion_cad_ai import __version__
from fusion_cad_ai.config import TOOL_ALLOWLIST, TOOL_GROUPS
from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.mcp_server import prompts, resources
from fusion_cad_ai.mcp_server.tools_analysis import EXPERIMENTAL, LIBRARY, REFS
from fusion_cad_ai.mcp_server.tools_assembly import ASSEMBLY
from fusion_cad_ai.mcp_server.tools_core import CORE
from fusion_cad_ai.mcp_server.tools_extra import CAM, CLOUD, CONFIGS, DRAWINGS, RENDER, SHEET, VOLUME
from fusion_cad_ai.units import AmbiguousUnitError

GROUPS = {
    "core": CORE,
    "assembly": ASSEMBLY,
    "library": LIBRARY,
    "refs": REFS,
    "experimental": EXPERIMENTAL,
    "cam": CAM,
    "sheet_metal": SHEET,
    "render": RENDER,
    "volume": VOLUME,
    "configs": CONFIGS,
    "drawings": DRAWINGS,
    "cloud": CLOUD,
}


def guard(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except FcaError as exc:
            raise RuntimeError(json.dumps(exc.to_dict(), ensure_ascii=False)) from None
        except AmbiguousUnitError as exc:
            raise RuntimeError(json.dumps(FcaError("UNIT_AMBIGUOUS", str(exc)).to_dict(), ensure_ascii=False)) from None

    return wrapped


def build_server() -> MCPServer:
    server = MCPServer(
        name="fusion-cad-ai",
        instructions=(
            "Инженерный слой Autodesk Fusion. Длины в миллиметрах. "
            "Цикл BUILD → VALIDATE → INSPECT → PREVIEW → проверочный экспорт → VERIFY → exports/. "
            "STEP — мастер. Не закрывай чужие документы."
        ),
        version=__version__,
    )
    allow = set(TOOL_ALLOWLIST)
    enabled = set(TOOL_GROUPS)
    for group, tools in GROUPS.items():
        for name, fn, annotations, description in tools:
            if allow and name not in allow:
                continue
            if not allow and group not in enabled:
                continue
            server.tool(name=name, description=description, annotations=annotations, structured_output=False)(guard(fn))
    resources.register(server)
    prompts.register(server)
    return server
