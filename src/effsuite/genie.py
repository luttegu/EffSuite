"""Read and write Genie 2000 files: calibrations (.CAL), nuclide libraries (.NLB)
and certificates (.CTF).

Genie stores these files in its own binary "CAM" format. Only Genie's own
component (the CamDatasource COM object) can read and write that format safely,
so we never touch the bytes ourselves. Instead we start Windows PowerShell,
which runs ``assets/genie_cam.ps1``; that script talks to Genie and sends the
answer back to Python as JSON.

Starting PowerShell takes about 2 seconds, so this module starts it as rarely
as possible:

* Rows read from a file are kept in memory, keyed by the file's content.
  Reading the same, unchanged file a second time costs nothing.
* An export starts PowerShell only once: the script writes the new values,
  saves the file, reopens it and returns what it reads back. Python then
  checks every value (the "read-back check") before publishing the file.

Source files are never modified: we always work on a private copy and publish
it under a new name.
"""
from __future__ import annotations

import base64
import copy
import json
import math
import os
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path

from .model_io import canonical_nuclide
from .parallel_coincidence import CoincidenceError, _publish_new

FILE_KINDS = ("cal", "nlb", "ctf")

# The value that is corrected in each kind of library file.
CORRECTED_QUANTITY = {"nlb": "abundance", "ctf": "rate"}

SCRIPT_PATH = Path(__file__).parent / "assets" / "genie_cam.ps1"

# Tiny PowerShell command given on the command line. It reads the real script
# and the request from standard input, then runs the script. (Passing the whole
# script on the command line would hit the Windows 32,767-character limit.)
STARTER_COMMAND = (
    "[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false); "
    "$message = [Console]::In.ReadToEnd() | ConvertFrom-Json; "
    "& ([ScriptBlock]::Create($message.script)) $message.request"
)
ENCODED_STARTER = base64.b64encode(STARTER_COMMAND.encode("utf-16-le")).decode("ascii")

# Rows already read, so the same file content is never read twice.
# Key: (file kind, SHA-256 of the file content). Value: list of rows.
_rows_cache: dict[tuple[str, str], list[dict]] = {}
MAX_CACHED_FILES = 20

# The PowerShell program that worked last time (tried first next time).
_working_powershell: Path | None = None


class LineNotCorrected(CoincidenceError):
    """There is no usable correction for this line; it is exported unchanged."""


# ---------------------------------------------------------------------------
# Talking to Genie through PowerShell
# ---------------------------------------------------------------------------

def _powershell_programs() -> list[Path]:
    """Windows PowerShell programs to try, the one that worked last time first.

    Genie's COM component is usually 32-bit, so the 32-bit PowerShell
    (in SysWOW64) is tried before the 64-bit one (in System32).
    """
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    programs = [windows / "SysWOW64/WindowsPowerShell/v1.0/powershell.exe",
                windows / "System32/WindowsPowerShell/v1.0/powershell.exe"]
    if _working_powershell in programs:
        programs.remove(_working_powershell)
        programs.insert(0, _working_powershell)
    return [program for program in programs if program.exists()]


