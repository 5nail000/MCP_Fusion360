"""Runtime loaded inside Fusion. Standard library and adsk only."""

SOURCE_SHA = ""


def handle(op: str, params_json: str, request_id: str) -> None:
    from fca_rt.dispatch import handle as _handle

    _handle(op, params_json, request_id)
