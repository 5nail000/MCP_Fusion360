"""Transport contract. Every Fusion call goes through one of these."""

from __future__ import annotations

from typing import Protocol


READ_ONLY_OPS = frozenset(
    {
        "health",
        "measure",
        "validate",
        "locate_defects",
        "inspect",
        "cross_sections",
        "compare",
        "find_features",
        "interference",
        "params_get",
        "session_state",
        "last_error",
        "script_log",
        "job_status",
        "search_library",
        "sheet_metal_rules",
        "config_get",
        "cloud_list",
        "cam_recognize",
        "visual_analyses",
        "thread_library",
    }
)


class FusionTransport(Protocol):
    def call(
        self,
        op: str,
        params: dict | None = None,
        *,
        timeout_s: float | None = None,
        read_only: bool = False,
    ) -> dict: ...

    def screenshot(self, direction: str, width_px: int, height_px: int) -> dict: ...
