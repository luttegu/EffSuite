"""Read and write ORTEC GammaVision files: nuclide libraries (.LIB) and
efficiency calibrations (.EFT), in pure Python.

.LIB layout (the same as EFFTRAN's gv.f reads it):

* The file is a sequence of 128-byte records, numbers in little-endian order.
* Record 1 is the header. It says where the isotope records and the peak
  records start, and how many records there are in total.
* Each isotope record holds 3 isotope entries of 42 bytes.
* Each peak record holds 4 peak (gamma line) entries of 32 bytes. A peak
  points to its isotope through a number ("nucpt") that matches the
  isotope's own number ("selfpt").

Only the gamma yield of each peak is ever changed. Exports are written to a
private copy, read back and checked before the new file is published.
"""
from __future__ import annotations

import math
import struct
import tempfile
from hashlib import sha256
from pathlib import Path

from .parallel_coincidence import CoincidenceError, _publish_new

RECORD_SIZE = 128
HEADER = struct.Struct("<8h7h9h8h19s2h11h")
ISOTOPE_ENTRY = struct.Struct("<8sffhhhh8shhhhh")   # 42 bytes
PEAK_ENTRY = struct.Struct("<ffhhhhhhhhhhhh")       # 32 bytes
ISOTOPES_PER_RECORD = 3
PEAKS_PER_RECORD = 4
YIELD_OFFSET_IN_PEAK = 4   # the yield is the second float of a peak entry
assert ISOTOPE_ENTRY.size == 42 and PEAK_ENTRY.size == 32 and HEADER.size <= RECORD_SIZE


# ---------------------------------------------------------------------------
# .LIB files
# ---------------------------------------------------------------------------

def _record_layout(data: bytes) -> tuple[int, int, int]:
    """Read the header: (first isotope record, first peak record, last record).

    Records are numbered from 1, like in the original Fortran program.
    """
    if len(data) < RECORD_SIZE:
        raise CoincidenceError("Not a GammaVision library: file is too short")
    header = HEADER.unpack_from(data, 0)
    record_length_in_words, total_records = header[2], header[3]
    first_isotope_record, first_peak_record = header[15], header[23]
    if (record_length_in_words != RECORD_SIZE // 2 or total_records < first_peak_record
            or not 1 < first_isotope_record < first_peak_record or len(data) < total_records * RECORD_SIZE):
        raise CoincidenceError("Not a recognised GammaVision .LIB file (unexpected header)")
    return first_isotope_record, first_peak_record, total_records


def _parse(data: bytes) -> tuple[list[dict], list[dict]]:
    """All isotope entries and all peak entries of a .LIB file."""
    first_isotope_record, first_peak_record, total_records = _record_layout(data)

    isotopes = []
    for record in range(first_isotope_record, first_peak_record):
        for slot in range(ISOTOPES_PER_RECORD):
            fields = ISOTOPE_ENTRY.unpack_from(data, (record - 1) * RECORD_SIZE + slot * ISOTOPE_ENTRY.size)
            name = fields[0].replace(b"\0", b" ").decode("latin-1").strip()
            isotopes.append({"index": len(isotopes) + 1, "name": name, "selfpt": fields[8]})

    peaks = []
    for record in range(first_peak_record, total_records + 1):
        for slot in range(PEAKS_PER_RECORD):
            start = (record - 1) * RECORD_SIZE + slot * PEAK_ENTRY.size
            fields = PEAK_ENTRY.unpack_from(data, start)
            peaks.append({"index": len(peaks) + 1,
                          "offset": start + YIELD_OFFSET_IN_PEAK,   # where the yield is stored in the file
                          "energy": fields[0], "yield": fields[1], "nucpt": fields[7]})
    return isotopes, peaks


