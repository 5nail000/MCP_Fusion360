"""Named selectors stored as attributes. entityToken is returned, never compared as text."""

from __future__ import annotations

from fca_rt.recognize import resolve


def select(object_name: str, selector: str, label: str = "") -> dict:
    return resolve(object_name, selector, label or selector)
