"""ORTEC GammaVision nuclide library (.LIB) reader/writer in pure Python.

Layout follows the record structure used by EFFTRAN's gv.f: 128-byte little-endian
records; record 1 is the header, isotope records hold 3 x 42-byte entries and peak
records hold 4 x 32-byte entries. Only the gamma yield of each peak is rewritten.
Writes use a private copy that is reopened and verified before publication.
"""
from __future__ import annotations
from hashlib import sha256
import math
from pathlib import Path
import shutil
import struct
import tempfile

from .parallel_coincidence import CoincidenceError, _publish_new

REC = 128
_HEADER = struct.Struct("<8h7h9h8h19s2h11h")
_ISO = struct.Struct("<8sffhhhh8shhhhh")  # 42 bytes
_PEAK = struct.Struct("<ffhhhhhhhhhhhh")  # 32 bytes
_PEAK_YIELD_OFFSET = 4
assert _ISO.size == 42 and _PEAK.size == 32 and _HEADER.size <= REC


def _layout(data):
    if len(data) < REC:raise CoincidenceError("Not a GammaVision library: file is too short")
    h = _HEADER.unpack_from(data, 0)
    reclen, rectot = h[2], h[3]
    isobas, pkbas = h[15], h[23]
    if reclen != REC // 2 or rectot < pkbas or not 1 < isobas < pkbas or len(data) < rectot * REC:
        raise CoincidenceError("Not a recognised GammaVision .LIB file (unexpected header)")
    return isobas, pkbas, rectot


def _parse(data):
    isobas, pkbas, rectot = _layout(data)
    isotopes = []
    for rec in range(isobas, pkbas):
        for j in range(3):
            f = _ISO.unpack_from(data, (rec - 1) * REC + j * _ISO.size)
            name = f[0].replace(b"\0", b" ").decode("latin-1").strip()
            isotopes.append({"index": len(isotopes) + 1, "name": name, "selfpt": f[8]})
    peaks = []
    for rec in range(pkbas, rectot + 1):
        for j in range(4):
            off = (rec - 1) * REC + j * _PEAK.size
            f = _PEAK.unpack_from(data, off)
            peaks.append({"index": len(peaks) + 1, "offset": off + _PEAK_YIELD_OFFSET,
                          "energy": f[0], "yield": f[1], "nucpt": f[7]})
    return isotopes, peaks


def read_library(path):
    isotopes, peaks = _parse(Path(path).read_bytes())
    rows = []
    for iso in isotopes:
        if not iso["name"]:continue
        for pk in peaks:
            if pk["nucpt"] == iso["selfpt"] and pk["energy"] > 0 and math.isfinite(pk["yield"]):
                rows.append({"nuclide": iso["name"].upper(), "energy": float(pk["energy"]),
                             "abundance": float(pk["yield"]), "record": iso["index"],
                             "line": pk["index"], "offset": pk["offset"]})
    if not rows:raise CoincidenceError("GammaVision library contains no gamma lines")
    return rows


