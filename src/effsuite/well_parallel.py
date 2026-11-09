"""Parallel WEFFTRAN nuclides using its separate legacy stage executables.

Prepare detector efficiencies once with coin1's stages, then supply their
efficiency.txt/buildup.txt here. This module does not run Excel or Genie CAM.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
from typing import Callable

from .correction_diagnostics import audit_corrections
from .parallel_coincidence import (CalculationCancelled, CoincidenceError,
                                  _curve, _publish_new, _terminate, split_library)

STAGES = ("initialize", "emissions", "emissions2", "peak", "correct")
OUTPUTS = ("correct.txt", "emissions.txt", "emissions2.txt", "peak.txt")
NAME = re.compile(r"[A-Z][A-Z0-9-]*\Z")


@dataclass(frozen=True)
class WellInputs:
    efficiency: bytes
    buildup: bytes
    param: bytes
    # Immutable parent/continuation snapshots. No worker reads a mutable library.
    groups: tuple[tuple[str, tuple[bytes, ...]], ...]

    @classmethod
    def from_directories(cls, prepared: Path, decay: Path,
                         nuclides: tuple[str, ...]) -> "WellInputs":
        groups = []
        for name in nuclides:
            if not NAME.fullmatch(name):
                raise CoincidenceError(f"Invalid parent nuclide: {name}")
            records = [(decay / (name + ".txt")).read_bytes()]
            continuation = decay / (name + "b.txt")
            if continuation.is_file():
                records.append(continuation.read_bytes())
            groups.append((name, tuple(records)))
        return cls((prepared / "efficiency.txt").read_bytes(),
                   (prepared / "buildup.txt").read_bytes(),
                   (prepared / "param.txt").read_bytes(), tuple(groups))

    def validate(self) -> None:
        if _curve(self.efficiency, "efficiency.txt") != _curve(self.buildup, "buildup.txt"):
            raise CoincidenceError("Efficiency and buildup energy grids must match")
        try:
            values = self.param.split()
            resolution = float(values[0]) if len(values) == 1 else float("nan")
        except ValueError as exc:
            raise CoincidenceError("Invalid resolving time in param.txt") from exc
        if not math.isfinite(resolution) or resolution < 0:
            raise CoincidenceError("Resolving time must be finite and nonnegative")
        if not self.groups or len({name for name, _ in self.groups}) != len(self.groups):
            raise CoincidenceError("Select at least one unique parent nuclide")
        for name, records in self.groups:
            if not NAME.fullmatch(name) or not 1 <= len(records) <= 2 or not all(records):
                raise CoincidenceError("Expected a parent record and optional b continuation")
            for raw in records:
                # Individual Decay_Data files end at EOF; KORDATEN uses an
                # explicit transition sentinel. Reuse its structural checks.
                split_library(name.encode("ascii") + b"\n" + raw.rstrip() +
                              b"\n-1 0 0 0 0 0 0\n")


@dataclass(frozen=True)
class WellResult:
    # Raw outputs retained separately from their scientific/export status.
    nuclides: tuple[tuple[str, tuple[tuple[str, bytes], ...]], ...]
    report: dict


def engine_commands(directory: Path) -> dict[str, tuple[str, ...]]:
    suffix = ".exe" if os.name == "nt" else ""
    return {stage: (str((directory / (stage + suffix)).resolve()),) for stage in STAGES}


def _run_nuclide(name: str, records: tuple[bytes, ...], inputs: WellInputs,
                 commands: dict[str, tuple[str, ...]], stop: threading.Event,
                 timeout_seconds: float) -> tuple[tuple[tuple[str, bytes], ...], float]:
    started = time.monotonic()
    with TemporaryDirectory(prefix="effsuite-well-") as temporary:
        work = Path(temporary)
        for filename, raw in (("efficiency.txt", inputs.efficiency),
                              ("buildup.txt", inputs.buildup), ("param.txt", inputs.param)):
            (work / filename).write_bytes(raw)

        def run(stage: str) -> None:
            if stop.is_set():
                raise CalculationCancelled("Calculation cancelled")
            with (work / "stdout.log").open("wb") as stdout, (work / "stderr.log").open("wb") as stderr:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
                process = subprocess.Popen(commands[stage], cwd=work, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, shell=False, creationflags=flags)
                try:
                    while process.poll() is None:
                        if stop.is_set():
                            raise CalculationCancelled("Calculation cancelled")
                        if time.monotonic() - started > timeout_seconds:
                            raise CoincidenceError(f"{name}: nuclide exceeded {timeout_seconds:g} seconds")
                        try:
                            process.wait(timeout=.02)
                        except subprocess.TimeoutExpired:
                            pass
                finally:
                    _terminate(process)
            if process.returncode:
                diagnostic = (work / "stderr.log").read_bytes()[:4000].decode("utf-8", errors="replace")
                raise CoincidenceError(f"{name}/{stage}: exit {process.returncode}: {diagnostic}")

        run("initialize")
        # A parent and its b record accumulate into the same three spectra.
        for record in records:
            (work / "coin.txt").write_bytes(record)
            for stage in ("emissions", "emissions2", "peak"):
                run(stage)
        run("correct")
        if stop.is_set():
            raise CalculationCancelled("Calculation cancelled")
        try:
            output = tuple((filename, (work / filename).read_bytes()) for filename in OUTPUTS)
        except OSError as exc:
            raise CoincidenceError(f"{name}: missing stage output") from exc
        return output, time.monotonic() - started


def calculate_well_parallel(inputs: WellInputs, commands: dict[str, tuple[str, ...]], *,
                            workers: int = 0, timeout_seconds: float = 300,
                            minimum_ratio: float = 1e-3, verify_serial: bool = False,
                            cancel: threading.Event | None = None,
                            progress: Callable[[int, int, str], None] | None = None) -> WellResult:
    inputs.validate()
    if type(workers) is not int or workers < 0:
        raise CoincidenceError("workers must be a nonnegative integer")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise CoincidenceError("timeout_seconds must be finite and positive")
    if not math.isfinite(minimum_ratio) or not 0 <= minimum_ratio <= 1:
        raise CoincidenceError("minimum_ratio must be between zero and one")
    if set(commands) != set(STAGES):
        raise CoincidenceError("Provide the five WEFFTRAN stage commands")
    for command in commands.values():
        if not command or not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
            raise CoincidenceError("Each stage must use an existing absolute executable path")
    # Snapshot command sequences to avoid caller mutations during execution.
    commands = {name: tuple(command) for name, command in commands.items()}
    stop = cancel if cancel is not None else threading.Event()
    if stop.is_set():
        raise CalculationCancelled("Calculation cancelled")
    auto_workers = max(1, (os.cpu_count() or 4) - 2)
    count = min(workers or auto_workers, len(inputs.groups))
    outputs = {}
    timings = {}
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=count, thread_name_prefix="well-supervisor") as pool:
        futures = {pool.submit(_run_nuclide, name, records, inputs, commands, stop, timeout_seconds): name
                   for name, records in inputs.groups}
        try:
            for future in as_completed(futures):
                name = futures[future]
                outputs[name], timings[name] = future.result()
                if progress:
                    progress(len(outputs), len(inputs.groups), name)
        except BaseException:
            stop.set()
            for future in futures:
                future.cancel()
            raise
    elapsed = time.monotonic() - started
    if stop.is_set():
        raise CalculationCancelled("Calculation cancelled")
    verification = {"requested": verify_serial, "passed": None}
    if verify_serial:
        for name, records in inputs.groups:
            reference, _ = _run_nuclide(name, records, inputs, commands, stop, timeout_seconds)
            if reference != outputs[name]:
                raise CoincidenceError(f"{name}: serial and parallel output bytes differ")
        verification["passed"] = True
    nuclides = tuple((name, outputs[name]) for name, _ in inputs.groups)
    summaries = []
    for name, files in nuclides:
        spectra = dict(files)
        audited = audit_corrections(spectra["emissions.txt"], spectra["peak.txt"],
                                    spectra["emissions2.txt"], spectra["correct.txt"],
                                    minimum_ratio=minimum_ratio)
        summaries.append({"nuclide": name, "seconds": timings[name],
                          "output_sha256": {filename: sha256(raw).hexdigest() for filename, raw in files},
                          "corrections": [row.to_object() for row in audited]})
    return WellResult(nuclides, {
        "schema_version": 1, "calculation": "legacy-wefftran-parallel-orchestration",
        "qualification": "Scheduling and diagnostics only; no new physics qualification",
        "workers": count, "nuclide_groups": len(inputs.groups),
        "decay_records": sum(len(records) for _, records in inputs.groups),
        "parallel_seconds": elapsed, "serial_verification": verification,
        "review_policy": {"minimum_denominator_ratio": minimum_ratio},
        "input_sha256": {"efficiency.txt": sha256(inputs.efficiency).hexdigest(),
                         "buildup.txt": sha256(inputs.buildup).hexdigest(),
                         "param.txt": sha256(inputs.param).hexdigest(),
                         "decay_records": {name: [sha256(raw).hexdigest() for raw in records]
                                           for name, records in inputs.groups}},
        "command_file_sha256": {stage: {str(Path(arg)): sha256(Path(arg).read_bytes()).hexdigest()
                                        for arg in command if Path(arg).is_absolute() and Path(arg).is_file()}
                                for stage, command in commands.items()},
        "nuclides": summaries,
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-dir", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--decay-data", type=Path, required=True)
    parser.add_argument("--nuclide", action="append", required=True)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--minimum-ratio", type=float, default=1e-3)
    parser.add_argument("--verify-serial", action="store_true")
    parser.add_argument("--output", type=Path, help="New diagnostic JSON file; default stdout")
    args = parser.parse_args(argv)
    stop = threading.Event()
    try:
        if args.output and args.output.exists():
            raise CoincidenceError("Output exists; choose a new filename")
        inputs = WellInputs.from_directories(args.inputs, args.decay_data, tuple(args.nuclide))
        result = calculate_well_parallel(inputs, engine_commands(args.engine_dir), workers=args.workers,
                                         timeout_seconds=args.timeout, minimum_ratio=args.minimum_ratio,
                                         verify_serial=args.verify_serial, cancel=stop,
                                         progress=lambda done, total, name:
                                         print(f"{done}/{total}: {name}", file=sys.stderr))
        raw = (json.dumps(result.report, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if args.output:
            _publish_new(args.output, raw)
        else:
            sys.stdout.write(raw.decode("utf-8"))
        # A diagnostic report is published even when the physics result failed.
        return 1 if any(row["status"] != "candidate" for item in result.report["nuclides"]
                        for row in item["corrections"]) else 0
    except KeyboardInterrupt:
        stop.set()
        return 130
    except (CoincidenceError, OSError) as exc:
        print(f"effsuite-well-coincidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
