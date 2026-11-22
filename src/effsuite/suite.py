"""Complete calculations (efficiency transfer and coincidence summing), shared
by the GUI and the CLI.

The main entry point is run_project(). In short, it:

1. checks the project (validate_project);
2. prepares a working folder with the models and material files
   (_prepare_folder) and runs the efficiency transfer (_run_transfer);
3. calculates the coincidence summing factors (_run_summing): the original
   Fortran engines for cylindrical and Marinelli samples, the ray-traced
   spatial model (well_spatial.py) for well detectors;
4. matches the factors to the lines of the user's nuclide library;
5. exports corrected Genie / GammaVision files and writes the result files
   (results.json, CSV tables, report.html) into a new results folder.
"""
from __future__ import annotations

import csv
import html
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from . import __version__ as VERSION
from .model_io import (ASSETS, COMMON_DATA, MODES, canonical_nuclide, material_roots, mode_name, model_bytes,
                       normalize_nuclides, validate_calibration, validate_model)
from .parallel_coincidence import (CalculationCancelled, CoincidenceError, SharedInputs,
                                   _publish_new, _terminate, calculate_parallel)
from . import tcs_uncertainty

# Fortran programs that prepare the efficiency curves for the summing calculation, in order.
PREP = ("mine", "energy", "total", "scatter", "buildup", "eta", "ptt", "efficiency")


# ---------------------------------------------------------------------------
# Checking a project
# ---------------------------------------------------------------------------

def validate_project(project: dict) -> dict:
    """Check a project and return a clean copy (models validated, names normalized).

    A project is a dict with: geometry, task ("transfer", "summing" or
    "both"), detector, sample, and for a transfer also standard and calibration;
    for summing a list of nuclides.
    """
    if project.get("schema_version") != 1:
        raise CoincidenceError("Unsupported project file version")
    out = json.loads(json.dumps(project, allow_nan=False))   # deep copy; NaN is refused
    mode = mode_name(out.get("geometry", "cylindrical"))
    out["geometry"] = mode
    data_dir = out.get("data_directory")
    out["detector"] = validate_model(mode, "detector", out.get("detector", []), data_directory=data_dir)
    out["sample"] = validate_model(mode, "sample", out.get("sample", []), data_directory=data_dir)

    task = out.get("task", "both")
    if task not in {"transfer", "summing", "both"}:
        raise CoincidenceError("Choose efficiency transfer, summing, or both")
    if task in {"transfer", "both"}:
        out["standard"] = validate_model(mode, "standard", out.get("standard", []), data_directory=data_dir)
        out["calibration"] = validate_calibration(out.get("calibration", []))

    if mode == "well":
        well_diameter = out["detector"][3]
        for kind in ("sample", "standard"):
            if kind in out and out[kind][0] > well_diameter:
                raise CoincidenceError(f"The {kind} container diameter ({out[kind][0]:g} mm) must fit "
                                       f"into the well diameter ({well_diameter:g} mm)")

    names = out.get("nuclides", [])
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise CoincidenceError("Nuclides must be a list")
    out["nuclides"] = normalize_nuclides(names)
    if task in {"summing", "both"} and not out["nuclides"]:
        raise CoincidenceError("Select at least one nuclide")
    if task in {"summing", "both"}:
        out["tcs_uncertainty"] = tcs_uncertainty.validate_settings(out.get("tcs_uncertainty"))

    workers = out.get("workers", 0)
    if type(workers) is not int or not 0 <= workers <= 64:
        raise CoincidenceError("Workers: enter 0 (automatic) or 1 to 64")
    out["workers"] = workers

    timeout = out.get("timeout_seconds", 300.)
    # Accept only a real number (not true/false, null or text) that is finite and positive.
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise CoincidenceError("timeout_seconds must be a positive number of seconds")
    out["timeout_seconds"] = float(timeout)
    return out


# ---------------------------------------------------------------------------
# Running one Fortran program
# ---------------------------------------------------------------------------

def engine_folder(mode: str) -> Path:
    """Folder of the Fortran programs of one engine, for this operating system."""
    target = "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"
    return ASSETS / mode / "bin" / target