def _library_rows(data: bytes) -> list[dict]:
    """Gamma lines of a .LIB file given as bytes (one row per line)."""
    isotopes, peaks = _parse(data)
    rows = []
    for isotope in isotopes:
        if not isotope["name"]:
            continue   # empty slot
        for peak in peaks:
            if peak["nucpt"] == isotope["selfpt"] and peak["energy"] > 0 and math.isfinite(peak["yield"]):
                rows.append({"nuclide": isotope["name"].upper(), "energy": float(peak["energy"]),
                             "abundance": float(peak["yield"]), "record": isotope["index"],
                             "line": peak["index"], "offset": peak["offset"]})
    if not rows:
        raise CoincidenceError("GammaVision library contains no gamma lines")
    return rows


def read_library(path) -> list[dict]:
    """Gamma lines of a .LIB file."""
    return _library_rows(Path(path).read_bytes())


def _as_float32(value: float) -> float:
    """The value as it is stored in the file (4-byte float)."""
    return struct.unpack("<f", struct.pack("<f", value))[0]


def export_copy(source, destination, result: dict, kind: str = "nlb") -> dict:
    """Write a corrected copy of a GammaVision file to a NEW file ``destination``.

    kind "nlb": every gamma yield is divided by its summing correction factor.
    kind "cal": the .EFT efficiencies are replaced by the transferred ones.
    """
    from .genie import LineNotCorrected, check_export_allowed, match_factor
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists() or source == destination:
        raise CoincidenceError("Choose a new output filename; source files are never overwritten")
    if kind == "cal":
        return _export_eft(source, destination, result)
    if kind != "nlb":
        raise CoincidenceError("GammaVision supports library (.LIB) and efficiency (.EFT) export")
    check_export_allowed(result)

    # Read the source once; parsing, patching and hashing all use these bytes.
    source_bytes = source.read_bytes()
    original = _library_rows(source_bytes)
    data = bytearray(source_bytes)
    expected_yields = []   # what the file must contain after saving
    report_lines = []      # (row, new yield, 1 if changed else 0)
    for row in original:
        try:
            new_yield = row["abundance"] / match_factor(result, row["nuclide"], row["energy"])
        except LineNotCorrected:
            new_yield = row["abundance"]   # no usable factor: keep the yield
        if not math.isfinite(new_yield) or new_yield < 0:
            raise CoincidenceError("Corrected GammaVision yield is nonfinite or negative")
        struct.pack_into("<f", data, row["offset"], new_yield)
        expected_yields.append(_as_float32(new_yield))
        report_lines.append((row, new_yield, 1 if new_yield != row["abundance"] else 0))

    destination.parent.mkdir(parents=True, exist_ok=True)
    output_bytes = bytes(data)
    with tempfile.TemporaryDirectory(prefix="effsuite-gv-", dir=destination.parent) as temporary:
        work_copy = Path(temporary) / source.name
        work_copy.write_bytes(output_bytes)
        # Read-back check: the saved copy must contain exactly the new yields.
        saved = read_library(work_copy)
        if len(saved) != len(original):
            raise CoincidenceError("GammaVision round-trip changed the line count")
        for old, new, wanted in zip(original, saved, expected_yields):
            if new["nuclide"] != old["nuclide"] or new["energy"] != old["energy"]:
                raise CoincidenceError("GammaVision round-trip changed a line")
            if not math.isclose(new["abundance"], wanted, rel_tol=2e-6, abs_tol=0.):
                raise CoincidenceError("GammaVision round-trip failed")
        _publish_new(destination, output_bytes)

    # Text report in the same format as EFFTRAN's gv.txt: the nuclide name, then
    # energy, old yield, new yield, factor and a 1/0 "changed" flag.
    report = []
    for row, new_yield, changed in report_lines:
        factor = row["abundance"] / new_yield if new_yield else 1.0
        report.append(row["nuclide"])
        report.append(f"{row['energy']:10.2f}{row['abundance']:10.2f}{new_yield:10.2f}{factor:10.3f}{changed:5d}")
    report_path = destination.with_name(destination.stem + "_gv.txt")
    report_path.write_text("\n".join(report) + "\n", encoding="ascii")   # always rewritten: never stale

    return {"source_sha256": sha256(source_bytes).hexdigest(), "output_sha256": sha256(output_bytes).hexdigest(),
            "roundtrip_verified": True, "format": "lib", "lines": len(original),
            "corrected_lines": sum(changed for _, _, changed in report_lines), "report": str(report_path)}


