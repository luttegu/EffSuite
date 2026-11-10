"""Parallel test runner for EffSuite.

Executes test modules concurrently across independent worker processes
while isolating GUI tests appropriately and reporting per-module timings.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"


def _run_module(module_name: str, verbose: bool) -> tuple[str, int, float, str, str]:
    started = time.monotonic()
    cmd = [sys.executable, "-m", "unittest", module_name]
    if verbose:
        cmd.append("-v")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        creationflags=flags,
    )
    elapsed = time.monotonic() - started
    return module_name, proc.returncode, elapsed, proc.stdout, proc.stderr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=0,
        help="Number of parallel test processes (0 = auto, up to 8)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show individual test case output",
    )
    parser.add_argument(
        "modules",
        nargs="*",
        help="Optional test module names or paths (e.g. tests.test_suite or test_suite.py); defaults to all tests/test_*.py",
    )
    args = parser.parse_args(argv)

    if args.modules:
        modules = []
        for item in args.modules:
            clean = item.replace("\\", "/").removesuffix(".py").strip("/")
            if not clean.startswith("tests."):
                clean = "tests." + clean.removeprefix("tests/")
            modules.append(clean)
    else:
        modules = [f"tests.{p.stem}" for p in sorted(TESTS_DIR.glob("test_*.py"))]

    if not modules:
        print("No test modules found.", file=sys.stderr)
        return 1

    workers = args.jobs if args.jobs > 0 else min(len(modules), max(2, min(8, (os.cpu_count() or 4) // 2)))
    print(f"Running {len(modules)} test module(s) across {workers} parallel worker(s)...\n", flush=True)

    started_total = time.monotonic()
    failures = []
    results = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run_module, mod, args.verbose): mod for mod in modules}
        for future in as_completed(futures):
            mod, rc, elapsed, stdout, stderr = future.result()
            status = "PASS" if rc == 0 else "FAIL"
            print(f"[{status}] {mod:<38} ({elapsed:6.2f}s)", flush=True)
            if args.verbose or rc != 0:
                output = (stdout + "\n" + stderr).strip()
                if output:
                    print("-" * 70)
                    print(output)
                    print("-" * 70, flush=True)
            results.append((mod, rc, elapsed))
            if rc != 0:
                failures.append(mod)

    total_elapsed = time.monotonic() - started_total
    sum_elapsed = sum(r[2] for r in results)
    print(f"\nCompleted {len(modules)} module(s) in {total_elapsed:.2f}s wall time (cumulative {sum_elapsed:.2f}s).")
    if failures:
        print(f"FAILED ({len(failures)}): {', '.join(failures)}", file=sys.stderr)
        return 1
    print("ALL TESTS PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
