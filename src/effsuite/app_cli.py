"""Command-line interface: calculations (cylinder, marinelli, well, run, batch), plot-geometry, material, models, examples, config, doctor, check-update, gui."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import json
import multiprocessing
import os
import re
from pathlib import Path
import sys


from .model_io import ASSETS, COMMON_DATA, MODES, material_names, mode_name, find_model, read_model, calibration_rows, normalize_nuclides, default_material_density
from .parallel_coincidence import CoincidenceError, _publish_new
from .paths import get_results_dir, get_data_dir
from .suite import VERSION, engine_folder, run_project, validate_project


def default_output():
    """A new, time-stamped results folder name."""
    return get_results_dir() / (datetime.now().strftime("%Y%m%d_%H%M%S_%f"))


def default_data_dir():
    """The laboratory data folder (same as paths.get_data_dir)."""
    return get_data_dir()


def load_project(path):
    """Read and check a project file (.json)."""
    return validate_project(json.loads(Path(path).read_text(encoding="utf-8")))


def _add_tcs_uncertainty_args(c):
    """Options of the TCS (summing factor) uncertainty; None means "keep the project/default value"."""
    g = c.add_argument_group("TCS uncertainty (see docs/TCS_UNCERTAINTY.md)")
    g.add_argument("--tcs-u-peak", type=float, metavar="PERCENT",
                   help="Relative standard uncertainty of the computed peak efficiency (default 5)")
    g.add_argument("--tcs-u-total", type=float, metavar="PERCENT",
                   help="Relative standard uncertainty of the computed total efficiency (default 10)")
    g.add_argument("--tcs-correlation", type=float, metavar="RHO",
                   help="Correlation between peak and total efficiency errors, -1 to 1 (default 0)")
    g.add_argument("--no-tcs-uncertainty", action="store_true", help="Do not calculate u(C) (saves the four sensitivity runs)")


def _apply_tcs_uncertainty_args(project, args):
    """Put the TCS uncertainty options into project["tcs_uncertainty"] (checked by validate_project)."""
    settings = dict(project.get("tcs_uncertainty") or {})
    for option, key in (("tcs_u_peak", "peak_efficiency_percent"), ("tcs_u_total", "total_efficiency_percent"),
                        ("tcs_correlation", "peak_total_correlation")):
        if getattr(args, option, None) is not None:
            settings[key] = getattr(args, option)
    if getattr(args, "no_tcs_uncertainty", False):
        settings["enabled"] = False
    if settings:
        project["tcs_uncertainty"] = settings
    return project


def _add_common_calc_args(c):
    """Command-line options shared by the cylinder, marinelli and well commands."""
    c.add_argument("--detector", required=True, help="Detector model (.txt path or name in Data/Detector)")
    c.add_argument("--sample", required=True, help="Sample model (.txt path or name in Data/Sample or Data/Standard)")
    c.add_argument("--sample-height", type=float, metavar="MM", help="Override sample filling height [mm]")
    c.add_argument("--sample-diameter", type=float, metavar="MM", help="Override sample container outer diameter [mm]")
    c.add_argument("--sample-gap", type=float, metavar="MM", help="Override sample-to-detector positioning gap [mm]")
    c.add_argument("--sample-material", metavar="NAME", help="Override sample matrix material name")
    c.add_argument("--sample-density", type=float, metavar="G_CM3", help="Override sample matrix bulk density [g/cm³] (line 8 of the source model; attenuation is scaled by rho/rho0)")
    c.add_argument("--container-material", metavar="NAME", help="Override sample container material name")
    c.add_argument("--standard", help="Reference standard source model (.txt path or name in Data/Standard)")
    c.add_argument("--calibration", type=Path, metavar="FILE", help="Reference efficiency .CAL, .EFT, .txt or .csv (in Data/Calibration)")
    c.add_argument("--export-cal", action="store_true", help="Export the transferred sample calibration: Genie .CAL or GammaVision .EFT (automatic when --calibration is a .CAL/.EFT file)")
    c.add_argument("--cal-template", type=Path, metavar="FILE", help="Genie .CAL or GammaVision .EFT template when using a .txt/.csv calibration")
    c.add_argument("--library", type=Path, metavar="FILE", help="Genie nuclide library (.NLB) or GammaVision library (.LIB) to export with summing corrections")
    c.add_argument("--certificate", type=Path, metavar="FILE", help="Genie certificate (.CTF) to export with summing corrections")
    c.add_argument("--nuclides", nargs="+", default=[], metavar="Co-60", help="One or more nuclides (comma or space separated)")
    c.add_argument("--output-cal", type=Path, metavar="FILE", help="Also copy the exported sample .CAL / .EFT to this file")
    c.add_argument("--output-nlb", type=Path, metavar="FILE", help="Also copy the exported corrected .NLB / .LIB to this file")
    c.add_argument("--output-ctf", type=Path, metavar="FILE.CTF", help="Also copy the exported corrected .CTF to this file")
    c.add_argument("--plot-geometry", nargs="?", const="geometry.png", metavar="PNG_OR_PDF", help="Save the axial cross-section drawing with all dimensions (default: geometry.png in the result folder)")
    c.add_argument("--out", type=Path, metavar="DIR", help="Result folder (default: <EffSuite user folder>/Results/<timestamp>)")
    c.add_argument("--save-project", type=Path, metavar="FILE", help="Save the resolved project JSON, to repeat the run with 'effsuite run'")
    c.add_argument("--workers", type=int, metavar="N", default=0, help="Worker processes: 0 = automatic, 1 = serial")
    c.add_argument("--software", choices=["genie", "gammavision"], help="Library software (default: auto-detect; .LIB = GammaVision)")
    c.add_argument("--data-dir", type=Path, metavar="DIR", help="Data directory (default: your data folder, see 'config')")
    c.add_argument("--verify-serial", action="store_true", help="Check the parallel summing results against a serial run")
    _add_tcs_uncertainty_args(c)


def parser():
    """The complete command-line definition (all commands and options)."""
    p = argparse.ArgumentParser(
        description="EffSuite: efficiency transfer and coincidence summing with EFFTRAN, MEFFTRAN and WEFFTRAN.\nBuilt by ChatGPT, Gemini and Claude under the supervision of G. Lutter."
    )
    p.add_argument("--version", action="version", version=f"EffSuite {VERSION} (built by ChatGPT, Gemini and Claude under the supervision of G. Lutter)")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("gui", help="Open the desktop graphical interface")
    sub.add_parser("doctor", help="Check dependencies and bundled engines")
    sub.add_parser("check-update", help="Report whether a newer release is on GitHub")

    material = sub.add_parser("material", help="Create or update material composition and XCOM attenuation files")
    material.add_argument("--input", type=Path, metavar="FILE", help="Composition JSON, original .txt, Material.xls or XLSX template")
    material.add_argument("--name", help="Material name (e.g. Glucose, Salt_water)")
    material.add_argument("--density", type=float, help="Bulk density in g/cm³ (e.g. 1.346)")
    material.add_argument("--compound", action="append", default=[], metavar="H2O=90", help="Chemical formula and relative weight; repeat for mixtures")
    material.add_argument("--geometry", choices=("cylinder", "marinelli", "well"), default="cylinder")
    material.add_argument("--library", type=Path, metavar="DIR", help="Output data folder (default: your data folder, see 'config')")
    material.add_argument("--base-data", type=Path, metavar="DIR", help="Folder to copy into a new, empty output data folder (default: none)")
    material.add_argument("--save-definition", type=Path, metavar="FILE", help="Also save the composition definition as JSON")
    material.add_argument("--overwrite", action="store_true", help="Overwrite an existing material and recalculate its XCOM attenuation")

    config = sub.add_parser("config", help="Show or change the default data folder (your own materials and models)")
    config_group = config.add_mutually_exclusive_group()
    config_group.add_argument("--data-dir", type=Path, metavar="DIR", help="Save this folder as the default data folder (Composition and Material are created)")
    config_group.add_argument("--reset-data-dir", action="store_true", help="Go back to the built-in default (<EffSuite root>/Data)")

    examples = sub.add_parser("examples", help="List or run the built-in example projects")
    examples.add_argument("--run", choices=("cylinder", "marinelli", "well"))

    models = sub.add_parser("models", help="List available detector, sample, standard, and material names")
    models.add_argument("geometry", choices=("cylinder", "marinelli", "well"))
    models.add_argument("--data-dir", type=Path, metavar="DIR", help="Data directory to inspect (default: your data folder, see 'config')")

    plot_cmd = sub.add_parser("plot-geometry", help="Save the axial cross-section drawing with all dimensions as PNG, PDF or SVG")
    plot_cmd.add_argument("--geometry", choices=("cylinder", "marinelli", "well", "cylindrical", "efftran", "mefftran", "wefftran"), default="cylinder")
    plot_cmd.add_argument("--detector", required=True, help="Detector model file or name")
    plot_cmd.add_argument("--sample", help="Sample model file or name")
    plot_cmd.add_argument("--standard", help="Standard model file or name (if plotting Standard)")
    plot_cmd.add_argument("--kind", choices=("Sample", "Standard", "Detector"), default="Sample")
    plot_cmd.add_argument("--sample-height", type=float, help="Override sample filling height [mm]")
    plot_cmd.add_argument("--sample-gap", type=float, help="Override positioning gap [mm]")
    plot_cmd.add_argument("--data-dir", type=Path, metavar="DIR", help="Data directory")
    plot_cmd.add_argument("--out", type=Path, metavar="FILE", required=True, help="Output image file (.png, .pdf, .svg)")

    batch_cmd = sub.add_parser("batch", help="Run batch calculations from a CSV or JSON table of samples")
    batch_cmd.add_argument("batch_file", nargs="?", type=Path, help="CSV or JSON file describing the batch jobs")
    batch_cmd.add_argument("--template", type=Path, metavar="CSV_PATH", help="Write a batch CSV template and exit")
    batch_cmd.add_argument("--out", type=Path, metavar="DIR", help="Output folder for all batch jobs and batch_summary.csv/.json")
    batch_cmd.add_argument("--workers", type=int, metavar="N", default=0, help="Worker processes per job (0 = automatic)")
    batch_cmd.add_argument("--data-dir", type=Path, metavar="DIR", help="Default data directory for the batch")
    batch_cmd.add_argument("--plot-geometry", action="store_true", help="Also save geometry.png with all dimensions for each sample")

    run = sub.add_parser("run", help="Execute a saved GUI/CLI project JSON (with optional CLI overrides)")
    run.add_argument("project", type=Path)
    run.add_argument("--out", type=Path)
    run.add_argument("--workers", type=int)
    run.add_argument("--sample-height", type=float, metavar="MM", help="Override sample filling height [mm]")
    run.add_argument("--sample-material", metavar="NAME", help="Override sample matrix material")
    run.add_argument("--sample-density", type=float, metavar="G_CM3", help="Override sample bulk density [g/cm³]")
    run.add_argument("--output-cal", type=Path, metavar="FILE", help="Copy exported Sample .CAL to this path")
    run.add_argument("--output-nlb", type=Path, metavar="FILE", help="Copy exported corrected .NLB to this path")
    run.add_argument("--output-ctf", type=Path, metavar="FILE", help="Copy exported corrected .CTF to this path")
    run.add_argument("--plot-geometry", nargs="?", const="geometry.png", help="Save the cross-section drawing")
    _add_tcs_uncertainty_args(run)

    for name, aliases in [("cylinder", ["efftran"]), ("marinelli", ["mefftran"]), ("well", ["wefftran"])]:
        c = sub.add_parser(name, aliases=aliases, help=f"Run a {name} calculation from model files or names, with overrides")
        _add_common_calc_args(c)
    return p


def doctor():
    """Check that Python packages, engines and XCOM are installed; print a report."""
    import importlib.util
    checks = {name:importlib.util.find_spec(name) is not None for name in ("numpy", "matplotlib", "xlrd", "PySide6")}
    engines = {}
    for mode in MODES:
        folder = engine_folder(mode)
        suffix = ".exe" if os.name=="nt" else ""
        stages = ["mine", "energy", "total", "scatter", "buildup", "eta", "ptt", "efficiency", "transfer"]+([] if mode=="well" else ["coincidence"])
        engines[MODES[mode]] = {name:(folder/(name+suffix)).is_file() for name in stages}
    from .materials import XCOM, TEMPLATE
    target = "windows" if os.name=="nt" else "macos" if sys.platform=="darwin" else "linux"
    materials = {"xcom":(XCOM/"bin"/target/("xcom.exe" if os.name=="nt" else "xcom")).is_file(), "excel_template":TEMPLATE.is_file(), "element_data":len(list(XCOM.glob("MDATX3.*")))==100}
    return {"version":VERSION, "python":sys.version, "interpreter":sys.executable, "dependencies":checks, "engines":engines, "materials":materials,
            "qualification":"Beta Build; experimental qualification pending. Verify installation against reference data"}


def example_path(name):
    """Path of a built-in example project ("cylinder", "marinelli" or "well")."""
    return Path(__file__).parent/"assets/examples"/(name+".effsuite.json")


def _resolve_file(path_or_name, subfolder, data_dir):
    """Find an input file: as given, else in the data folders' ``subfolder``."""
    if not path_or_name:
        return None
    p = Path(path_or_name).expanduser()
    if p.is_file():
        return p.resolve()
    search = []
    if data_dir:
        d = Path(data_dir).expanduser()
        search.extend([d/subfolder/p.name, d/p.name])
    default_d = default_data_dir()
    if default_d:
        search.extend([default_d/subfolder/p.name, default_d/p.name])
    for candidate in search:
        if candidate.is_file():
            return candidate.resolve()
    raise CoincidenceError(f"File not found: {path_or_name} (also looked in the {subfolder} data folders)")