# ---------------------------------------------------------------------------
# .EFT files (text)
#
# EFFTRAN .EFT: one calibration point per line, 11 fields:
#   energy  efficiency  livetime realtime date time nuclide activity  unc%  100.0  flag
# MEFFTRAN .EFT: the short form with 5 fields:
#   energy  efficiency  unc%  100.0  flag
# Other lines ("FitType = ...", "Total Source Uncertainty = ...") are kept as they are.
# ---------------------------------------------------------------------------

def _uncertainty_field(fields: list[str]) -> int:
    """Position of the uncertainty (%) in a calibration line."""
    return 2 if len(fields) == 5 else 8


def _eft_points(text: str) -> list[tuple[int, list[str], float, float, float]]:
    """Calibration lines: (line number, fields, energy, efficiency, uncertainty %)."""
    points = []
    for number, line in enumerate(text.splitlines()):
        fields = line.split()
        if len(fields) not in (5, 11):
            continue
        try:
            energy, efficiency = float(fields[0]), float(fields[1])
            uncertainty = float(fields[_uncertainty_field(fields)])
        except ValueError:
            continue   # a text line that happens to have 5 or 11 words
        points.append((number, fields, energy, efficiency, uncertainty))
    if not points:
        raise CoincidenceError("No calibration points found in GammaVision .EFT file")
    return points


def read_cal(path) -> list[dict]:
    """Efficiency points of a .EFT file."""
    text = Path(path).read_text(encoding="latin-1")
    return [{"energy_keV": energy, "efficiency": efficiency, "u_rel_percent": uncertainty}
            for _, _, energy, efficiency, uncertainty in _eft_points(text)]


def _export_eft(source: Path, destination: Path, result: dict) -> dict:
    """Write the template .EFT with the transferred sample efficiencies."""
    # Decode the bytes ourselves: read_text() would turn Windows line endings
    # into Unix ones, so the template's own line endings could not be kept.
    source_bytes = source.read_bytes()
    source_text = source_bytes.decode("latin-1")
    points = _eft_points(source_text)
    new_points = result["efficiency"]
    if not new_points or len(new_points) != len(points):
        raise CoincidenceError("EFT template must contain the same number of calibration points")

    lines = source_text.splitlines()
    line_end = "\r\n" if "\r\n" in source_text else "\n"   # keep the template's line endings
    for (number, fields, _, _, _), new in zip(points, new_points):
        fields[0] = f"{new['energy_keV']:.2f}"
        fields[1] = f"{new['sample_efficiency']:.3E}"
        fields[_uncertainty_field(fields)] = f"{new['sample_relative_uncertainty_percent_legacy']:.1f}"
        lines[number] = " ".join(fields)
    output_bytes = (line_end.join(lines) + (line_end if source_text.endswith("\n") else "")).encode("latin-1")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="effsuite-gv-", dir=destination.parent) as temporary:
        work_copy = Path(temporary) / source.name
        work_copy.write_bytes(output_bytes)
        # Read-back check (the file keeps 4 significant digits, hence rel_tol=1e-3).
        for saved, new in zip(read_cal(work_copy), new_points):
            if (not math.isclose(saved["efficiency"], new["sample_efficiency"], rel_tol=1e-3)
                    or abs(saved["energy_keV"] - new["energy_keV"]) > 0.01):
                raise CoincidenceError("GammaVision EFT round-trip failed")
        _publish_new(destination, output_bytes)

    return {"source_sha256": sha256(source_bytes).hexdigest(),
            "output_sha256": sha256(output_bytes).hexdigest(),
            "roundtrip_verified": True, "format": "eft", "lines": len(points)}