def export_copy(source, destination, result, kind="nlb"):
    from .genie import match_factor
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists() or source == destination:raise CoincidenceError("Choose a new output filename; source files are never overwritten")
    if kind == "cal":return _export_eft(source, destination, result)
    if kind != "nlb":raise CoincidenceError("GammaVision supports library (.LIB) and efficiency (.EFT) export")
    original = read_library(source)
    data = bytearray(source.read_bytes())
    expected = []
    applied = []
    for old in original:
        try:value = old["abundance"] / match_factor(result, old["nuclide"], old["energy"])
        except CoincidenceError:value = old["abundance"]
        if not math.isfinite(value) or value < 0:raise CoincidenceError("Corrected GammaVision yield is nonfinite or negative")
        struct.pack_into("<f", data, old["offset"], value)
        expected.append(struct.unpack("<f", struct.pack("<f", value))[0])
        applied.append((old, value, 1 if value != old["abundance"] else 0))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="effsuite-gv-", dir=destination.parent) as tmp:
        copy = Path(tmp) / source.name
        copy.write_bytes(bytes(data))
        actual = read_library(copy)
        if len(actual) != len(original):raise CoincidenceError("GammaVision round-trip changed the line count")
        for old, row, exp in zip(original, actual, expected):
            if row["nuclide"] != old["nuclide"] or row["energy"] != old["energy"]:raise CoincidenceError("GammaVision round-trip changed a line")
            if not math.isclose(row["abundance"], exp, rel_tol=2e-6, abs_tol=0.):raise CoincidenceError("GammaVision round-trip failed")
        _publish_new(destination, copy.read_bytes())
    # Same report as EFFTRAN gv.txt: nuclide, then energy, old yield, new yield, factor, applied flag.
    report = []
    for old, value, flag in applied:
        factor = old["abundance"] / value if value else 1.0
        report.append(old["nuclide"])
        report.append(f"{old['energy']:10.2f}{old['abundance']:10.2f}{value:10.2f}{factor:10.3f}{flag:5d}")
    report_path = destination.with_name(destination.stem + "_gv.txt")
    if not report_path.exists():report_path.write_text("\n".join(report) + "\n", encoding="ascii")
    return {"source_sha256": sha256(source.read_bytes()).hexdigest(), "output_sha256": sha256(destination.read_bytes()).hexdigest(),
            "roundtrip_verified": True, "format": "lib", "lines": len(original), "report": str(report_path)}


# ---- GammaVision efficiency (.EFT) -------------------------------------------------
# EFFTRAN.EFT layout: one calibration point per line,
#   energy eff [livetime realtime date time nuclide activity] unc% 100.0 flag
# followed by trailer lines ("FitType = ...", "Total Source Uncertainty = ...").
# MEFFTRAN.EFT uses the short form: energy eff unc% 100.0 flag.
def _eft_lines(text):
    out = []
    for i, line in enumerate(text.splitlines()):
        t = line.split()
        if len(t) in (5, 11):
            try:
                e, eff = float(t[0]), float(t[1])
                u = float(t[2] if len(t) == 5 else t[8])
            except ValueError:continue
            out.append((i, t, e, eff, u))
    if not out:raise CoincidenceError("No calibration points found in GammaVision .EFT file")
    return out


def read_cal(path):
    text = Path(path).read_text(encoding="latin-1")
    return [{"energy_keV": e, "efficiency": eff, "u_rel_percent": u} for _, _, e, eff, u in _eft_lines(text)]


def _export_eft(source, destination, result):
    text = Path(source).read_text(encoding="latin-1")
    pts = _eft_lines(text)
    rows = result["efficiency"]
    if not rows or len(rows) != len(pts):raise CoincidenceError("EFT template must contain the same number of calibration points")
    lines = text.splitlines()
    sep = "\r\n" if "\r\n" in text else "\n"
    for (i, t, _, _, _), new in zip(pts, rows):
        t[0] = f"{new['energy_keV']:.2f}"
        t[1] = f"{new['sample_efficiency']:.3E}"
        t[2 if len(t) == 5 else 8] = f"{new['sample_relative_uncertainty_percent_legacy']:.1f}"
        lines[i] = " ".join(t)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="effsuite-gv-", dir=destination.parent) as tmp:
        copy = Path(tmp) / source.name
        copy.write_bytes((sep.join(lines) + (sep if text.endswith("\n") else "")).encode("latin-1"))
        back = read_cal(copy)
        for b, new in zip(back, rows):
            if not math.isclose(b["efficiency"], new["sample_efficiency"], rel_tol=1e-3) or abs(b["energy_keV"] - new["energy_keV"]) > 0.01:
                raise CoincidenceError("GammaVision EFT round-trip failed")
        _publish_new(destination, copy.read_bytes())
    return {"source_sha256": sha256(source.read_bytes()).hexdigest(), "output_sha256": sha256(destination.read_bytes()).hexdigest(),
            "roundtrip_verified": True, "format": "eft", "lines": len(pts)}
