"""Stable error codes returned by every tool."""

from __future__ import annotations

from typing import Any


class FcaError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        hint: str = "",
        fusion_error: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.fusion_error = fusion_error

    def to_dict(self, request_id: str = "") -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "hint": self.hint,
            },
        }
        if self.fusion_error:
            payload["error"]["fusion_error"] = self.fusion_error
        if request_id:
            payload["error"]["request_id"] = request_id
        return payload