def _apply_sample_overrides(mode, sample_values, *, height=None, diameter=None, gap=None, material=None, density=None, container_material=None, data_dir=None, progress=None):
    """Apply --sample-height, --sample-material ... to a sample model."""
    out = list(sample_values)
    if len(out)==7:
        out.append(default_material_density(out[5], data_dir))
    if diameter is not None:
        out[0] = float(diameter)
    if height is not None:
        idx = 2 if mode=="marinelli" else 1
        out[idx] = float(height)
    if gap is not None and mode!="marinelli":
        out[4] = float(gap)
    if material:
        out[5] = str(material).strip()
        if density is None:
            out[7] = default_material_density(out[5], data_dir)
    if container_material:
        out[6] = str(container_material).strip()
    if density is not None:
        out[7] = float(density)
    return out


def _save_geometry_plot(project, dest_path, kind="Sample"):
    """Save a picture of the geometry (PNG) and return its path."""
    import matplotlib.pyplot as plt
    from .geometry_view import draw_geometry
    mode = project["geometry"]
    d = project["detector"]
    s = project.get("standard") if kind=="Standard" else project.get("sample") if kind=="Sample" else None
    fig = plt.figure(figsize=(10.5, 6.4))
    ax = fig.add_subplot(111)
    fig.subplots_adjust(left=.08, right=.66, bottom=.10, top=.92)
    draw_geometry(ax, mode, d, s, kind, compact=False)
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=150)
    plt.close(fig)
    return str(dest.resolve())


