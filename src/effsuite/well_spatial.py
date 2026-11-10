"""Spatial WEFFTRAN correction CLI. Uses prepared coin1 detector response files."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from hashlib import sha256
import json
import math
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from .model_io import ASSETS, COMMON_DATA
from .parallel_coincidence import CoincidenceError, _publish_new
from .spatial_summing import (Quadrature, integrated_counts, parse_decay,
                              prepare_local, required_energies)
from .well_parallel import NAME

_WORKER_LOCAL = None
_WORKER_TIME = None


def _safe_py_sha256(filename: str) -> str:
    path = Path(__file__).parent / filename
    try:
        if path.is_file():
            return sha256(path.read_bytes()).hexdigest()
        pyc = path.with_suffix(".pyc")
        if pyc.is_file():
            return sha256(pyc.read_bytes()).hexdigest()
    except Exception:
        pass
    return sha256(filename.encode()).hexdigest()


def _initialize_spatial_worker(local, resolving_time):
    global _WORKER_LOCAL, _WORKER_TIME
    for array in (local.energies, local.weights, local.peak, local.total, local.points):
        array.flags.writeable = False
    _WORKER_LOCAL, _WORKER_TIME = local, resolving_time


def _calculate_spatial_group(records):
    return integrated_counts(records, _WORKER_LOCAL, _WORKER_TIME)


def prepare_well_case(installation: Path, engine_dir: Path, detector: Path,
                      sample: Path, destination: Path, progress=None) -> None:
    """Run coin1 stages in a private directory for the exact selected inputs."""
    for folder in ("Composition", "Material"):
        source = installation/folder if (installation/folder).is_dir() else COMMON_DATA/folder
        shutil.copytree(source, destination/folder)
    for filename in ("zzaa.txt", "param.txt"):
        if (installation/filename).is_file():
            shutil.copyfile(installation/filename, destination/filename)
        elif (engine_dir/filename).is_file():
            shutil.copyfile(engine_dir/filename, destination/filename)
        elif (ASSETS/"well"/filename).is_file():
            shutil.copyfile(ASSETS/"well"/filename, destination/filename)
    shutil.copyfile(detector, destination/"detector.txt")
    shutil.copyfile(sample, destination/"source.txt")
    suffix = ".exe" if os.name == "nt" else ""
    for stage in ("mine", "energy", "total", "scatter", "buildup", "eta", "ptt", "efficiency"):
        executable = (engine_dir/(stage+suffix)).resolve()
        if not executable.is_file():
            raise CoincidenceError(f"Missing compiled reference stage: {executable}")
        if progress:
            progress(f"Preparing shared response: {stage}")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
            result = subprocess.run([str(executable)], cwd=destination, stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=300, shell=False, creationflags=flags)
        except subprocess.TimeoutExpired as exc:
            raise CoincidenceError(f"Shared response stage timed out: {stage}") from exc
        if result.returncode:
            message = result.stderr[:4000].decode("utf-8", errors="replace")
            raise CoincidenceError(f"Shared response stage {stage} failed: {message}")


def load_groups(installation, names, beta_plus_pl=("NA-22",)):
    decay_dir = (
        installation/"Decay_Data"
        if installation and (installation/"Decay_Data").is_dir()
        else (COMMON_DATA/"Decay_Data" if (COMMON_DATA/"Decay_Data").is_dir() else ASSETS/"well/Decay_Data")
    )
    groups = []; missing = []
    for name in names:
        if not NAME.fullmatch(name):
            raise CoincidenceError(f"Invalid parent nuclide: {name}")
        parent_path = decay_dir/(name+".txt")
        if not parent_path.is_file():
            missing.append(name); continue
        records = []
        for label in (name, name+"b"):
            path = decay_dir/(label+".txt")
            if path.is_file():
                records.append(parse_decay(label, path.read_bytes(), beta_plus_in_pl=name in beta_plus_pl))
        groups.append((name, tuple(records)))
    if not groups:
        raise CoincidenceError("Unknown parent nuclides: " + ", ".join(missing))
    return tuple(groups), missing


def calculate_groups(groups, local, resolving_time, workers, verify_serial=False, cancel=None):
    from .parallel_coincidence import CalculationCancelled
    if cancel is not None and cancel.is_set():raise CalculationCancelled("Calculation cancelled")
    if workers <= 1:
        results = {name: integrated_counts(records, local, resolving_time) for name, records in groups}
    else:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="well-nuclide") as pool:
            futures = {pool.submit(integrated_counts, records, local, resolving_time): name
                       for name, records in groups}
            results = {}
            for future in as_completed(futures):
                if cancel is not None and cancel.is_set():
                    for pending in futures:pending.cancel()
                    raise CalculationCancelled("Calculation cancelled")
                results[futures[future]] = future.result()
    if verify_serial and workers > 1:
        reference = calculate_groups(groups, local, resolving_time, 1,cancel=cancel)
        if reference != tuple((name, results[name]) for name, _ in groups):
            raise CoincidenceError("Spatial serial and parallel results differ")
    return tuple((name, results[name]) for name, _ in groups)


def calculate_spatial(installation: Path, prepared: Path, names: tuple[str, ...], *,
                      order=Quadrature(), workers=0, verify_serial=False,
                      check_convergence=True, rtol=.01, beta_plus_pl=("NA-22",),
                      progress=None, cancel=None) -> dict:
    if type(workers) is not int or workers < 0:
        raise CoincidenceError("workers must be a nonnegative integer")
    if not math.isfinite(rtol) or not 0 < rtol < 1:
        raise CoincidenceError("Numerical convergence rtol must be between zero and one")
    groups, missing = load_groups(installation, names, beta_plus_pl)
    auto_workers = max(1, (os.cpu_count() or 4) - 2)
    count = min(workers or auto_workers, len(groups))
    energies = required_energies(tuple(record for _, records in groups for record in records))
    resolving_time = float((prepared/"param.txt").read_text().strip())
    started = time.monotonic()
    if progress:
        progress("Calculating local detector response")
    local = prepare_local(installation, prepared, energies, order, cancel, workers=workers)
    initial = calculate_groups(groups, local, resolving_time, count, verify_serial,cancel)
    convergence = {"requested": check_convergence, "passed": None, "rtol": rtol,
                   "meaning": "Numerical refinement only; not model uncertainty"}
    if check_convergence:
        if progress:
            progress("Refining spatial and angular quadrature")
        fine = prepare_local(installation, prepared, energies, order.refined(), cancel, workers=workers)
        refined = calculate_groups(groups, fine, resolving_time, count, verify_serial,cancel)
        previous = {name: {row["energy_kev"]: row for row in item["corrections"]} for name, item in initial}
        differences = []
        for name, item in refined:
            for row in item["corrections"]:
                before = previous[name].get(row["energy_kev"], {}).get("factor")
                after = row["factor"]
                error = abs(after-before)/abs(after) if before is not None and after is not None and after > 0 else None
                passed = error is not None and error <= rtol
                row["refinement_relative_change"] = error
                row["status"] = "candidate" if passed else "not_converged"
                differences.append({"nuclide": name, "energy_kev": row["energy_kev"],
                                    "relative_change": error, "passed": passed})
        convergence.update({"passed": bool(differences) and all(row["passed"] for row in differences),
                            "maximum_relative_change": max((row["relative_change"] for row in differences
                                                            if row["relative_change"] is not None), default=None),
                            "failed_lines": [row for row in differences if not row["passed"]],
                            "initial_quadrature": local.metadata["quadrature"]})
        results, local = refined, fine
    else:
        results = initial
        for _, item in results:
            for row in item["corrections"]:
                row["status"] = "convergence_not_checked"
    return {"schema_version": 1, "calculation": "wefftran-spatial-count-integration",
            "engine_version": "0.2.0-spatial",
            "engine_sha256": {filename: _safe_py_sha256(filename)
                              for filename in ("spatial_summing.py", "well_spatial.py")},
            "qualification": "Regression and numerical checks; laboratory qualification pending",
            "model": "Ray-traced hollow-crystal well response with probability-conserving upstream Compton/Rayleigh scattering, local peak-to-total, and exact antiparallel 511 keV pairs; pointwise cascade recursion",
            "limitations": ["Isotropic independent emission directions; no angular correlation model",
                            "Deterministic approximation, not a Monte Carlo transport; real crystal contacts, holder and cryostat details are not modelled",
                            "Gamma peak output uses legacy transition-energy bins",
                            "Annihilation-pair sum peaks at 1022 keV and mixed pair sum-in channels are not added"],
            "workers": count, "serial_verification": {"requested": verify_serial, "passed": True if verify_serial else None},
            "resolving_time": resolving_time,
            "param_sha256": sha256((prepared/"param.txt").read_bytes()).hexdigest(),
            "seconds": time.monotonic()-started,
            "transport": local.metadata, "convergence": convergence,
            "missing_nuclides": missing,
            "nuclides": [{"nuclide": name, **item} for name, item in results]}


def legacy_text(report: dict) -> bytes:
    if len(report["nuclides"]) != 1:
        raise CoincidenceError("Legacy correct.txt output requires one parent nuclide")
    if not report["convergence"]["passed"]:
        raise CoincidenceError("Legacy output requires a passing numerical refinement check")
    if report["transport"]["probability_saturation_count"]:
        raise CoincidenceError("Legacy output blocked: local build-up response required probability saturation")
    rows = report["nuclides"][0]["corrections"]
    if not rows or any(row["status"] != "candidate" or row["factor"] is None for row in rows):
        raise CoincidenceError("No complete set of converged correction factors")
    # Do not pretend to supply pair sum-in to a 1022-keV line. Other mixed
    # pair sum-in overlaps require laboratory-specific qualification as well.
    if report["nuclides"][0]["annihilation_pair_records"] and any(abs(row["energy_kev"]-1022) < 1 for row in rows):
        raise CoincidenceError("1022-keV pair sum-in output is not implemented")
    return "".join(f"{row['energy_kev']:10d}{row['factor']:15.7E}\n" for row in rows).encode("ascii")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True, help="WEFFTRAN materials and Decay_Data directory")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--inputs", type=Path, help="Complete coin1 outputs for the same detector/sample")
    source.add_argument("--detector", type=Path, help="Detector model; prepare fresh response files")
    parser.add_argument("--sample", type=Path, help="Sample model; required with --detector")
    parser.add_argument("--engine-dir", type=Path, help="Compiled reference stages; default --original")
    parser.add_argument("--nuclide", action="append", required=True)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--radial", type=int, default=4)
    parser.add_argument("--axial", type=int, default=8)
    parser.add_argument("--polar", type=int, default=32)
    parser.add_argument("--azimuth", type=int, default=64)
    parser.add_argument("--rtol", type=float, default=.01, help="Numerical refinement criterion; not physical uncertainty")
    parser.add_argument("--verify-serial", action="store_true")
    parser.add_argument("--no-refinement", action="store_true", help="Diagnostic results only; legacy export disabled")
    parser.add_argument("--beta-plus-pl", action="append", default=None,
                        help="Explicit PL beta+ encoding; default NA-22 for the supplied archive; repeat as needed")
    parser.add_argument("--format", choices=("json", "correct"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise CoincidenceError("Output exists; choose a new filename")
        progress = lambda message: print(message, file=sys.stderr)
        with ExitStack() as stack:
            prepared = args.inputs
            if args.detector:
                if not args.sample:
                    raise CoincidenceError("--sample is required with --detector")
                prepared = Path(stack.enter_context(TemporaryDirectory(prefix="weff-spatial-inputs-")))
                prepare_well_case(args.original, args.engine_dir or args.original,
                                  args.detector, args.sample, prepared, progress)
            elif args.sample or args.engine_dir:
                raise CoincidenceError("Use --sample/--engine-dir with --detector")
            report = calculate_spatial(args.original, prepared, tuple(args.nuclide),
                                       order=Quadrature(args.radial, args.axial, args.polar, args.azimuth),
                                       workers=args.workers, verify_serial=args.verify_serial,
                                       check_convergence=not args.no_refinement, rtol=args.rtol,
                                       beta_plus_pl=tuple(args.beta_plus_pl) if args.beta_plus_pl is not None else ("NA-22",),
                                       progress=progress)
        raw = legacy_text(report) if args.format == "correct" else (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()
        if args.output:
            _publish_new(args.output, raw)
        else:
            sys.stdout.write(raw.decode())
        return 0 if report["convergence"]["passed"] else 1
    except KeyboardInterrupt:
        return 130
    except (CoincidenceError, OSError, ValueError) as exc:
        print(f"effsuite-well-spatial: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
