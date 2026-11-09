"""Parallel orchestration for EFFTRAN 4.8 / MEFFTRAN 1.7 coincidence.f.

The numerical executable is unchanged. Complete nuclide groups, including all
lowercase-b continuation records, are assigned to isolated child processes.
This is a source-informed migration component, not a rewritten physics engine.
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
import subprocess
from tempfile import TemporaryDirectory, NamedTemporaryFile
import threading
import time
from typing import Callable


class CoincidenceError(Exception):
    pass


class CalculationCancelled(CoincidenceError):
    pass


def _number(token: bytes) -> float:
    try:
        value = float(token.replace(b"D", b"E").replace(b"d", b"e"))
    except ValueError as exc:
        raise CoincidenceError(f"Invalid numeric token: {token!r}") from exc
    if not math.isfinite(value):
        return 1e-15
    return value


@dataclass(frozen=True)
class NuclideGroup:
    index: int
    name: str
    records: tuple[str, ...]
    raw: bytes
    estimated_cost: int


def split_library(raw: bytes) -> tuple[NuclideGroup, ...]:
    """Parse record boundaries, preserving the exact original record bytes.

    EFFTRAN's rule is a lowercase b in the last nonblank character of the
    Fortran A10 nuclide label. Such a record contributes to the preceding group.
    It must never be scheduled as an independent nuclide.
    """
    lines = raw.splitlines(keepends=True)
    position = 0
    groups: list[NuclideGroup] = []

    def take(minimum_fields: int) -> list[bytes]:
        nonlocal position
        if position >= len(lines):
            raise CoincidenceError("Truncated KORDATEN record")
        fields = lines[position].split()
        position += 1
        if len(fields) < minimum_fields:
            raise CoincidenceError(f"Too few fields at library line {position}")
        return fields

    while position < len(lines):
        start = position
        try:
            name = lines[position].rstrip(b"\r\n")[:10].decode("ascii").rstrip(" ")
        except UnicodeDecodeError as exc:
            raise CoincidenceError("Nuclide labels must be ASCII") from exc
        position += 1
        if not name or name != name.strip():
            raise CoincidenceError(f"Invalid nuclide label at line {position}")
        for value in take(4)[:4]:
            _number(value)
        level_count = 0
        while True:
            fields = take(5)
            values = [_number(value) for value in fields[:5]]
            if values[0] < 0:
                break
            level_count += 1
            if level_count > 100:
                raise CoincidenceError(f"{name}: more than 100 levels exceeds legacy arrays")
        if level_count == 0:
            raise CoincidenceError(f"{name}: no levels")
        while True:
            fields = take(7)
            try:
                source, destination = int(fields[0]), int(fields[1])
            except ValueError as exc:
                raise CoincidenceError(f"{name}: invalid transition indices") from exc
            for value in fields[2:7]:
                _number(value)
            if source == -1:
                break
            if not (1 <= source <= 100 and 1 <= destination <= 100):
                raise CoincidenceError(f"{name}: transition outside legacy array bounds")
        record_raw = b"".join(lines[start:position])
        cost = max(1, level_count**3)
        if name.endswith("b"):
            if not groups:
                raise CoincidenceError("Continuation record has no preceding parent nuclide")
            parent = groups[-1]
            groups[-1] = NuclideGroup(parent.index, parent.name, parent.records + (name,),
                                      parent.raw + record_raw, parent.estimated_cost + cost)
        else:
            groups.append(NuclideGroup(len(groups), name, (name,), record_raw, cost))
    if not groups:
        raise CoincidenceError("Empty KORDATEN library")
    if len({group.name for group in groups}) != len(groups):
        raise CoincidenceError("Duplicate parent labels need an explicit grouping policy")
    return tuple(groups)


def _curve(raw: bytes, name: str) -> tuple[float, ...]:
    energies = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 3:
            raise CoincidenceError(f"{name}:{line_number}: expected three columns")
        values = [_number(value) for value in fields[:3]]
        if any(value <= 0 for value in values):
            raise CoincidenceError(f"{name}:{line_number}: logarithmic inputs must be positive")
        if energies and values[0] <= energies[-1]:
            raise CoincidenceError(f"{name}: energies must increase strictly")
        energies.append(values[0])
    if not 2 <= len(energies) <= 100:
        raise CoincidenceError(f"{name}: expected 2 to 100 energy rows")
    return tuple(energies)


@dataclass(frozen=True)
class SharedInputs:
    efficiency: bytes
    buildup: bytes
    library: bytes

    @classmethod
    def from_directory(cls, directory: Path) -> "SharedInputs":
        return cls((directory / "efficiency.txt").read_bytes(),
                   (directory / "buildup.txt").read_bytes(),
                   (directory / "kordaten.txt").read_bytes())

    def validate(self) -> None:
        if _curve(self.efficiency, "efficiency.txt") != _curve(self.buildup, "buildup.txt"):
            raise CoincidenceError("Efficiency and buildup energy grids must match")


@dataclass(frozen=True)
class ParallelResult:
    coin_bytes: bytes
    report: dict


def _partition(groups: tuple[NuclideGroup, ...], workers: int) -> list[tuple[NuclideGroup, ...]]:
    """Deterministic balancing; only a bounded number of native processes launch."""
    buckets: list[list[NuclideGroup]] = [[] for _ in range(workers)]
    loads = [0] * workers
    for group in sorted(groups, key=lambda group: (-group.estimated_cost, group.index)):
        bucket = min(range(workers), key=lambda index: (loads[index], index))
        buckets[bucket].append(group)
        loads[bucket] += group.estimated_cost
    return [tuple(sorted(bucket, key=lambda group: group.index)) for bucket in buckets if bucket]


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _run_shard(command: tuple[str, ...], inputs: SharedInputs,
               groups: tuple[NuclideGroup, ...], stop: threading.Event,
               timeout_seconds: float) -> tuple[dict[str, bytes], float]:
    if stop.is_set():
        raise CalculationCancelled("Calculation cancelled")
    started = time.monotonic()
    with TemporaryDirectory(prefix="effsuite-cascade-") as directory:
        work = Path(directory)
        (work / "efficiency.txt").write_bytes(inputs.efficiency)
        (work / "buildup.txt").write_bytes(inputs.buildup)
        (work / "kordaten.txt").write_bytes(b"".join(group.raw for group in groups))
        with (work / "stdout.log").open("wb") as stdout, (work / "stderr.log").open("wb") as stderr:
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
                process = subprocess.Popen(command, cwd=work, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, shell=False, creationflags=flags)
            except OSError as exc:
                raise CoincidenceError(f"Cannot start coincidence executable: {exc}") from exc
            try:
                while process.poll() is None:
                    if stop.is_set():
                        raise CalculationCancelled("Calculation cancelled")
                    if time.monotonic() - started > timeout_seconds:
                        raise CoincidenceError(f"Coincidence worker exceeded {timeout_seconds:g} seconds")
                    try:
                        process.wait(timeout=.05)
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                _terminate(process)
        if stop.is_set():
            raise CalculationCancelled("Calculation cancelled")
        if process.returncode:
            diagnostic = (work / "stderr.log").read_bytes()[:4000].decode("utf-8", errors="replace")
            raise CoincidenceError(f"Coincidence worker exit {process.returncode}: {diagnostic}")
        output = work / "coin.txt"
        if not output.is_file():
            raise CoincidenceError("Coincidence worker did not produce coin.txt")
        # Reassemble by the original A10 parent labels, retaining each raw output row.
        rows: dict[str, list[bytes]] = {group.name: [] for group in groups}
        for line in output.read_bytes().splitlines(keepends=True):
            if not line.strip():
                raise CoincidenceError("Unexpected blank output row")
            try:
                label = line[:10].decode("ascii").rstrip(" ")
                energy = int(line[10:20])
                factor = _number(line[20:].strip())
            except (UnicodeDecodeError, ValueError) as exc:
                raise CoincidenceError("Malformed fixed-width coin.txt output") from exc
            if label not in rows or not 2 <= energy <= 3000:
                raise CoincidenceError("Unexpected nuclide or energy in coin.txt")
            rows[label].append(line)
        return {name: b"".join(lines) for name, lines in rows.items()}, time.monotonic() - started


def calculate_parallel(inputs: SharedInputs, command: tuple[str, ...], *, workers: int = 0,
                       nuclides: tuple[str, ...] | None = None,
                       timeout_seconds: float = 300,
                       cancel: threading.Event | None = None,
                       progress: Callable[[int, int, str], None] | None = None,
                       verify_serial: bool = False) -> ParallelResult:
    """Called from CLI or a GUI supervisor thread; no widgets are accessed here.

    `workers=0` selects at most four native workers. `workers=1` is the serial
    path, executing all selected groups in one native process.
    """
    if not command or not Path(command[0]).is_absolute():
        raise CoincidenceError("Executable must have an absolute path")
    if Path(command[0]).name.lower() in {"coin", "coin.exe"}:
        raise CoincidenceError("Use coincidence.exe, not the full-pipeline coin.exe launcher")
    if type(workers) is not int or workers < 0:
        raise CoincidenceError("workers must be a nonnegative integer")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise CoincidenceError("timeout_seconds must be finite and positive")
    inputs.validate()
    groups = split_library(inputs.library)
    missing = set()
    if nuclides is not None:
        wanted = {name.strip().upper() for name in nuclides}
        available = {group.name.upper() for group in groups}
        missing = wanted - available
        groups = tuple(group for group in groups if group.name.upper() in wanted)
        if not groups:
            raise CoincidenceError("Unknown parent nuclides: " + ", ".join(sorted(missing)))
    auto_workers = max(1, (os.cpu_count() or 4) - 2)
    count = min(workers or auto_workers, len(groups))
    shards = _partition(groups, count)
    stop = cancel if cancel is not None else threading.Event()
    if stop.is_set():
        raise CalculationCancelled("Calculation cancelled")
    hashes = {}
    for argument in command:
        path = Path(argument)
        if path.is_absolute() and path.is_file():
            hashes[str(path)] = sha256(path.read_bytes()).hexdigest()
    started = time.monotonic()
    rows: dict[str, bytes] = {}
    completed = 0
    timings = []
    # Python threads supervise independent native processes. Numerical work is
    # outside Python and cannot race through shared Fortran COMMON/SAVE state.
    with ThreadPoolExecutor(max_workers=count, thread_name_prefix="cascade-supervisor") as pool:
        futures = {pool.submit(_run_shard, command, inputs, shard, stop, timeout_seconds): shard
                   for shard in shards}
        try:
            for future in as_completed(futures):
                shard = futures[future]
                output, elapsed = future.result()
                rows.update(output)
                timings.append({"nuclides": [group.name for group in shard], "seconds": elapsed})
                for group in shard:
                    completed += 1
                    if progress is not None:
                        progress(completed, len(groups), group.name)
        except BaseException:
            stop.set()
            for future in futures:
                future.cancel()
            raise
    raw = b"".join(rows[group.name] for group in groups)
    elapsed = time.monotonic() - started
    verification = {"requested": verify_serial, "passed": None}
    if verify_serial:
        reference_rows, reference_time = _run_shard(command, inputs, groups, stop, timeout_seconds)
        reference = b"".join(reference_rows[group.name] for group in groups)
        verification.update({"passed": reference == raw,
                             "reference_sha256": sha256(reference).hexdigest(),
                             "reference_seconds": reference_time})
        if reference != raw:
            raise CoincidenceError("Parallel output differs from the complete serial output; no result published")
    report = {
        "schema_version": 1, "calculation": "legacy-cascade-parallel-orchestration",
        "qualification": "Scheduling comparison only; not a new physics qualification",
        "workers": count, "nuclide_groups": len(groups),
        "decay_records": sum(len(group.records) for group in groups),
        "nuclides_in_output_order": [group.name for group in groups],
        "missing_nuclides": sorted(missing),
        "parallel_seconds": elapsed,
        "worker_timings": sorted(timings, key=lambda item: item["nuclides"]),
        "serial_verification": verification,
        "input_sha256": {"efficiency.txt": sha256(inputs.efficiency).hexdigest(),
                         "buildup.txt": sha256(inputs.buildup).hexdigest(),
                         "kordaten.txt": sha256(inputs.library).hexdigest()},
        "command_file_sha256": hashes,
        "coin_txt_sha256": sha256(raw).hexdigest(),
    }
    return ParallelResult(raw, report)


def _publish_new(path: Path, raw: bytes) -> None:
    """Publish complete bytes without overwriting, using atomic creation."""
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=".cascade-", delete=False) as target:
            temporary = Path(target.name)
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        if os.name == "nt":
            if path.exists():
                raise FileExistsError(f"Target file already exists: {path}")
            os.replace(temporary, path)
            temporary = None
        else:
            os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path, help="Path to coincidence.exe or native equivalent")
    parser.add_argument("--inputs", required=True, type=Path, help="Directory with prepared curve and library files")
    parser.add_argument("--output", required=True, type=Path, help="New coin.txt result path")
    parser.add_argument("--workers", type=int, default=0, help="0: auto, at most four; 1: serial")
    parser.add_argument("--nuclide", action="append", help="Parent nuclide; repeat to select several")
    parser.add_argument("--timeout", type=float, default=300, help="Timeout per native worker")
    parser.add_argument("--verify-serial", action="store_true", help="Require byte-identical complete serial output")
    args = parser.parse_args(argv)
    stop = threading.Event()
    try:
        if args.output.exists():
            raise CoincidenceError("Output exists; choose a new filename")
        result = calculate_parallel(
            SharedInputs.from_directory(args.inputs), (str(args.engine.resolve()),),
            workers=args.workers, nuclides=tuple(args.nuclide) if args.nuclide is not None else None,
            timeout_seconds=args.timeout, cancel=stop, verify_serial=args.verify_serial,
            progress=lambda done, total, name: print(f"{done}/{total}: {name}", file=sys.stderr),
        )
        _publish_new(args.output, result.coin_bytes)
        print(json.dumps(result.report, indent=2, allow_nan=False))
        return 0
    except KeyboardInterrupt:
        stop.set()
        print("Calculation cancelled", file=sys.stderr)
        return 130
    except (CoincidenceError, OSError) as exc:
        print(f"effsuite-coincidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