def _call(action: str, path, updates: list[dict] | None = None) -> dict:
    """Run one action of genie_cam.ps1 on ``path`` and return its JSON answer.

    ``action`` is "read_cal", "read_nlb", "read_ctf", "write_cal", "write_nlb"
    or "write_ctf". A write action also returns the rows read back after saving.
    """
    global _working_powershell
    if os.name != "nt":
        raise CoincidenceError("Genie CAL/NLB/CTF access requires Windows and the original Genie CAM components; "
                               "text calibration files work on other platforms")
    path = Path(path).resolve()
    if not path.is_file():
        raise CoincidenceError(f"File not found: {path}")

    request = {"action": action, "path": str(path), "updates": updates or [],
               "progid": os.environ.get("EFFSUITE_CAM_PROGID", "")}
    message = json.dumps({"script": SCRIPT_PATH.read_text(encoding="utf-8"), "request": request})

    # A failed write attempt could leave the file half-changed, so we restore
    # the original bytes before trying the next PowerShell program.
    original_bytes = path.read_bytes() if action.startswith("write_") else None

    errors = []
    for program in _powershell_programs():
        if original_bytes is not None:
            path.write_bytes(original_bytes)
        command = [str(program), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", ENCODED_STARTER]
        try:
            finished = subprocess.run(command, input=message.encode("utf-8"), capture_output=True, timeout=120,
                                      shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{program.parent.parent.parent.name}: {exc}")
            continue
        try:
            answer = json.loads(finished.stdout.decode("utf-8-sig"))
        except ValueError:
            details = (finished.stderr or finished.stdout).decode(errors="replace").strip()
            errors.append(f"{program.parent.parent.parent.name}: no valid answer ({details[:1500]})")
            continue
        if answer.get("ok"):
            _working_powershell = program
            return answer
        errors.append(f"{program.parent.parent.parent.name}: {str(answer.get('error'))[:1500]}")

    if not errors:
        errors.append("Windows PowerShell was not found")
    raise CoincidenceError("Genie CAM is unavailable or rejected the file: " + " | ".join(errors))


def _read_rows(kind: str, path, content: bytes | None = None) -> list[dict]:
    """Rows of a Genie file, read only once per file content (see _rows_cache).

    ``content`` may be given when the caller has already read the file bytes.
    """
    if content is None:
        content = Path(path).read_bytes()
    key = (kind, sha256(content).hexdigest())
    if key not in _rows_cache:
        if len(_rows_cache) >= MAX_CACHED_FILES:
            _rows_cache.clear()
        _rows_cache[key] = _call("read_" + kind, path)["rows"]
    # Return a copy so callers cannot change the cached rows by accident.
    return copy.deepcopy(_rows_cache[key])


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def read_cal(path) -> list[dict]:
    """Efficiency points of a .CAL file (uncertainty converted to percent)."""
    return [{"energy_keV": float(row["energy"]),
             "efficiency": float(row["efficiency"]),
             "u_rel_percent": 100 * float(row["uncertainty"]) / float(row["efficiency"])}
            for row in _read_rows("cal", path)]


def read_library(path) -> list[dict]:
    """Gamma lines of a .NLB nuclide library."""
    return _read_rows("nlb", path)


def read_certificate(path) -> list[dict]:
    """Certified lines of a .CTF certificate file."""
    return _read_rows("ctf", path)


# ---------------------------------------------------------------------------
# Finding the correction factor of one line
# ---------------------------------------------------------------------------

def check_export_allowed(result: dict) -> None:
    """Refuse to export when the well-detector model did not pass its checks."""
    well = result.get("well_spatial_diagnostics")
    if well and (not well["convergence"]["passed"] or well["transport"]["probability_saturation_count"]):
        raise CoincidenceError("Well-model convergence/probability checks failed; Genie export is blocked")


def match_factor(result: dict, nuclide: str, energy: float) -> float:
    """Coincidence-summing correction factor of one library line.

    Raises ``LineNotCorrected`` when the line simply has no usable factor (the
    line is then exported unchanged), and ``CoincidenceError`` when exporting
    would be unsafe (well model failed, or two different factors match).
    """
    check_export_allowed(result)
    nuclide = canonical_nuclide(nuclide)   # "Co60" and "CO-60" are the same nuclide

    well = result.get("well_spatial_diagnostics")
    if well:
        record = next((r for r in well["nuclides"] if canonical_nuclide(r["nuclide"]) == nuclide), None)
        if record and record["annihilation_pair_records"] and abs(energy - 1022) < 1:
            raise LineNotCorrected("The 1022-keV pair sum-in channel is outside this backend's scope")

    # Factors of the same nuclide within 1 keV of the line energy.
    nearby = [row for row in result["summing"]
              if canonical_nuclide(row["nuclide"]) == nuclide and abs(row["energy_keV"] - energy) < 1.0]
    if not nearby:
        raise LineNotCorrected(f"No coincidence summing correction for {nuclide} at {energy:g} keV")

    # Keep the closest one(s). Two equally close rows are fine only if they agree.
    smallest_distance = min(abs(row["energy_keV"] - energy) for row in nearby)
    closest = [row for row in nearby if abs(row["energy_keV"] - energy) == smallest_distance]
    if any(row["activity_multiplier"] != closest[0]["activity_multiplier"] for row in closest):
        raise CoincidenceError(f"Ambiguous correction for {nuclide} at {energy:g} keV")
    row = closest[0]

    factor = row["activity_multiplier"]
    if row["status"] != "candidate" or factor is None or not math.isfinite(factor) or factor <= 0:
        raise LineNotCorrected(f"Unusable correction for {nuclide} at {energy:g} keV")
    return factor


# ---------------------------------------------------------------------------
# Exporting a corrected copy
# ---------------------------------------------------------------------------

def _calibration_updates(original: list[dict], result: dict) -> list[dict]:
    """New efficiency points for a .CAL file: the transferred sample efficiency."""
    new_points = result["efficiency"]
    if not new_points or len(new_points) != len(original):
        raise CoincidenceError("CAL template must contain the same number of calibration points")
    updates = []
    for entry, point in enumerate(new_points, start=1):
        efficiency = point["sample_efficiency"]
        updates.append({"entry": entry,
                        "energy": point["energy_keV"],
                        "value": efficiency,
                        "uncertainty": efficiency * point["sample_relative_uncertainty_percent_legacy"] / 100})
    return updates


def _library_updates(original: list[dict], result: dict, kind: str) -> tuple[list[dict], int]:
    """New values for a .NLB (abundance) or .CTF (emission rate) file.

    Each value is divided by its correction factor C (P_corr = P / C).
    Lines without a usable factor keep their original value.
    Returns the updates and the number of corrected lines.
    """
    quantity = CORRECTED_QUANTITY[kind]
    updates = []
    corrected_lines = 0
    for row in original:
        old_value = float(row[quantity])
        try:
            factor = match_factor(result, str(row["nuclide"]), float(row["energy"]))
            new_value = old_value / factor
            corrected_lines += 1
        except LineNotCorrected:
            new_value = old_value
        if not math.isfinite(new_value) or new_value < 0:
            raise CoincidenceError("Corrected Genie coefficient is nonfinite or negative")
        # .NLB values are addressed by "line", .CTF values by "record".
        updates.append({"line": row.get("line"), "record": row["record"], "value": new_value})
    return updates, corrected_lines


def _close(a: float, b: float) -> bool:
    """True when two numbers agree to the precision Genie stores (single precision)."""
    return math.isclose(float(a), float(b), rel_tol=2e-6, abs_tol=0.0)


def _check_read_back(kind: str, original: list[dict], updates: list[dict], read_back: list[dict]) -> None:
    """Compare the rows read back from the saved file with what we asked to write."""
    if len(read_back) != len(original):
        raise CoincidenceError("Genie round-trip changed the line count")
    quantity = "efficiency" if kind == "cal" else CORRECTED_QUANTITY[kind]
    for number, (old, wanted, saved) in enumerate(zip(original, updates, read_back), start=1):
        if not _close(saved[quantity], wanted["value"]):
            raise CoincidenceError(f"Genie round-trip failed at line {number}")
        wanted_energy = wanted["energy"] if kind == "cal" else old["energy"]
        if not math.isclose(float(saved["energy"]), float(wanted_energy), rel_tol=2e-6, abs_tol=1e-6):
            raise CoincidenceError("Genie round-trip changed a line energy")
        if kind == "cal":
            if not _close(saved["uncertainty"], wanted["uncertainty"]):
                raise CoincidenceError("Genie round-trip changed efficiency uncertainty")
        elif saved["nuclide"] != old["nuclide"]:
            raise CoincidenceError("Genie round-trip changed a nuclide")


def export_copy(source, destination, result: dict, kind: str) -> dict:
    """Write a corrected copy of a Genie file to a NEW file ``destination``.

    kind "cal": efficiency points replaced by the transferred sample efficiency.
    kind "nlb"/"ctf": abundances / emission rates divided by the summing factor.
    The copy is written, saved, reopened and checked before it is published.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists() or source == destination:
        raise CoincidenceError("Choose a new output filename; source files are never overwritten")
    if kind not in FILE_KINDS:
        raise CoincidenceError("Unsupported Genie format")
    if kind != "cal":
        check_export_allowed(result)

    # Read the source once; everything below uses these exact bytes.
    source_bytes = source.read_bytes()
    original = _read_rows(kind, source, source_bytes)
    if kind == "cal":
        updates = _calibration_updates(original, result)
        corrected_lines = len(updates)
    else:
        updates, corrected_lines = _library_updates(original, result, kind)

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Work on a private copy next to the destination; Genie never sees the source path.
    with tempfile.TemporaryDirectory(prefix="effsuite-cam-", dir=destination.parent) as temporary:
        work_copy = Path(temporary) / source.name
        work_copy.write_bytes(source_bytes)
        answer = _call("write_" + kind, work_copy, updates)
        _check_read_back(kind, original, updates, answer["rows"])
        output_bytes = work_copy.read_bytes()
        _publish_new(destination, output_bytes)

    return {"source_sha256": sha256(source_bytes).hexdigest(),
            "output_sha256": sha256(output_bytes).hexdigest(),
            "roundtrip_verified": True,
            "format": kind,
            "lines": len(updates),
            "corrected_lines": corrected_lines,
            "cam_host": {key: answer.get(key) for key in ("progid", "architecture", "type_library", "type_library_version")}}

