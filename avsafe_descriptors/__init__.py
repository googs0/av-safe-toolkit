# avsafe_descriptors/__init__.py
"""
AV-SAFE Toolkit
Privacy-preserving audiovisual metrology (WHO/IEEE-aligned) + HF-AVC corpus tools.
"""

from __future__ import annotations

import logging as _logging
from importlib import metadata as _metadata

__all__ = ["__version__", "get_version"]

def get_version() -> str:
    """
    Resolve the installed distribution version (PEP 440) if available,
    otherwise fall back to the in-tree default. Adjust names if your
    PyPI/GitHub release name differs.
    """
    for dist_name in ("av-safe-toolkit", "avsafe_descriptors"):
        try:
            return _metadata.version(dist_name)
        except Exception:
            pass
    # Fallback for editable/dev installs before packaging:
    return "0.6.0"

__version__ = get_version()

# Prevent "No handler found" warnings if users import without configuring logging.
_logging.getLogger(__name__).addHandler(_logging.NullHandler())

# Optional light re-exports (keep import time light; avoid hard deps)
try:
    from .rules.profile_loader import RulesProfile, load_profile  # noqa: F401
    from .rules.evaluator import evaluate  # noqa: F401
except Exception:
    # If optional deps aren't installed, importing the package still works.
    pass