def _export_path(result, kind):
    """Path of the exported file for kind ('cal','nlb','ctf') inside the published output directory."""
    info = (result.get("genie_exports") or {}).get(kind)
    if isinstance(info, dict) and info.get("file") and result.get("output_directory"):
        path = Path(result["output_directory"])/info["file"]
        return str(path) if path.is_file() else ""
    return ""


def _copy_direct_outputs(result, *, output_cal=None, output_nlb=None, output_ctf=None):
    """Copy the verified exports to the paths given with --output-cal/-nlb/-ctf.

    Existing files are never overwritten. Asking for an output that the run
    could not produce is an error (the warnings say why), not a silent skip.
    """
    copied = {}
    for key, target in [("cal", output_cal), ("nlb", output_nlb), ("ctf", output_ctf)]:
        if not target:
            continue
        source = _export_path(result, key)
        if not source:
            reasons = "; ".join(w for w in result.get("warnings", []) if "export" in w.lower()) or "no source file for this export"
            raise CoincidenceError(f"--output-{key}: the corrected {key.upper()} file was not produced ({reasons})")
        target_path = Path(target).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _publish_new(target_path, Path(source).read_bytes())
        except FileExistsError as exc:
            raise CoincidenceError(f"--output-{key}: {target_path} already exists; choose a new file name") from exc
        copied[key+"_output"] = str(target_path)
    if copied:
        result["direct_outputs"] = copied


