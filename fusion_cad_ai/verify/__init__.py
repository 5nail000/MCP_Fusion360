"""Second kernel. Missing optional packages become warnings, not a silent pass of deep checks."""

from fusion_cad_ai.verify.files import verify_files

__all__ = ["verify_files"]
