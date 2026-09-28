from __future__ import annotations

import pytest

from fusion_cad_ai.engineering import LinearDim
from fusion_cad_ai.units import AmbiguousUnitError, assert_public_keys, cm3_to_mm3, require_explicit_unit


def test_unitless_length_is_rejected() -> None:
    with pytest.raises(AmbiguousUnitError):
        require_explicit_unit(10, None)


def test_inch_converts_to_mm() -> None:
    assert require_explicit_unit(1, "in") == pytest.approx(25.4)


def test_cube_volume_scale() -> None:
    assert cm3_to_mm3(1.0) == 1000.0


def test_hole_clearance_increases_diameter() -> None:
    dim = LinearDim("hole", 8.0, clearance_mm=0.2, kind="hole")
    assert dim.effective_mm == pytest.approx(8.2)


def test_shaft_clearance_decreases_diameter() -> None:
    dim = LinearDim("pin", 8.0, clearance_mm=0.2, kind="shaft")
    assert dim.effective_mm == pytest.approx(7.8)


def test_bare_public_key_rejected() -> None:
    with pytest.raises(AmbiguousUnitError):
        assert_public_keys({"volume": 1})
