"""Rebuild native references and reproduce the spatial WEFFTRAN fix checks.

Only temporary source copies/job directories are written. Source-guided
numerical checks do not establish a measurement uncertainty or lab validation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
import numpy as np
from effsuite.spatial_summing import LocalEfficiencies, integrated_counts, required_energies
from effsuite.well_spatial import calculate_spatial, load_groups

STAGES = ("mine", "energy", "total", "scatter", "buildup", "eta", "ptt", "efficiency",
          "initialize", "emissions", "emissions2", "peak", "correct")


def validate(original: Path, compiler: list[str]) -> dict:
    names = ("CO-60", "CS-134", "EU-152", "NA-22")
    groups = load_groups(original, names)
    report = {"scope": "Numerical/regression tests, not laboratory qualification",
              "compiler_command": compiler, "python": sys.version, "numpy": np.__version__,
              "point_reference": {}, "height_cases": []}
    with TemporaryDirectory(prefix="weff-spatial-validation-") as temporary:
        root = Path(temporary)
        executables = {}
        for stage in (*STAGES, "peak_org"):
            source = original/(stage+".f")
            text = source.read_text(encoding="cp1252")
            if os.name != "nt":
                text = text.replace("\\\\", "/")
            saved = root/(stage+".f")
            saved.write_text(text)
            exe = root/(stage+(".exe" if os.name == "nt" else ""))
            subprocess.run(compiler+["-O3", "-w", "-o", str(exe), str(saved)],
                           check=True, capture_output=True, timeout=60)
            executables[stage] = exe

        def run(stage, work):
            subprocess.run([str(executables[stage])], cwd=work, check=True,
                           capture_output=True, timeout=60)

        def native_group(name, work, peak="peak"):
            run("initialize", work)
            for label in (name, name+"b"):
                path = original/"Decay_Data"/(label+".txt")
                if path.is_file():
                    shutil.copyfile(path, work/"coin.txt")
                    for stage in ("emissions", "emissions2", peak):
                        run(stage, work)
            run("correct", work)
            return {filename: (work/filename).read_bytes()
                    for filename in ("emissions.txt", "peak.txt", "correct.txt")}

        # Point-response reference: no spatial variation and no second-moment
        # subtraction. Constant curves make interpolation independently exact.
        work = root/"point"
        work.mkdir()
        (work/"efficiency.txt").write_text("1 .1 .1\n3000 .1 .1\n")
        (work/"buildup.txt").write_text("1 .2 .2\n3000 .2 .2\n")
        (work/"param.txt").write_text("10.\n")
        for name, records in load_groups(original, ("CO-60", "CS-134", "BA-133")):
            native = native_group(name, work, "peak_org")
            energy = required_energies(records)
            local = LocalEfficiencies(energy, np.ones(1), np.full((1,len(energy)), .1),
                                       np.full((1,len(energy)), .2), np.zeros((1,2)), {})
            python = integrated_counts(records, local, 10.)
            observed = {row["energy_kev"]: row for row in python["corrections"]}
            reference = {int(line.split()[0]): float(line.split()[1])
                         for line in native["correct.txt"].splitlines()}
            assert set(reference) == set(observed)
            changes = [abs(observed[e]["factor"]-value)/abs(value) for e,value in reference.items()]
            assert max(changes) < 1e-4, (name, max(changes))
            report["point_reference"][name] = {"lines": len(changes), "maximum_relative_difference": max(changes),
                "acceptance": "1e-4 relative, reflecting five-significant-digit native text",
                "native_output_sha256": {filename: sha256(raw).hexdigest() for filename,raw in native.items()}}

        for height in (3.25, 31.499, 31.5, 31.501, 32.5, 50., 69.1, 100.):
            print(f"Height {height:g} mm", flush=True)
            work = root/("height_"+str(height))
            work.mkdir()
            for folder in ("Composition", "Material"):
                shutil.copytree(original/folder, work/folder)
            shutil.copyfile(original/"zzaa.txt", work/"zzaa.txt")
            shutil.copyfile(original/"param.txt", work/"param.txt")
            shutil.copyfile(original/"Detector/DET07.txt", work/"detector.txt")
            source = (original/"Sample/Plastic_vial_5mL.txt").read_text().splitlines()
            source[1] = str(height)
            (work/"source.txt").write_text("\n".join(source)+"\n")
            for stage in STAGES[:8]:
                run(stage, work)
            legacy = {}
            for name in names:
                raw = native_group(name, work)["correct.txt"]
                legacy[name] = {int(line.split()[0]): float(line.split()[1]) for line in raw.splitlines()}
            result = calculate_spatial(original, work, names, workers=4, verify_serial=True)
            assert result["convergence"]["passed"], result["convergence"]
            assert result["transport"]["probability_saturation_count"] == 0
            for item in result["nuclides"]:
                assert item["corrections"]
                for row in item["corrections"]:
                    assert row["factor"] is not None and row["factor"] > 0
                    row["legacy_factor"] = legacy[item["nuclide"]].get(row["energy_kev"])
            report["height_cases"].append({"sample_height_mm": height, **result})
        neighbors = [case for case in report["height_cases"] if 31.49 < case["sample_height_mm"] < 31.51]
        by_height = {}
        for case in neighbors:
            by_height[case["sample_height_mm"]] = {(item["nuclide"], row["energy_kev"]): row["factor"]
                                                   for item in case["nuclides"] for row in item["corrections"]}
        low, at, high = (by_height[height] for height in (31.499, 31.5, 31.501))
        relative = max(abs(high[key]-low[key])/at[key] for key in at)
        assert relative < .001
        report["crystal_rim_continuity"] = {"sample_heights_mm": [31.499,31.5,31.501],
                                            "maximum_relative_factor_change": relative, "passed": True}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--compiler", default="gfortran")
    parser.add_argument("--compiler-arg", action="append", default=[])
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Choose a new report filename")
    result = validate(args.original, [args.compiler, *args.compiler_arg])
    with args.report.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, allow_nan=False)
        target.write("\n")


if __name__ == "__main__":
    main()
