"""Process-wide session kept on the fca_rt module across official MCP calls."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionState:
    namespace: dict = field(default_factory=dict)
    names: dict = field(default_factory=dict)
    snapshots: dict = field(default_factory=dict)
    jobs: dict = field(default_factory=dict)
    script_log: list = field(default_factory=list)
    last_error: str = ""
    model_path: str = ""
    active_component: str = ""
    document_name: str = ""


STATE = SessionState()
