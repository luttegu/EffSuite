"""Choose the spectrometry software for a file: Genie 2000 or GammaVision.

Rule: the environment variable EFFSUITE_SOFTWARE=genie|gammavision wins;
otherwise .LIB and .EFT files are GammaVision and everything else is Genie.
The functions below simply forward the call to genie.py or gammavision.py.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import gammavision, genie
from .genie import match_factor, read_certificate  # re-exported: used by gui.py and suite.py
from .parallel_coincidence import CoincidenceError, _publish_new

__all__ = ["detect", "label", "read_library", "read_cal", "read_certificate", "match_factor",
           "export_copy", "copy_verified_export"]


def detect(path) -> str:
    """Return "gammavision" or "genie" for this file."""
    forced = os.environ.get("EFFSUITE_SOFTWARE", "").strip().lower()
    if forced in {"genie", "gammavision"}:
        return forced
    return "gammavision" if Path(path).suffix.lower() in {".lib", ".eft"} else "genie"


def label(path) -> str:
    """Human-readable software name for a file: "GammaVision" or "Genie"."""
    return "GammaVision" if detect(path) == "gammavision" else "Genie"


def _backend(path):
    """The module (gammavision or genie) that handles this file."""
    return gammavision if detect(path) == "gammavision" else genie


def read_library(path):
    return _backend(path).read_library(path)


def read_cal(path):
    return _backend(path).read_cal(path)


def export_copy(source, destination, result, kind):
    report = _backend(source).export_copy(source, destination, result, kind)
    report["software"] = label(source)
    return report


def copy_verified_export(result: dict, kind: str, destination) -> Path:
    """Copy the corrected file that ``run_project`` already exported and verified.

    The GUI "Export" buttons use this, so a file is not exported a second time.
    ``kind`` is "cal", "nlb" or "ctf". Existing files are never overwritten.
    Returns the new file path.
    """
    info = (result.get("genie_exports") or {}).get(kind)
    if not isinstance(info, dict) or not info.get("file") or not result.get("output_directory"):
        raise CoincidenceError("This run did not export a corrected file; see the warnings in the log")
    exported = Path(result["output_directory"]) / info["file"]
    if not exported.is_file():
        raise CoincidenceError(f"The exported file is missing: {exported}")
    destination = Path(destination).resolve()
    if destination.suffix.lower() != exported.suffix.lower():
        raise CoincidenceError(f"The corrected file is a {exported.suffix.upper()} file; "
                               f"save it with the {exported.suffix.upper()} extension")
    if destination.exists():
        raise CoincidenceError("Choose a new output filename; existing files are never overwritten")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _publish_new(destination, exported.read_bytes())
    return destination
