"""Build the bundled source engines without changing their scientific routines."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/"src/effsuite/assets/engines"
COMMON = ("mine", "energy", "total", "scatter", "buildup", "eta", "ptt", "efficiency", "transfer")


def build(compiler, target, extra=()):
    manifest = {"compiler": compiler, "target": target, "flags": list(extra), "programs": []}
    version = subprocess.run([compiler, "--version"], capture_output=True, text=True, check=True)
    manifest["compiler_version"] = version.stdout
    flags = ["-O2", "-std=legacy", "-fno-fast-math", "-ffp-contract=off", "-fno-use-linker-plugin"]
    probe = subprocess.run([compiler, "-fallow-argument-mismatch", "-E", "-"], input="", text=True, capture_output=True)
    if probe.returncode == 0 or "unrecognized command line option" not in probe.stderr:
        flags.append("-fallow-argument-mismatch")
    if target == "windows": flags += ["-static"]
    jobs = []
    for mode in ("cylindrical", "marinelli", "well"):
        folder = ASSETS/mode
        output = folder/"bin"/target
        output.mkdir(parents=True, exist_ok=True)
        for stage in COMMON + (("coincidence",) if mode != "well" else ("initialize", "emissions", "emissions2", "peak", "correct")):
            jobs.append((mode, folder, output, stage))

    def compile_job(job):
        mode, folder, output, stage = job
        source = folder/"source"/(stage+".f")
        raw = source.read_bytes()
        copy = output/(stage+".f")
        text = raw.decode("cp1252")
        output_change = None
        if stage == "coincidence":
            text, changed = re.subn(r"(?i)format\(a10,i10,f15\.3\)", "format(a10,i10,e23.15)", text)
            if changed != 1:raise RuntimeError("Cannot identify the legacy summing output format")
            output_change = "Text output F15.3 -> E23.15; scientific arithmetic is unchanged"
        if target != "windows": text = text.replace("\\\\", "/")
        copy.write_text(text)
        binary = output/(stage+(".exe" if target == "windows" else ""))
        cmd = [compiler, *extra, *flags, "-w", "-o", str(binary), str(copy)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode: raise RuntimeError(f"{mode}/{stage}: {result.stderr}")
        copy.unlink()
        print(mode, stage, flush=True)
        return {"geometry": mode, "stage": stage, "source_sha256": sha256(raw).hexdigest(),
                "compiled_source_sha256":sha256(text.encode()).hexdigest(),"output_format_change":output_change,
                "binary_sha256": sha256(binary.read_bytes()).hexdigest(), "command": cmd}
    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest["programs"] = list(pool.map(compile_job, jobs))
    for mode in ("cylindrical", "marinelli", "well"):
        (ASSETS/mode/"bin"/target/"build_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--compiler", default="gfortran")
    p.add_argument("--compiler-arg", action="append", default=[])
    p.add_argument("--target", choices=("windows", "linux", "macos"), default="windows" if os.name=="nt" else "linux")
    a=p.parse_args()
    build(a.compiler,a.target,a.compiler_arg)

if __name__=="__main__":main()
