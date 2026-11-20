"""Build the WEFFTRAN ray-tracing program (raytrace.f90) only.

The EFFTRAN, MEFFTRAN and WEFFTRAN engines are NOT rebuilt (use
build_engines.py for those). The program is written to
src/effsuite/assets/engines/well/bin/<target>/ with its own manifest
raytrace_manifest.json (compiler, flags and SHA-256 of source and binary).

Usage:
    python tools/build_raytrace.py --compiler C:/path/to/gfortran.exe
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WELL = ROOT / "src/effsuite/assets/engines/well"
SOURCE = WELL / "source/raytrace.f90"

# Same numerical flags as build_engines.py: no fast-math and no fused
# multiply-add, so the floating-point results are predictable.
FLAGS = ["-O2", "-fno-fast-math", "-ffp-contract=off", "-fno-strict-aliasing", "-std=f2018"]


def build(compiler: str, target: str) -> dict:
    output = WELL / "bin" / target
    output.mkdir(parents=True, exist_ok=True)
    binary = output / ("raytrace.exe" if target == "windows" else "raytrace")
    flags = FLAGS + (["-static"] if target == "windows" else [])
    env = dict(os.environ)
    # The compiler finds its assembler and linker in its own folder.
    env["PATH"] = str(Path(compiler).resolve().parent) + os.pathsep + env.get("PATH", "")
    work = output / "raytrace_build"   # the compiler writes a .mod file here
    work.mkdir(exist_ok=True)
    command = [compiler, *flags, "-J", str(work), "-o", str(binary), str(SOURCE)]
    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=300)
    for leftover in work.iterdir():
        leftover.unlink()
    work.rmdir()
    if result.returncode:
        raise SystemExit(f"Compilation failed:\n{result.stderr}")
    version = subprocess.run([compiler, "--version"], capture_output=True, text=True, env=env).stdout.splitlines()[0]
    manifest = {"program": "raytrace", "compiler": compiler, "compiler_version": version, "target": target,
                "flags": flags, "source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
                "binary_sha256": sha256(binary.read_bytes()).hexdigest(), "command": command}
    (output / "raytrace_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Built {binary}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compiler", default="gfortran")
    parser.add_argument("--target", choices=("windows", "linux", "macos"), default="windows" if os.name == "nt" else "linux")
    args = parser.parse_args()
    build(args.compiler, args.target)


if __name__ == "__main__":
    main()