def _stage(stage: str, mode: str, work: Path, stop, timeout: float, progress, provenance: dict) -> None:
    """Run one Fortran program (e.g. "total") in the folder ``work``.

    Its screen output goes to <stage>.log. The program's SHA-256 is recorded in
    ``provenance``. Cancel and the time limit are checked every 0.05 s.
    """
    if stop.is_set():
        raise CalculationCancelled("Calculation cancelled")
    program = engine_folder(mode) / (stage + (".exe" if os.name == "nt" else ""))
    if not program.is_file():
        raise CoincidenceError(f"Missing {MODES[mode]} engine '{stage}'. Run tools/build_engines.py for this platform.")
    if progress:
        progress(f"{MODES[mode]}: {stage}")
    provenance[stage] = sha256(program.read_bytes()).hexdigest()
    with (work / (stage + ".log")).open("wb") as log:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        process = subprocess.Popen([str(program.resolve())], cwd=work, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=log, shell=False, creationflags=flags)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if stop.is_set():
                    raise CalculationCancelled("Calculation cancelled")
                if time.monotonic() - started > timeout:
                    raise CoincidenceError(f"{stage}: time limit exceeded")
                try:
                    process.wait(timeout=.05)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            _terminate(process)
    if process.returncode:
        diagnostic = (work / (stage + ".log")).read_bytes()[-4000:].decode("utf-8", errors="replace")
        raise CoincidenceError(f"{stage} failed (exit {process.returncode}): {diagnostic}")


# ---------------------------------------------------------------------------
# Data folders and materials
# ---------------------------------------------------------------------------

def _user_data_directory(project: dict) -> Path:
    """The laboratory data folder of a run: the project's own "data_directory",
    otherwise the user's default data folder (paths.get_data_dir). New
    attenuation tables are saved there. Every part of a run (folder
    preparation, well model, provenance report) uses this one rule.
    """
    if project.get("data_directory"):
        return Path(project["data_directory"]).expanduser().resolve()
    from .paths import get_data_dir
    return get_data_dir()


def _material_roots(project: dict) -> list[Path]:
    """Material/Composition folders of a run, most specific first (bundled originals last)."""
    return material_roots(project.get("data_directory"))


def _data_fingerprint(roots: list[Path], engine_dir: Path, mode: str) -> dict:
    """SHA-256 of every data file a run uses: bundled Material/Composition files,
    replaced by the user's files of the same name (``roots``, most specific
    first), plus the engine tables."""
    hashes = {}
    for root in reversed(roots):
        for directory in ("Material", "Composition"):
            for path in sorted((root / directory).glob("*.txt")):
                hashes[f"{directory}/{path.name}"] = sha256(path.read_bytes()).hexdigest()
    for name in ("zzaa.txt", "param.txt", "kordaten.txt"):
        # Same choice as _prepare_folder: the lab's table, else the bundled one.
        for folder in (engine_dir, ASSETS / mode):
            if (folder / name).is_file():
                hashes[name] = sha256((folder / name).read_bytes()).hexdigest()
                break
    return hashes


# Attenuation tables already calculated by XCOM in this program session.
# Key: SHA-256 of the composition file. Avoids running XCOM twice for the same
# material (for example in the transfer and summing parts of one analysis).
_generated_tables = {}


def _attenuation_table(material: str, comp_file: Path, user_data: Path | None, stop=None, progress=None) -> bytes:
    """Attenuation table (Material file) of a material that only has a composition.

    It is calculated with XCOM, then also saved in the laboratory data folder
    (when there is one) so the next run can use it directly. It is never saved
    in the program's own folder, which belongs to the installation.
    """
    key = sha256(comp_file.read_bytes()).hexdigest()
    if key not in _generated_tables:
        from .materials import generate_attenuation, load_composition
        if progress:
            progress(f"Calculating attenuation table of '{material}' with XCOM")
        try:
            raw, _ = generate_attenuation(load_composition(comp_file, name=material), cancel=stop)
        except CalculationCancelled:
            raise
        except Exception as exc:
            raise CoincidenceError(f"Material '{material}' is missing from Material and automatic generation failed: {exc}") from exc
        _generated_tables[key] = raw
    raw = _generated_tables[key]
    if user_data and not user_data.is_dir():
        # Only the user's default data folder is created; a missing project folder
        # (e.g. a path from another PC) is left alone.
        from .paths import ensure_data_dir, get_data_dir
        if user_data == get_data_dir():
            try:
                ensure_data_dir(user_data)
            except OSError:
                pass
    if user_data and user_data.is_dir():
        target = user_data / "Material" / (material + ".txt")
        if not target.exists():
            try:
                target.parent.mkdir(exist_ok=True)
                _publish_new(target, raw)
            except OSError as exc:
                if progress:
                    progress(f"Could not save the attenuation table in {target}: {exc}")
    return raw