def _build_project_from_args(mode, args, progress=None):
    """Turn the command-line options of one calculation into a checked project."""
    data_dir = args.data_dir or default_data_dir()
    cal_path = _resolve_file(args.calibration, "Calibration", data_dir) if args.calibration else None
    nlb_path = _resolve_file(args.library, "NuclideLibrary", data_dir) if args.library else None
    ctf_path = _resolve_file(args.certificate, "Certificates", data_dir) if args.certificate else None
    has_transfer = cal_path is not None and bool(args.standard)
    if (cal_path is not None) != bool(args.standard) and not (args.nuclides or nlb_path or ctf_path):
        raise CoincidenceError("Efficiency transfer needs both --standard and --calibration")
    names = normalize_nuclides(args.nuclides)
    genie_sources = {}
    # Lines of the library AND the certificate: every line of both files must
    # get its correction factor, not only the lines of the first file.
    lib_records = []
    for kind, path in (("nlb", nlb_path), ("ctf", ctf_path)):
        if path:
            from .software import read_library, read_certificate
            rows = (read_library if kind=="nlb" else read_certificate)(path)
            names = normalize_nuclides(names+[str(row["nuclide"]) for row in rows])
            genie_sources[kind] = str(path.resolve())
            for row in rows:
                record = {"nuclide":str(row["nuclide"]), "energy_keV":float(row["energy"])}
                if record not in lib_records:
                    lib_records.append(record)
    if not has_transfer and not names:
        raise CoincidenceError("Add --nuclides / --library / --certificate for summing, or --standard and --calibration for efficiency transfer")
    det_values = read_model(mode, "detector", find_model(mode, "detector", args.detector, data_dir))
    smp_values = read_model(mode, "sample", find_model(mode, "sample", args.sample, data_dir))
    smp_values = _apply_sample_overrides(
        mode, smp_values,
        height=args.sample_height, diameter=args.sample_diameter, gap=args.sample_gap,
        material=args.sample_material, density=args.sample_density, container_material=args.container_material,
        data_dir=data_dir, progress=progress,
    )
    project = {
        "schema_version":1,
        "geometry":mode,
        "task":"both" if names and has_transfer else "transfer" if has_transfer else "summing",
        "detector":det_values,
        "sample":smp_values,
        "nuclides":names,
        "workers":args.workers,
        "verify_serial":args.verify_serial,
    }
    if lib_records:
        project["library_rows"] = lib_records
    if has_transfer:
        project["standard"] = read_model(mode, "standard", find_model(mode, "standard", args.standard, data_dir))
        project["calibration"] = calibration_rows(cal_path)
        if cal_path.suffix.lower() in {".cal", ".eft"}:
            project["calibration_template"] = str(cal_path.resolve())
        if args.cal_template:
            tpl = _resolve_file(args.cal_template, "Calibration", data_dir)
            project["calibration_template"] = str(tpl.resolve())
        if project.get("calibration_template") and (args.export_cal or args.output_cal or cal_path.suffix.lower() in {".cal", ".eft"}):
            genie_sources["cal"] = project["calibration_template"]
    if (args.export_cal or args.output_cal) and "cal" not in genie_sources:
        raise CoincidenceError("--export-cal/--output-cal need --standard and a .CAL/.EFT calibration input or --cal-template")
    if genie_sources:
        project["genie_exports"] = genie_sources
    _apply_tcs_uncertainty_args(project, args)
    project = validate_project(project)
    if data_dir:
        project["data_directory"] = str(Path(data_dir).resolve())
    return project


