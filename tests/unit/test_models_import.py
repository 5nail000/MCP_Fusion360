from __future__ import annotations

import importlib
import sys


def test_params_import_without_adsk() -> None:
    sys.modules.pop("adsk", None)
    module = importlib.import_module("models.parts.flange")
    params = module.FlangeParams()
    assert params.unit == "mm"
    assert params.outer_diameter_mm == 40.0
    assert "adsk" not in sys.modules