def _prepare_folder(mode: str, project: dict, destination: Path, source_kind: str, stop=None, progress=None) -> None:
    """Create a working folder with everything the engines read.

    It contains: the bundled original materials, overlaid by the user's own
    files (legacy, default, then project data folder), the engine tables, and
    the detector and source models under the file names the Fortran programs expect.
    """
    destination.mkdir()
    lab_data = _user_data_directory(project)
    engine_dir = lab_data if (lab_data / "Detector").is_dir() else ASSETS / mode

    for name in ("Material", "Composition"):
        (destination / name).mkdir()
        for root in reversed(_material_roots(project)):   # least specific first: later copies win
            if (root / name).is_dir():
                shutil.copytree(root / name, destination / name, dirs_exist_ok=True)
    for name in ("zzaa.txt", "param.txt", "kordaten.txt"):
        if (engine_dir / name).is_file():
            shutil.copyfile(engine_dir / name, destination / name)
        elif (ASSETS / mode / name).is_file():
            shutil.copyfile(ASSETS / mode / name, destination / name)
    if not (destination / "param.txt").exists():
        (destination / "param.txt").write_text("10.\n")

    # The Fortran programs use different file names for the same model.
    detector_bytes = model_bytes(mode, "detector", project["detector"])
    source_bytes = model_bytes(mode, source_kind, project[source_kind])
    for name in ("detector.txt", "det.txt"):
        (destination / name).write_bytes(detector_bytes)
    for name in ("source.txt", "src.txt"):
        (destination / name).write_bytes(source_bytes)
    for name in ("sample", "standard"):
        if project.get(name):
            (destination / (name + ".txt")).write_bytes(model_bytes(mode, name, project[name]))

    # Check every named material before running any numerical program.
    models = [project["detector"], project[source_kind]]
    if source_kind == "sample" and project.get("standard"):
        models.append(project["standard"])
    materials = [str(value) for model in models for value in model if isinstance(value, str)]
    for material in materials:
        comp_file = destination / "Composition" / (material + ".txt")
        mat_file = destination / "Material" / (material + ".txt")
        if mode == "well" and not comp_file.is_file():
            # The well model also reads the density from the Composition file.
            raise CoincidenceError(f"Material '{material}' is missing from {MODES[mode]} Composition")
        if mat_file.is_file():
            continue   # the Fortran engines only need the attenuation table (Material)
        if not comp_file.is_file():
            raise CoincidenceError(f"Material '{material}' is missing: no attenuation table (Material) "
                                   f"and no composition (Composition) to calculate it from")
        mat_file.write_bytes(_attenuation_table(material, comp_file, lab_data, stop, progress))


def _table(path: Path, columns: int) -> list[list[float]]:
    """A numeric result table written by a Fortran program."""
    rows = []
    for line in path.read_text().splitlines():
        values = [float(token.replace("D", "E")) for token in line.split()]
        if len(values) != columns or not all(math.isfinite(value) for value in values):
            raise CoincidenceError(f"Invalid result table: {path.name}")
        rows.append(values)
    if not rows:
        raise CoincidenceError(f"Empty result: {path.name}")
    return rows


# ---------------------------------------------------------------------------
# Result files
# ---------------------------------------------------------------------------