BATCH_COLUMNS = [
    "id", "geometry", "detector", "sample", "sample_height_mm", "sample_material", "sample_density_g_cm3", "sample_gap_mm",
    "standard", "calibration", "library", "certificate", "nuclides", "output_cal", "output_nlb", "output_ctf"
]


def _run_batch(args, progress):
    """Run every job of a batch CSV/JSON file and write a batch summary."""
    if args.template:
        tpl = Path(args.template)
        tpl.parent.mkdir(parents=True, exist_ok=True)
        with tpl.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(BATCH_COLUMNS)
            w.writerow(["Sample_001", "cylinder", "High-energy", "Water", "33.4", "water", "1.0", "0", "Solution", "TF400_268_2025.CAL", "LIBRARY.NLB", "", "", "Sample_001.CAL", "Sample_001.NLB", ""])
        print(f"Created batch template: {tpl}", file=sys.stderr)
        return 0
    if not args.batch_file or not args.batch_file.is_file():
        raise CoincidenceError("Provide a batch CSV or JSON file (or use --template batch.csv to generate one)")
    if args.batch_file.suffix.lower()==".json":
        jobs = json.loads(args.batch_file.read_text(encoding="utf-8"))
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs", [])
    else:
        with args.batch_file.open("r", newline="", encoding="utf-8-sig") as f:
            jobs = [row for row in csv.DictReader(f) if any(v and str(v).strip() for v in row.values())]
    if not jobs:
        raise CoincidenceError("No jobs found in batch file")
    master_out = args.out or (get_results_dir()/("Batch_"+datetime.now().strftime("%Y%m%d_%H%M%S")))
    master_out.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    all_ok = True
    used_ids = set()
    for idx, row in enumerate(jobs, 1):
        # The id becomes a folder name: keep only safe characters, and make it unique.
        job_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(row.get("id") or f"Job_{idx:03d}").strip()).strip("._") or f"Job_{idx:03d}"
        if job_id in used_ids:
            job_id = f"{job_id}_{idx:03d}"
        used_ids.add(job_id)
        geom = mode_name(str(row.get("geometry") or "cylinder").strip())
        progress(f"[{idx}/{len(jobs)}] Running batch job '{job_id}' ({geom})...")
        # A failing job is recorded in the summary; the other jobs still run.
        try:
            job_ns = argparse.Namespace(
                detector=str(row.get("detector") or "").strip(),
                sample=str(row.get("sample") or "").strip(),
                sample_height=float(row["sample_height_mm"]) if str(row.get("sample_height_mm") or "").strip() else None,
                sample_diameter=float(row["sample_diameter_mm"]) if str(row.get("sample_diameter_mm") or "").strip() else None,
                sample_gap=float(row["sample_gap_mm"]) if str(row.get("sample_gap_mm") or "").strip() else None,
                sample_material=str(row.get("sample_material") or "").strip() or None,
                sample_density=float(row["sample_density_g_cm3"]) if str(row.get("sample_density_g_cm3") or "").strip() else None,
                container_material=str(row.get("container_material") or "").strip() or None,
                standard=str(row.get("standard") or "").strip() or None,
                calibration=Path(row["calibration"].strip()) if str(row.get("calibration") or "").strip() else None,
                export_cal=Path(str(row.get("calibration") or "").strip()).suffix.lower() in {".cal", ".eft"},
                cal_template=None,
                library=Path(row["library"].strip()) if str(row.get("library") or "").strip() else None,
                certificate=Path(row["certificate"].strip()) if str(row.get("certificate") or "").strip() else None,
                nuclides=[s.strip() for s in str(row.get("nuclides") or "").split(",") if s.strip()],
                output_cal=Path(row["output_cal"].strip()) if str(row.get("output_cal") or "").strip() else None,
                output_nlb=Path(row["output_nlb"].strip()) if str(row.get("output_nlb") or "").strip() else None,
                output_ctf=Path(row["output_ctf"].strip()) if str(row.get("output_ctf") or "").strip() else None,
                workers=args.workers,
                data_dir=args.data_dir,
                verify_serial=False,
            )
            job_out = master_out/job_id
            project = _build_project_from_args(geom, job_ns, progress=progress)
            res = run_project(project, job_out, progress=progress)
            _copy_direct_outputs(res, output_cal=job_ns.output_cal, output_nlb=job_ns.output_nlb, output_ctf=job_ns.output_ctf)
            if args.plot_geometry:
                res["geometry_plot"] = _save_geometry_plot(project, job_out/"geometry.png")
            all_ok = all_ok and bool(res.get("all_reported_factors_valid", True))
            exports = res.get("genie_exports") or {}
            summary_rows.append({
                "id":job_id,
                "geometry":geom,
                "task":project["task"],
                "sample_material":project["sample"][5],
                "sample_height_mm":project["sample"][2 if geom=="marinelli" else 1],
                "output_directory":res["output_directory"],
                "cal_output":res.get("direct_outputs", {}).get("cal_output") or _export_path(res, "cal"),
                "nlb_output":res.get("direct_outputs", {}).get("nlb_output") or _export_path(res, "nlb"),
                "ctf_output":res.get("direct_outputs", {}).get("ctf_output") or _export_path(res, "ctf"),
                "valid":res.get("all_reported_factors_valid", True),
            })
        except (CoincidenceError, OSError, ValueError, KeyError) as exc:
            all_ok = False
            progress(f"[{idx}/{len(jobs)}] Job '{job_id}' failed: {exc}")
            summary_rows.append({"id":job_id, "geometry":geom, "valid":False, "error":str(exc)})
    summary_csv = master_out/"batch_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        # Failed jobs have fewer columns: collect every column name, in order.
        fieldnames = list(dict.fromkeys(key for row in summary_rows for key in row))
        w = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        w.writeheader()
        w.writerows(summary_rows)
    summary_json = master_out/"batch_summary.json"
    summary_json.write_text(json.dumps({"batch_directory":str(master_out.resolve()), "jobs":summary_rows}, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"batch_directory":str(master_out.resolve()), "summary_csv":str(summary_csv.resolve()), "jobs":summary_rows}, indent=2))
    return 0 if all_ok else 1


