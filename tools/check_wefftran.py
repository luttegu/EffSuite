"""Validate the geometry patch against an extracted WEFFTRAN source directory.

Requires a native GNU Fortran compiler. Uses temporary build and job directories;
the original installation is read only. This does not validate Windows binaries
when executed on Linux, or establish independent accuracy of the physics model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time
import os
import sys
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "native/wefftran_geometry"
PATH_PATTERN = r"(?im)^\s*subroutine path\([^\n]*\n.*?^\s*end\s*$"
STAGES = ["mine", "energy", "total", "scatter", "buildup", "eta", "ptt", "efficiency",
          "initialize", "emissions", "emissions2", "peak", "correct"]


def check(original: Path, compiler: list[str], all_nuclides=False) -> dict:
    sys.path.insert(0, str(ROOT / "src"))
    from effsuite.well_parallel import WellInputs, STAGES as WELL_STAGES, NAME, calculate_well_parallel
    report = {"platform": os.name, "compiler_command": compiler,
              "scope": "Native geometry and supplied versus patched source comparison",
              "full_physics_qualification": False}
    with TemporaryDirectory(prefix="well-verify-") as temporary:
        work = Path(temporary)

        def compile_source(source: Path, name: str, routine_only=False) -> Path:
            text = source.read_text(encoding="cp1252")
            if routine_only:
                text = re.search(PATH_PATTERN, text, re.S).group(0) + "\n"
            elif os.name != "nt":
                # File-path adaptation only, in the temporary validation copy.
                text = text.replace("\\\\", "/")
            saved = work / (name + ".f")
            saved.write_text(text)
            executable = work / (name + (".exe" if os.name == "nt" else ""))
            sources = [str(work / "driver.f90"), str(saved)] if routine_only else [str(saved)]
            result = subprocess.run(compiler + ["-O3", "-w", "-o", str(executable), *sources],
                                    capture_output=True, text=True, timeout=60)
            if result.returncode:
                raise RuntimeError(f"Compile {source.name}: {result.stderr}")
            return executable

        (work / "driver.f90").write_text('''program check_path
implicit none
real(8) :: zlo,zup,r2,x0,z0,tx,ty,tz,d
integer :: ios
do
read(*,*,iostat=ios) zlo,zup,r2,x0,z0,tx,ty,tz
if (ios /= 0) exit
call path(zlo,zup,r2,x0,z0,tx,ty,tz,d)
write(*,'(ES25.17)') d
end do
end program
''')
        paths = {"legacy": compile_source(original / "total_org.f", "ray_legacy", True),
                 "supplied": compile_source(original / "total.f", "ray_supplied", True),
                 "fixed": compile_source(PATCH / "path_fixed.f", "ray_fixed", True)}

        def evaluate(name, cases):
            text = "".join(" ".join(format(v, ".17g") for v in row) + "\n" for row in cases)
            result = subprocess.run([str(paths[name])], input=text, capture_output=True,
                                    text=True, check=True, timeout=30)
            return result.stdout.splitlines(), [float(v) for v in result.stdout.splitlines()]

        rng = random.Random(20261030)

        def ray(inside):
            radius = rng.uniform(1, 100)
            bottom = rng.uniform(-20, 20)
            top = bottom + rng.uniform(1, 100)
            x = rng.uniform(0, (.95 if inside else 2) * radius)
            z = rng.uniform(bottom, top) if inside else rng.uniform(bottom - 2*(top-bottom), top + 2*(top-bottom))
            uz, phi = rng.uniform(-.99, .99), rng.uniform(0, 2 * math.pi)
            ux, uy = math.sqrt(1-uz*uz)*math.cos(phi), math.sqrt(1-uz*uz)*math.sin(phi)
            return bottom, top, radius*radius, x, z, ux, uy, uz

        interior = [ray(True) for _ in range(2000)]
        assert evaluate("legacy", interior)[0] == evaluate("fixed", interior)[0]
        cases = [ray(False) for _ in range(4000)]
        observed = evaluate("fixed", cases)[1]
        errors = []
        for case, value in zip(cases, observed):
            bottom, top, radius2, x, z, ux, uy, uz = case
            # Independent closest-approach/chord construction, rather than
            # the stable quadratic-root implementation being tested.
            transverse = ux*ux + uy*uy
            center = -x*ux/transverse
            closest_squared = x*x - (x*ux)**2/transverse
            if closest_squared >= radius2:
                expected = 0.
            else:
                half = math.sqrt((radius2-closest_squared)/transverse)
                low, high = sorted(((bottom-z)/uz, (top-z)/uz))
                expected = max(0., min(center+half, high) - max(0., center-half, low))
            errors.append(abs(value-expected))
        assert max(errors) < 1e-9
        analytic = [(0,69,36**2,0,80,.8,0,.6),
                    (0,69,36**2,0,80,0,0,-1), (26,69,12.75**2,0,80,0,0,-1)]
        report["rays"] = {"unchanged_interior_cases": 2000,
                          "independent_comparisons": 4000,
                          "max_absolute_error_mm": max(errors),
                          "analytic_cases": {name: evaluate(name, analytic)[1] for name in paths}}
        assert report["rays"]["analytic_cases"]["fixed"] == [0.,69.,43.]

        executables = {name: compile_source(original / (name + ".f"), "full_" + name)
                       for name in STAGES}
        patched = {name: compile_source(PATCH / (name + ".f"), "fixed_" + name)
                   for name in ("total", "scatter", "eta")}
        original_peak = compile_source(original / "peak_org.f", "original_peak")
        height_cases = []
        for height in (3.25, 31.5, 32.5, 50., 100.):
            row = {"sample_height_mm": height, "sample_top_z_mm": 37.5 + height, "variants": {}}
            for variant in ("supplied", "fixed"):
                case = work / f"case_{height}_{variant}"
                case.mkdir()
                for directory in ("Composition", "Material"):
                    shutil.copytree(original / directory, case / directory)
                for filename in ("zzaa.txt", "param.txt"):
                    shutil.copyfile(original / filename, case / filename)
                shutil.copyfile(original / "Detector/DET07.txt", case / "detector.txt")
                sample = (original / "Sample/Plastic_vial_5mL.txt").read_text().splitlines()
                sample[1] = str(height)
                (case / "source.txt").write_text("\n".join(sample) + "\n")

                def run(stage):
                    executable = patched[stage] if variant == "fixed" and stage in patched else executables[stage]
                    result = subprocess.run([str(executable)], cwd=case, capture_output=True,
                                            text=True, timeout=30)
                    if result.returncode:
                        raise RuntimeError(f"{height}/{variant}/{stage}: {result.stderr}")

                started = time.monotonic()
                for stage in STAGES[:8]:
                    run(stage)
                nuclide_results = {}
                for nuclide in ("CO-60", "CS-134", "EU-152"):
                    run("initialize")
                    for name in (nuclide, nuclide + "b"):
                        decay = original / "Decay_Data" / (name + ".txt")
                        if decay.is_file():
                            shutil.copyfile(decay, case / "coin.txt")
                            for stage in ("emissions", "emissions2", "peak"):
                                run(stage)
                    run("correct")
                    raw = (case / "correct.txt").read_bytes()
                    values = [[float(v) for v in line.split()] for line in raw.decode().splitlines()]
                    assert values and all(math.isfinite(v) for line in values for v in line)
                    nuclide_results[nuclide] = {"sha256": hashlib.sha256(raw).hexdigest(), "rows": values}
                row["variants"][variant] = {"seconds": time.monotonic()-started,
                                              "nuclides": nuclide_results}
                if height == 50. and variant == "supplied":
                    # The original peak routine independently reproduces the
                    # Eu-152 failure; it is not caused by the Na-22 modification.
                    run("initialize")
                    for name in ("EU-152", "EU-152b"):
                        decay = original / "Decay_Data" / (name + ".txt")
                        if decay.is_file():
                            shutil.copyfile(decay, case / "coin.txt")
                            run("emissions")
                            run("emissions2")
                            subprocess.run([str(original_peak)], cwd=case, check=True,
                                           capture_output=True, timeout=30)
                    run("correct")
                    report["original_peak_eu152_50mm_matches_supplied"] = (
                        hashlib.sha256((case / "correct.txt").read_bytes()).hexdigest() ==
                        nuclide_results["EU-152"]["sha256"])
                    names = tuple(sorted(p.stem for p in (original / "Decay_Data").glob("*.txt")
                                         if NAME.fullmatch(p.stem))) if all_nuclides else ("CO-60", "CS-134", "EU-152")
                    inputs = WellInputs.from_directories(case, original / "Decay_Data", names)
                    commands = {stage: (str(executables[stage]),) for stage in WELL_STAGES}
                    parallel = calculate_well_parallel(inputs, commands, workers=4, verify_serial=True)
                    # Also compare with the independently driven coin2 sequence above.
                    output = {name: dict(files) for name, files in parallel.nuclides}
                    assert all(hashlib.sha256(output[name]["correct.txt"]).hexdigest() ==
                               nuclide_results[name]["sha256"] for name in nuclide_results)
                    summary = {key: value for key, value in parallel.report.items() if key != "nuclides"}
                    summary["independent_coin2_sequence_matches"] = True
                    summary["nuclides"] = [
                        {key: value for key, value in item.items() if key != "corrections"} |
                        {"status_counts": dict(Counter(c["status"] for c in item["corrections"]))}
                        for item in parallel.report["nuclides"]]
                    report["well_parallel"] = summary
                    eu = next(item for item in parallel.report["nuclides"] if item["nuclide"] == "EU-152")
                    report["eu152_50mm_failure_diagnostics"] = [c for c in eu["corrections"]
                                                               if c["status"] != "candidate"]
            row["correction_outputs_identical"] = all(
                row["variants"]["supplied"]["nuclides"][n]["sha256"] ==
                row["variants"]["fixed"]["nuclides"][n]["sha256"]
                for n in ("CO-60", "CS-134", "EU-152"))
            height_cases.append(row)
        report["height_cases"] = height_cases
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--compiler", default="gfortran")
    parser.add_argument("--compiler-arg", action="append", default=[])
    parser.add_argument("--report", type=Path)
    parser.add_argument("--all-nuclides", action="store_true",
                        help="Compare serial and parallel output for all parent Decay_Data files")
    args = parser.parse_args()
    result = check(args.original, [args.compiler, *args.compiler_arg], args.all_nuclides)
    text = json.dumps(result, indent=2, allow_nan=False)
    if args.report:
        with args.report.open("x", encoding="utf-8") as target:
            target.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