def _write_outputs(root: Path, result: dict) -> None:
    """Write results.json, efficiency.csv, summing.csv and report.html."""
    (root / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (root / "efficiency.csv").open("w", newline="", encoding="utf-8") as file:
        columns = ["energy_keV", "standard_efficiency", "sample_efficiency", "transfer_factor",
                   "sample_relative_uncertainty_percent_legacy"]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in result["efficiency"]:
            writer.writerow({key: row[key] for key in columns})
    with (root / "summing.csv").open("w", newline="", encoding="utf-8") as file:
        columns = ["nuclide", "energy_keV", "activity_multiplier", "status", *tcs_uncertainty.FIELDS]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        # An empty cell means "no uncertainty available" (uncorrected line or calculation disabled).
        writer.writerows({key: row.get(key) for key in columns} for row in result["summing"])
    (root / "report.html").write_text(render_report(result), encoding="utf-8")


def _html_rows(rows: list[dict], keys: list[str]) -> str:
    """Table rows (<tr>) with the given keys of each row."""
    escape = html.escape
    return "".join("<tr>" + "".join(f"<td>{escape(str(row[key]))}</td>" for key in keys) + "</tr>" for row in rows)


def _exports_table(result: dict) -> str:
    """HTML table listing the exported Genie / GammaVision files ("" when none)."""
    escape = html.escape
    rows = "".join(
        f"<tr><td style='text-align:left'><b>{escape(str(info.get('software', 'Genie')))}</b></td>"
        f"<td style='text-align:left'><code>{escape(str(info.get('file', '')))}</code></td>"
        f"<td><code>.{escape(str(info.get('format', kind)).upper())}</code></td>"
        f"<td>{escape(str(info.get('lines', '')))}</td>"
        f"<td>{'Yes' if info.get('roundtrip_verified') else 'No'}</td></tr>"
        for kind, info in (result.get("genie_exports") or {}).items() if isinstance(info, dict))
    if not rows:
        return ""
    return ("<h2>Exported Spectrometry Files (Genie 2000 / GammaVision)</h2>"
            "<table><tr><th style='text-align:left'>Target Software</th><th style='text-align:left'>Exported File</th>"
            "<th>Format</th><th>Lines / Points</th><th>Round-Trip Verified</th></tr>"
            f"{rows}</table>")


def _report_chart(result: dict) -> str:
    """The report's chart as inline SVG ("" when it cannot be drawn).

    matplotlib loads its SVG writer only inside savefig(), so a missing
    module can appear there too (for example in an installed build that does
    not bundle it). The chart is optional: the report is written without it
    rather than losing the whole result.
    """
    try:
        return _draw_report_chart(result)
    except ImportError:
        return ""


def _draw_report_chart(result: dict) -> str:
    """Draw the report's chart (see _report_chart)."""
    from matplotlib.figure import Figure
    figure = Figure(figsize=(9, 3.5), tight_layout=True)
    axis = figure.add_subplot(111)
    if result["efficiency"]:
        points = result["efficiency"]
        for key, label in [("standard_efficiency", "Standard"), ("sample_efficiency", "Sample")]:
            axis.loglog([r["energy_keV"] for r in points], [r[key] for r in points], "o-", label=label, markersize=3)
        axis.set_ylabel("Full-energy efficiency")
        axis.legend()
    else:
        for name in dict.fromkeys(r["nuclide"] for r in result["summing"]):
            points = [r for r in result["summing"] if r["nuclide"] == name and r["activity_multiplier"] is not None]
            if points:
                axis.scatter([r["energy_keV"] for r in points], [r["activity_multiplier"] for r in points], s=12, label=name)
        axis.set_yscale("log")
        axis.axhline(1, color="gray", linewidth=.8)
        axis.set_ylabel("Activity multiplier")
        axis.legend()
    axis.set_xlabel("Energy [keV]")
    axis.grid(True, which="both", alpha=.2)
    stream = io.StringIO()
    figure.savefig(stream, format="svg")
    text = stream.getvalue()
    return text[text.index("<svg"):]


REPORT_STYLE = ("body{font:16px Georgia,serif;max-width:1100px;margin:40px auto;color:#182532}"
                "table{border-collapse:collapse;width:100%;margin:20px 0}"
                "td,th{border:1px solid #ccd3d9;padding:7px;text-align:right}th{background:#edf2f6}"
                ".notice{background:#e8f4fd;border-left:4px solid #2563eb;padding:14px}svg{max-width:100%;height:auto}")


def _tcs_report_note(result: dict) -> str:
    """Paragraph explaining the TCS uncertainty column ("" when there is no summing)."""
    info = result.get("tcs_uncertainty")
    if not info:
        return ""
    if not info["enabled"]:
        return "<p>TCS uncertainty calculation was switched off for this job.</p>"
    s = info["settings"]
    monte_carlo = info.get("monte_carlo_relative_uncertainty_percent")
    mc_text = f" Monte Carlo statistical uncertainty of the efficiencies: {monte_carlo:.2g} %." if monte_carlo is not None else ""
    return ("<p><b>u(C)</b> is the relative standard uncertainty (k = 1) of the correction factor, propagated from "
            f"assumed relative uncertainties of the computed peak efficiency ({s['peak_efficiency_percent']:g} %) and "
            f"total efficiency ({s['total_efficiency_percent']:g} %), correlation {s['peak_total_correlation']:g}, "
            f"with sensitivity coefficients from ±{s['step_percent']:g} % curve scaling, plus the engine's numerical "
            f"uncertainty.{mc_text} Decay-data uncertainties are not included. See docs/TCS_UNCERTAINTY.md.</p>")


def _summing_display(rows: list[dict]) -> list[dict]:
    """Summing rows with u(C) as text ("–" when not available)."""
    return [{**row, "u_text": "–" if row.get("tcs_u_rel_percent") is None else f"{row['tcs_u_rel_percent']:.3g}"}
            for row in rows]


def render_report(result: dict) -> str:
    """The HTML report of one calculation."""
    escape = html.escape
    efficiency_rows = _html_rows(result["efficiency"], ["energy_keV", "standard_efficiency", "sample_efficiency", "transfer_factor"])
    summing_rows = _html_rows(_summing_display(result["summing"]), ["nuclide", "energy_keV", "activity_multiplier", "u_text", "status"])
    return (
        f'<!doctype html><html><meta charset="utf-8"><title>EffSuite result</title><style>{REPORT_STYLE}</style>'
        f"<h1>{escape(result['engine_name'])} — calculation result</h1>"
        f'<p class="notice">Beta build v{VERSION}. Experimental gamma spectrometry efficiency transfer and coincidence '
        "summing engine. Factors multiply activity; correction below one is permitted for summing-in.</p>"
        f"<p>Job: {escape(result['job_id'])}<br>Created: {escape(result['created'])}</p>"
        f"{_report_chart(result)}{_exports_table(result)}"
        "<h2>Efficiency transfer</h2><table><tr><th>E / keV</th><th>Standard efficiency</th><th>Sample efficiency</th>"
        f"<th>Transfer factor</th></tr>{efficiency_rows}</table>"
        "<h2>True coincidence summing</h2><table><tr><th>Nuclide</th><th>E / keV</th><th>Activity multiplier C</th>"
        f"<th>u(C) / % (k=1)</th><th>Status</th></tr>{summing_rows}</table>{_tcs_report_note(result)}"
        "<p>Original inputs, intermediate files and engine hashes are included with results.json. Legacy uncertainty "
        "percentages preserve the original transfer routine's assumptions; they are not a complete uncertainty budget.</p></html>")


# ---------------------------------------------------------------------------
# Step 1: efficiency transfer
# ---------------------------------------------------------------------------

def _well_transfer(project: dict, folder: Path, stop, progress, result: dict) -> list[list[float]]:
    """Well detector: ray-traced efficiencies of standard and sample; their ratio is the transfer.

    Returns rows [energy, sample efficiency, uncertainty %].
    """
    import numpy as np
    from .spatial_summing import _crystal_zz_aa, well_peak_efficiencies
    from .well_spatial import module_sha256
    energies = np.asarray([row["energy_keV"] for row in project["calibration"]], dtype=float)
    zz_aa = _crystal_zz_aa(folder, folder, project["detector"][5])
    efficiencies = {}
    for kind in ("standard", "sample"):
        if progress:
            progress(f"WEFFTRAN: ray-traced efficiency transfer ({kind})")
        efficiencies[kind] = well_peak_efficiencies(folder, project["detector"], project[kind], energies,
                                                    cancel=stop, zz_aa=zz_aa, workers=project["workers"])
    standard, sample = efficiencies["standard"], efficiencies["sample"]
    if np.any(standard <= 0) or np.any(~np.isfinite(sample / standard)):
        raise CoincidenceError("Standard well efficiency is zero")
    # The original WEFFTRAN adds fixed 0.5 % contributions for standard and sample.
    transferred = [[row["energy_keV"], row["efficiency"] * float(ratio), math.sqrt(row["u_rel_percent"]**2 + .5**2 + .5**2)]
                   for row, ratio in zip(project["calibration"], sample / standard)]
    (folder / "efficiency.txt").write_text("".join(f"{e:.5e} {v:.5e} {u:.5e}\n" for e, v, u in transferred))
    result["engine_sha256"]["well_transfer"] = module_sha256("spatial_summing.py")
    return transferred


def _fortran_transfer(mode: str, project: dict, folder: Path, stop, progress, result: dict) -> list[list[float]]:
    """Cylindrical / Marinelli: the original "total" and "transfer" Fortran programs."""
    for kind in ("sample", "standard"):
        source_bytes = model_bytes(mode, kind, project[kind])
        (folder / "source.txt").write_bytes(source_bytes)
        (folder / "src.txt").write_bytes(source_bytes)
        (folder / "total.txt").unlink(missing_ok=True)
        _stage("total", mode, folder, stop, project["timeout_seconds"], progress, result["engine_sha256"])
        shutil.copyfile(folder / "total.txt", folder / (kind + "-efficiency.txt"))
    _stage("transfer", mode, folder, stop, project["timeout_seconds"], progress, result["engine_sha256"])
    return _table(folder / "efficiency.txt", 3)


def _run_transfer(mode: str, project: dict, work: Path, stop, progress, result: dict) -> None:
    """Transfer the standard's calibration to the sample; fill result["efficiency"]."""
    folder = work / "transfer"
    _prepare_folder(mode, project, folder, "sample", stop, progress)
    calibration = project["calibration"]
    (folder / "reference.txt").write_text("".join(
        f"{row['energy_keV']:.17g} {row['efficiency']:.17g} {row['u_rel_percent']:.17g}\n" for row in calibration))
    if mode == "well":
        transferred = _well_transfer(project, folder, stop, progress, result)
    else:
        transferred = _fortran_transfer(mode, project, folder, stop, progress, result)

    if len(transferred) != len(calibration):
        raise CoincidenceError("Transferred calibration line count changed")
    for reference, (energy, efficiency, uncertainty) in zip(calibration, transferred):
        if efficiency <= 0 or efficiency > 1:
            raise CoincidenceError("Transferred efficiency is outside zero to one")
        if uncertainty < 0:
            raise CoincidenceError("Transferred relative uncertainty is negative")
        if not math.isclose(reference["energy_keV"], energy, rel_tol=1e-4, abs_tol=0.05):
            raise CoincidenceError("Transferred calibration energies changed beyond native single-precision print resolution")
        result["efficiency"].append({"energy_keV": reference["energy_keV"], "standard_efficiency": reference["efficiency"],
                                     "sample_efficiency": efficiency, "transfer_factor": efficiency / reference["efficiency"],
                                     "sample_relative_uncertainty_percent_legacy": uncertainty})

    if mode in ("cylindrical", "marinelli"):
        result["warnings"].append("Cylindrical and Marinelli transfer uncertainties add the Monte Carlo statistical uncertainty "
                                  "of the standard and sample efficiencies (EFFTRAN 5.0 / MEFFTRAN 1.9); well transfers retain "
                                  "the original hard-coded 0.5% standard/sample contributions; no complete uncertainty budget is claimed")
    else:
        result["warnings"].append("Well transfer uncertainties retain the original hard-coded 0.5% standard/sample "
                                  "contributions; no complete uncertainty budget is claimed")


# ---------------------------------------------------------------------------
# Step 2: coincidence summing
# ---------------------------------------------------------------------------

def _well_summing(project: dict, folder: Path, data_root: Path, stop, progress, result: dict) -> list[dict]:
    """Well detector: the ray-traced spatial model. Returns one row per gamma line."""
    from .well_spatial import calculate_spatial
    settings = project["tcs_uncertainty"]
    report = calculate_spatial(data_root, folder, tuple(project["nuclides"]), workers=project["workers"],
                               verify_serial=project.get("verify_serial", False),
                               check_convergence=project.get("check_convergence", True),
                               rtol=project.get("numerical_rtol", .01),
                               sensitivity_step=settings["step_percent"] / 100 if settings["enabled"] else None,
                               progress=progress, cancel=stop)
    result["well_spatial_diagnostics"] = report
    for failure in report.get("failed_nuclides", []):
        result["warnings"].append(f"{failure['nuclide']} was not corrected (its library lines are exported unchanged): "
                                  f"{failure['reason']}")
    rows = []
    for item in report["nuclides"]:
        for row in item["corrections"]:
            if settings["enabled"] and row["factor"] is not None:
                # Numerical term: the change of C when the quadrature is refined.
                uncertainty = tcs_uncertainty.line_uncertainty(row.get("sensitivity_peak"), row.get("sensitivity_total"),
                                                               settings, row.get("refinement_relative_change"))
            else:
                uncertainty = tcs_uncertainty.empty_fields()
            rows.append({"nuclide": item["nuclide"], "energy_keV": row["energy_kev"], "activity_multiplier": row["factor"],
                         "status": row["status"], **uncertainty})
    result["tcs_uncertainty"] = tcs_uncertainty.summary(settings, "change of C under x2 quadrature refinement (directions and "
                                                                  "sample points); omitted when the refinement check is off")
    if not report["convergence"]["passed"]:
        result["warnings"].append("Some well correction factors failed numerical refinement; do not export them to Genie or GammaVision")
    if report.get("missing_nuclides"):
        result["warnings"].append("Decay data not available for: " + ", ".join(report["missing_nuclides"])
                                  + ". These nuclides remain uncorrected (* in table).")
    return rows


def _cascade_summing(mode: str, project: dict, folder: Path, stop, progress, result: dict) -> list[dict]:
    """Cylindrical / Marinelli: the original Fortran "coincidence" program, one
    process per group of nuclides (see parallel_coincidence.py)."""
    for stage in PREP:
        _stage(stage, mode, folder, stop, project["timeout_seconds"], progress, result["engine_sha256"])
    program = engine_folder(mode) / ("coincidence.exe" if os.name == "nt" else "coincidence")
    show = (lambda done, total, name: progress(f"Nuclides {done}/{total}: {name}")) if progress else None
    inputs = SharedInputs.from_directory(folder)
    report = calculate_parallel(inputs, (str(program.resolve()),), workers=project["workers"],
                                nuclides=tuple(project["nuclides"]), cancel=stop,
                                verify_serial=project.get("verify_serial", False),
                                timeout_seconds=project["timeout_seconds"], progress=show)
    (folder / "coin.txt").write_bytes(report.coin_bytes)
    result["parallel_diagnostics"] = report.report
    if report.report.get("missing_nuclides"):
        result["warnings"].append("Decay data not available in EFFTRAN for: " + ", ".join(report.report["missing_nuclides"])
                                  + ". These nuclides remain uncorrected (* in table).")
    settings = project["tcs_uncertainty"]
    sensitivities, monte_carlo = {}, None
    if settings["enabled"]:
        if progress:
            progress("TCS uncertainty: efficiency sensitivity runs")

        def run(scaled):
            return calculate_parallel(scaled, (str(program.resolve()),), workers=project["workers"],
                                      nuclides=tuple(project["nuclides"]), cancel=stop,
                                      timeout_seconds=project["timeout_seconds"]).coin_bytes
        sensitivities = tcs_uncertainty.cascade_sensitivities(inputs, run, settings["step_percent"] / 100)
        monte_carlo = tcs_uncertainty.monte_carlo_uncertainty((folder / "total.txt").read_bytes())
    result["tcs_uncertainty"] = tcs_uncertainty.summary(
        settings, "Monte Carlo statistical uncertainty of the efficiency integration (largest value of column 4 "
                  "of total.txt), applied to peak and total efficiency together: u_num = |S_P + S_T| s_MC", monte_carlo)
    rows = []
    # coin.txt has fixed columns: nuclide (10 characters), energy (10), factor.
    for line in report.coin_bytes.splitlines():
        name, energy, factor = line[:10].decode().strip(), int(line[10:20]), float(line[20:])
        s_peak, s_total = sensitivities.get((name, energy), (None, None))
        if settings["enabled"] and factor > 0 and s_peak is not None and s_total is not None:
            numerical = None if monte_carlo is None else abs(s_peak + s_total) * monte_carlo
            uncertainty = tcs_uncertainty.line_uncertainty(s_peak, s_total, settings, numerical)
        else:
            uncertainty = tcs_uncertainty.empty_fields()
        rows.append({"nuclide": name, "energy_keV": energy, "activity_multiplier": factor if factor > 0 else None,
                     "status": "candidate" if factor > 0 else "invalid", **uncertainty})
    return rows


def _library_lines(project: dict, result: dict) -> list[dict] | None:
    """The gamma lines of the user's library: {"nuclide", "energy_keV"} rows.

    Taken from the project when the GUI or CLI already read them, otherwise
    read from the NLB/CTF file to export. None when there is no library.
    """
    rows = project.get("library_rows")
    exports = project.get("genie_exports")
    if rows or not exports:
        return rows
    from .software import read_certificate, read_library
    for kind, reader in (("nlb", read_library), ("ctf", read_certificate)):
        path = exports.get(kind)
        if path and Path(path).is_file():
            try:
                return [{"nuclide": str(r["nuclide"]), "energy_keV": float(r["energy"])} for r in reader(path)]
            except Exception as exc:
                # Keep going with the calculated factors, but tell the user why
                # the library lines could not be listed.
                result["warnings"].append(f"Could not read {Path(path).name}: {exc}")
            return rows   # only the first available file is used, as before
    return rows


def _match_library_lines(library_rows: list[dict], calculated: list[dict], missing: set[str],
                         uncertainty_enabled: bool = True) -> list[dict]:
    """One factor for every library line, from the calculated factors.

    A line gets the calculated factor of the same nuclide within 1 keV (the
    closest one). Otherwise it gets 1.0 with status:
    * "uncorrected": the nuclide was calculated but not this line, or its
      decay data is missing (a factor of 1 would be a guess);
    * "candidate": the nuclide has no coincidence at all (1.0 is correct).

    The TCS uncertainty fields follow the factor: copied from the matched
    line, None for an uncorrected line, zero for a line without coincidences.
    """
    matched = []
    for item in library_rows:
        nuclide = canonical_nuclide(item["nuclide"])   # a library may write "Co60" for "CO-60"
        energy = float(item["energy_keV"])
        label = str(item["nuclide"]).strip()
        nearby = [row for row in calculated if canonical_nuclide(row["nuclide"]) == nuclide and abs(row["energy_keV"] - energy) < 1.0]
        if nearby:
            closest = min(nearby, key=lambda row: abs(row["energy_keV"] - energy))
            factor = closest["activity_multiplier"]
            if factor is not None and factor > 0 and math.isfinite(factor) and closest.get("status") == "candidate":
                matched.append({"nuclide": label, "energy_keV": energy, "activity_multiplier": factor, "status": "candidate",
                                **{key: closest.get(key) for key in tcs_uncertainty.FIELDS}})
            else:
                matched.append({"nuclide": label, "energy_keV": energy, "activity_multiplier": 1.0, "status": "uncorrected",
                                **tcs_uncertainty.empty_fields()})
            continue
        nuclide_was_calculated = any(canonical_nuclide(row["nuclide"]) == nuclide for row in calculated)
        # I-129 below 35 keV: X-ray lines that the engines do not calculate.
        if nuclide_was_calculated or nuclide in missing or (nuclide == "I-129" and energy < 35):
            status = "uncorrected"
        else:
            status = "candidate"
        uncertainty = (tcs_uncertainty.zero_fields() if status == "candidate" and uncertainty_enabled
                       else tcs_uncertainty.empty_fields())
        matched.append({"nuclide": label, "energy_keV": energy, "activity_multiplier": 1.0, "status": status, **uncertainty})
    return matched


def _run_summing(mode: str, project: dict, work: Path, data_root: Path, stop, progress, result: dict) -> None:
    """Calculate the summing factors; fill result["summing"] (and result["raw_coin"])."""
    folder = work / "summing"
    _prepare_folder(mode, project, folder, "sample", stop, progress)
    if mode == "well":
        calculated = _well_summing(project, folder, data_root, stop, progress, result)
    else:
        calculated = _cascade_summing(mode, project, folder, stop, progress, result)
    library_rows = _library_lines(project, result)
    result["raw_coin"] = calculated
    if not library_rows:
        result["summing"] = calculated
        return
    missing = set()
    for key in ("parallel_diagnostics", "well_spatial_diagnostics"):
        if key in result:
            missing.update(canonical_nuclide(name) for name in result[key].get("missing_nuclides", []))
    result["summing"] = _match_library_lines(library_rows, calculated, missing, project["tcs_uncertainty"]["enabled"])


# ---------------------------------------------------------------------------
# Step 3: export and publish
# ---------------------------------------------------------------------------

def _export_files(project: dict, work: Path, result: dict, progress) -> None:
    """Write corrected copies of the user's Genie / GammaVision files into the results.

    A failed export is reported as a warning; the calculation result is kept.
    """
    from .software import detect, export_copy, label
    result["genie_exports"] = {}
    for kind, source in project["genie_exports"].items():
        if detect(source) == "gammavision":
            extension = {"cal": "EFT", "nlb": "LIB"}.get(kind, kind.upper())
        else:
            extension = kind.upper()
        if progress:
            progress(label(source) + ": exporting and reopening " + extension)
        target = work / (Path(source).stem + "_corrected." + extension)
        try:
            result["genie_exports"][kind] = export_copy(source, target, result, kind)
            result["genie_exports"][kind]["file"] = target.name
        except Exception as exc:
            result["warnings"].append(f"{label(source)} auto-export of {extension} skipped: {exc}")


def _publish_folder(work: Path, output: Path) -> None:
    """Move the finished working folder to its final name.

    Renaming is instant, but Windows sometimes holds a file for a moment (for
    example an antivirus scan), so we retry a few times, then fall back to copying.
    """
    for _ in range(5):
        try:
            os.rename(work, output)
            return
        except OSError:   # includes PermissionError
            time.sleep(0.08)
    shutil.copytree(work, output)
    shutil.rmtree(work, ignore_errors=True)


def run_project(project: dict, output: Path, *, cancel=None, progress=None) -> dict:
    """Run a complete calculation and save it in the NEW folder ``output``.

    ``cancel`` is an optional threading.Event to stop the calculation;
    ``progress`` an optional function that receives status messages.
    Returns the result dict (also saved as results.json).
    """
    project = validate_project(project)
    mode = project["geometry"]
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise CoincidenceError("Output folder already exists; choose a new name")
    output.parent.mkdir(parents=True, exist_ok=True)
    stop = cancel if cancel is not None else threading.Event()
    # Work in a hidden temporary folder next to the output; it only gets its
    # final name when everything succeeded.
    work = Path(tempfile.mkdtemp(prefix=".effsuite-job-", dir=output.parent))
    try:
        (work / "project.effsuite.json").write_text(json.dumps(project, indent=2) + "\n")
        result = {"schema_version": 1, "application_version": VERSION, "job_id": uuid4().hex[:12],
                  "created": datetime.now().astimezone().isoformat(), "geometry": mode, "engine_name": MODES[mode],
                  "qualification": "beta_build", "project": project,
                  "efficiency": [], "summing": [], "engine_sha256": {}, "warnings": [], "output_directory": str(output)}
        lab_data = _user_data_directory(project)
        data_root = lab_data if (lab_data / "Composition").is_dir() else COMMON_DATA
        engine_dir = lab_data if (lab_data / "Detector").is_dir() else ASSETS / mode
        result["scientific_data_directory"] = str(lab_data)
        result["scientific_data_sha256"] = _data_fingerprint(_material_roots(project), engine_dir, mode)

        if project["task"] in {"transfer", "both"}:
            _run_transfer(mode, project, work, stop, progress, result)
        if project["task"] in {"summing", "both"}:
            _run_summing(mode, project, work, data_root, stop, progress, result)
        if stop.is_set():
            raise CalculationCancelled("Calculation cancelled")

        result["all_reported_factors_valid"] = all(row["status"] == "candidate" and row["activity_multiplier"] is not None
                                                   for row in result["summing"])
        if "well_spatial_diagnostics" in result:
            diagnostic = result["well_spatial_diagnostics"]
            saturated = diagnostic["transport"]["probability_saturation_count"]
            if not diagnostic["convergence"]["passed"] or saturated:
                result["all_reported_factors_valid"] = False
                if saturated:
                    result["warnings"].append("Local response required probability saturation; review the well-model assumptions before use")
        if project.get("genie_exports"):
            _export_files(project, work, result, progress)
        _write_outputs(work, result)
        _publish_folder(work, output)
        return result
    finally:
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