def print_cli_banner():
    """Print the program banner (name, version, engines, disclaimer)."""
    print("=" * 72)
    print("                 EffSuite gamma spectrometry CLI")
    print(f"       Efficiency transfer and true coincidence summing (v{VERSION})")
    print("       EFFTRAN 5.0 • MEFFTRAN 1.9 • WEFFTRAN • NIST XCOM")
    print("=" * 72)
    print(" Supervisor : G. Lutter")
    print(" Built by   : ChatGPT, Gemini and Claude")
    print(" Disclaimer : Provided strictly AS-IS; users must verify analytical results.")
    print("=" * 72)
    print()


def _pause_if_interactive():
    """Keep console window open on Windows when launched interactively."""
    if sys.stdin.isatty():
        try:
            input("\nPress Enter to continue…")
        except (KeyboardInterrupt, EOFError):
            pass


def _run_interactive_project(path: Path):
    """Interactive menu: run one project file and show where the results are."""
    print(f"\n--- Running project: {path.name} ---")
    progress = lambda s: print(s, file=sys.stderr, flush=True)
    out_dir = default_output()
    try:
        project = load_project(path)
        result = run_project(project, out_dir, progress=progress)
        print(f"\n[SUCCESS] Calculation complete. Results saved to:\n  {result['output_directory']}")
        print(f"  All reported factors valid: {result['all_reported_factors_valid']}")
    except Exception as exc:
        print(f"\n[ERROR] Calculation failed: {exc}", file=sys.stderr)
        _pause_if_interactive()
        return 2   # same exit code as the non-interactive command line
    _pause_if_interactive()
    return 0 if result["all_reported_factors_valid"] else 1


def _run_interactive_batch(path: Path):
    """Interactive menu: run a batch file."""
    print(f"\n--- Batch run: {path.name} ---")
    progress = lambda s: print(s, file=sys.stderr, flush=True)
    class BatchArgs:
        batch_file = path
        out = default_output()
        workers = 0
        data_dir = None
        plot_geometry = False
        template = None
    try:
        ret = _run_batch(BatchArgs(), progress)
        print(f"\n[SUCCESS] Batch run complete (exit code {ret}).")
    except Exception as exc:
        print(f"\n[ERROR] Batch run failed: {exc}", file=sys.stderr)
        _pause_if_interactive()
        return 2
    _pause_if_interactive()
    return ret


def _run_interactive_example(name: str):
    """Interactive menu: run a built-in example."""
    ex_file = example_path(name)
    print(f"\n--- Built-in example: {name.title()} ({ex_file.name}) ---")
    return _run_interactive_project(ex_file)


