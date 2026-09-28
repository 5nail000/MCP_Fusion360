"""Public payloads keep unit suffixes. A bare length field is a contract error."""

from __future__ import annotations

from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.units import assert_public_keys


def seal(payload: dict) -> dict:
    try:
        assert_public_keys(payload)
    except Exception as exc:
        raise FcaError("UNIT_AMBIGUOUS", str(exc)) from exc
    return payload
