"""Software dispatch: picks the Genie (CAM) or GammaVision backend.

Selection: EFFSUITE_SOFTWARE=genie|gammavision overrides; otherwise a .LIB file
is GammaVision and everything else is Genie.
"""
from __future__ import annotations
import os
from pathlib import Path

from . import genie, gammavision
from .genie import match_factor, read_certificate  # noqa: F401  (shared / Genie-only)


def detect(path):
    forced = os.environ.get("EFFSUITE_SOFTWARE", "").strip().lower()
    if forced in {"genie", "gammavision"}:return forced
    return "gammavision" if Path(path).suffix.lower() in {".lib", ".eft"} else "genie"


def label(path):
    """Human-readable software name for a file: "GammaVision" or "Genie"."""
    return "GammaVision" if detect(path) == "gammavision" else "Genie"


def read_library(path):
    return (gammavision if detect(path) == "gammavision" else genie).read_library(path)


def export_copy(source, destination, result, kind):
    report = (gammavision if detect(source) == "gammavision" else genie).export_copy(source, destination, result, kind)
    report["software"] = label(source)
    return report


def read_cal(path):
    return (gammavision if detect(path) == "gammavision" else genie).read_cal(path)
