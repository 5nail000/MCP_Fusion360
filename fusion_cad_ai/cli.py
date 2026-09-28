"""stdio entry point. Logs stay on stderr so the MCP stream stays clean."""

from __future__ import annotations

import logging
import sys

from fusion_cad_ai import __version__
from fusion_cad_ai.logger import log


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args or "-V" in args:
        print(f"fusion-cad-ai {__version__}")
        return 0
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
    log(f"fusion-cad-ai {__version__} stdio")
    from fusion_cad_ai.mcp_server.server import build_server

    build_server().run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