def interactive_cli():
    """Interactive console menu when EffSuite_CLI is launched with no arguments."""
    print_cli_banner()
    while True:
        print("Operations:")
        print("  [1] Run a saved project (.json), or drop a file here")
        print("  [2] Run a batch (.csv / .json table)")
        print("  [3] Run a built-in validation example (cylinder / Marinelli / well)")
        print("  [4] Check dependencies and engines (doctor)")
        print("  [5] Show command line help (--help)")
        print("  [6] Open the desktop GUI")
        print("  [0] Exit")
        print()
        try:
            choice = input("Select an option [0-6] or enter a file path: ").strip().strip('"').strip("'")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            return 0

        if not choice:
            continue

        candidate_path = Path(choice)
        if candidate_path.is_file():
            if candidate_path.suffix.lower() == ".json":
                return _run_interactive_project(candidate_path)
            elif candidate_path.suffix.lower() == ".csv":
                return _run_interactive_batch(candidate_path)
            else:
                print(f"[ERROR] Unsupported file format '{candidate_path.suffix}'. Expected .json or .csv\n")
                continue

        if choice == "1":
            try:
                p_in = input("Path to the project .json file (or drop it here): ").strip().strip('"').strip("'")
            except (KeyboardInterrupt, EOFError):
                return 0
            if not p_in:
                print("No file specified.\n")
                continue
            path = Path(p_in)
            if not path.is_file():
                print(f"[ERROR] File not found: {path}\n")
                continue
            return _run_interactive_project(path)

        elif choice == "2":
            try:
                b_in = input("Path to the batch .csv or .json file: ").strip().strip('"').strip("'")
            except (KeyboardInterrupt, EOFError):
                return 0
            if not b_in:
                print("No file specified.\n")
                continue
            path = Path(b_in)
            if not path.is_file():
                print(f"[ERROR] File not found: {path}\n")
                continue
            return _run_interactive_batch(path)

        elif choice == "3":
            print("\nBuilt-in validation examples:")
            print("  [c] Cylindrical sample on coaxial detector")
            print("  [m] Marinelli beaker geometry")
            print("  [w] Well-type detector geometry")
            try:
                ex_choice = input("Choose example [c/m/w]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return 0
            mapping = {"c": "cylinder", "cylinder": "cylinder",
                       "m": "marinelli", "marinelli": "marinelli",
                       "w": "well", "well": "well"}
            ex_name = mapping.get(ex_choice)
            if not ex_name:
                print("Invalid example choice.\n")
                continue
            return _run_interactive_example(ex_name)

        elif choice == "4":
            print("\nChecking dependencies and engines…\n")
            doc = doctor()
            print(json.dumps(doc, indent=2))
            _pause_if_interactive()
            print()
            continue

        elif choice == "5":
            print()
            parser().print_help()
            _pause_if_interactive()
            print()
            continue

        elif choice == "6":
            print("\nOpening the GUI…\n")
            from .gui import main as gui_main
            return gui_main()

        elif choice in {"0", "q", "exit", "quit"}:
            print("Goodbye.")
            return 0

        else:
            print(f"Unknown option '{choice}'. Choose 0 to 6.\n")


def _command_doctor(args):
    """doctor: check the installation and print a report."""
    result = doctor()
    print(json.dumps(result, indent=2))
    return 0 if all(all(v.values()) for v in result["engines"].values()) and all(result["materials"].values()) and all(result["dependencies"][name] for name in ("numpy", "matplotlib", "xlrd")) else 1


def _command_material(args, progress):
    """material: create a material (composition + XCOM attenuation table)."""
    from .materials import load_composition, validate_composition, create_material, default_library, save_definition
    definition = load_composition(args.input) if args.input else {"schema_version":1, "components":[]}
    if args.name:
        definition["name"] = args.name
    if args.density is not None:
        definition["density_g_cm3"] = args.density
    if args.compound:
        if args.input:
            raise CoincidenceError("Use --input or --compound; override density/name explicitly if needed")
        rows = []
        for value in args.compound:
            if value.count("=")!=1:
                raise CoincidenceError("Compound syntax: --compound H2O=90 --compound NaCl=10")
            formula, weight = value.split("=")
            rows.append({"formula":formula, "weight":weight})
        definition["components"] = rows
    definition = validate_composition(definition)
    if args.save_definition and args.save_definition.exists():
        raise CoincidenceError("Definition output exists; choose a new filename")
    result = create_material(definition, args.library or default_library(), geometry=args.geometry, base_directory=args.base_data, progress=progress, overwrite=args.overwrite)
    if args.save_definition:
        save_definition(args.save_definition, definition)
    print("Saved material: "+definition["name"]+"\nData folder: "+result["data_directory"], file=sys.stderr)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


def _command_models(args):
    """models: list the detector, sample, standard and material names."""
    mode = mode_name(args.geometry)
    data_dir = args.data_dir or default_data_dir()
    for label in ("Detector", "Sample", "Standard"):
        names = set(p.stem for p in (ASSETS/mode/label).glob("*.txt"))
        if data_dir and (Path(data_dir)/label).is_dir():
            names |= set(p.stem for p in (Path(data_dir)/label).glob("*.txt"))
        print(label+": "+", ".join(sorted(names)))
    print("Materials: "+", ".join(material_names(data_dir)))
    print("Original materials (bundled): "+", ".join(sorted((p.stem for p in (COMMON_DATA/"Composition").glob("*.txt")), key=str.lower)))
    return 0


def _command_check_update(args):
    """check-update: compare the installed version with the newest GitHub release."""
    from . import updater
    try:
        release = updater.check_for_update()
    except updater.UpdateError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if release is None:
        print(f"[INFO] EffSuite {VERSION} is the latest version")
    else:
        print(f"[INFO] EffSuite {release.version} is available (installed: {VERSION})")
        print(f"[INFO] Release page: {release.page_url}")
        print(f"[INFO] Installer:    {release.asset_url}")
    return 0


def _command_config(args):
    """config: show or change the default data folder."""
    from .paths import builtin_data_dir, data_dir_source, legacy_data_dirs, set_data_dir, settings_file
    if args.data_dir or args.reset_data_dir:
        if data_dir_source() == "environment":
            print("Note: EFFSUITE_DATA is set and still takes precedence over the saved setting.", file=sys.stderr)
        folder = set_data_dir(None if args.reset_data_dir else args.data_dir)
        print(("Default data folder reset: " if args.reset_data_dir else "Default data folder saved: ")+str(folder))
        return 0
    folder = get_data_dir()
    print(f"Data folder:      {folder}  (from {data_dir_source()})")
    print(f"  Composition:    {'present' if (folder/'Composition').is_dir() else 'not created yet'}")
    print(f"  Material:       {'present' if (folder/'Material').is_dir() else 'not created yet'}")
    print(f"Built-in default: {builtin_data_dir()}")
    for legacy in legacy_data_dirs():
        print(f"Legacy (read):    {legacy}{'' if legacy.is_dir() else '  (absent)'}")
    print(f"Bundled originals:{COMMON_DATA}")
    print(f"Settings file:    {settings_file()}")
    return 0


def _command_plot_geometry(args):
    """plot-geometry: save a picture of a detector/source geometry."""
    mode = mode_name(args.geometry)
    data_dir = args.data_dir or default_data_dir()
    det = read_model(mode, "detector", find_model(mode, "detector", args.detector, data_dir))
    smp = read_model(mode, "sample", find_model(mode, "sample", args.sample, data_dir)) if args.sample else None
    if smp:
        smp = _apply_sample_overrides(mode, smp, height=args.sample_height, gap=args.sample_gap, data_dir=data_dir)
    std = read_model(mode, "standard", find_model(mode, "standard", args.standard, data_dir)) if args.standard else None
    proj = {"geometry":mode, "detector":det, "sample":smp, "standard":std}
    saved = _save_geometry_plot(proj, args.out, kind=args.kind)
    print(json.dumps({"geometry_plot":saved}, indent=2))
    return 0


def _command_examples(args, progress):
    """examples: list the built-in examples, or run one."""
    if args.run:
        result = run_project(load_project(example_path(args.run)), default_output(), progress=progress)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result["all_reported_factors_valid"] else 1
    for name in ("cylinder", "marinelli", "well"):
        print(example_path(name))
    return 0


def _command_calculation(args, progress):
    """run / cylinder / marinelli / well: one calculation; exit code 0, 1 (invalid factors)."""
    if args.command=="run":
        project = load_project(args.project)
        if args.workers is not None:
            project["workers"] = args.workers
        _apply_tcs_uncertainty_args(project, args)
        if any(v is not None for v in (args.sample_height, args.sample_material, args.sample_density)):
            project["sample"] = _apply_sample_overrides(
                project["geometry"], project["sample"],
                height=args.sample_height, material=args.sample_material, density=args.sample_density,
                data_dir=project.get("data_directory"), progress=progress,
            )
    else:
        mode = mode_name(args.command)
        project = _build_project_from_args(mode, args, progress=progress)
        if args.save_project:
            with args.save_project.open("x", encoding="utf-8") as f:
                json.dump(project, f, indent=2)
                f.write("\n")
    out_dir = args.out or default_output()
    result = run_project(project, out_dir, progress=progress)
    _copy_direct_outputs(result, output_cal=getattr(args, "output_cal", None), output_nlb=getattr(args, "output_nlb", None), output_ctf=getattr(args, "output_ctf", None))
    if getattr(args, "plot_geometry", None):
        plot_arg = args.plot_geometry
        plot_dest = (Path(result["output_directory"])/"geometry.png") if plot_arg=="geometry.png" else Path(plot_arg)
        result["geometry_plot"] = _save_geometry_plot(project, plot_dest)
    print(f"Saved: {result['output_directory']}", file=sys.stderr)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["all_reported_factors_valid"] else 1


def main(argv=None):
    """Command-line entry point; returns the exit code (0 = success)."""
    argv = list(sys.argv[1:] if argv is None else argv)

    # A single file argument (drag and drop onto EffSuite_CLI.exe) runs a .json project or a .csv batch.
    if len(argv) == 1 and not argv[0].startswith("-"):
        candidate = Path(argv[0].strip('"').strip("'"))
        if candidate.is_file():
            if candidate.suffix.lower() == ".json":
                argv = ["run", str(candidate)]
            elif candidate.suffix.lower() == ".csv":
                argv = ["batch", str(candidate)]

    if not argv:
        if sys.stdin.isatty():
            return interactive_cli()
        else:
            print_cli_banner()
            parser().print_help()
            return 0

    args = parser().parse_args(argv)
    if getattr(args, "software", None):
        os.environ["EFFSUITE_SOFTWARE"] = args.software
    progress = lambda s:print(s, file=sys.stderr, flush=True)
    try:
        if args.command=="gui":
            from .gui import main as gui_main
            return gui_main()
        if args.command=="doctor":
            return _command_doctor(args)
        if args.command=="material":
            return _command_material(args, progress)
        if args.command=="models":
            return _command_models(args)
        if args.command=="plot-geometry":
            return _command_plot_geometry(args)
        if args.command=="batch":
            return _run_batch(args, progress)
        if args.command=="examples":
            return _command_examples(args, progress)
        if args.command=="config":
            return _command_config(args)
        if args.command=="check-update":
            return _command_check_update(args)
        return _command_calculation(args, progress)
    except (CoincidenceError, OSError, ValueError) as exc:
        print(f"EffSuite: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__=="__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
