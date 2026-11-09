"""Controlled reference comparison; never authorizes routine laboratory use.

Reference values can come from EFFTRAN/MEFFTRAN/WEFFTRAN, measurements or an
independent calculation. Their evidential roles are recorded, not conflated.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

from .parallel_coincidence import CoincidenceError, _publish_new

FIELDS = ("case_id", "geometry", "detector_id", "sample_id", "input_set_id", "nuclide", "line_id",
          "energy_keV", "quantity", "unit", "convention", "value", "u_standard",
          "source_file", "source_sha256")
GEOMETRIES = {"cylindrical", "marinelli", "well"}
CONVENTIONS = {"full_energy_efficiency": "absolute_probability",
               "transfer_factor": "multiply_reference_efficiency",
               "summing_activity_multiplier": "multiply_activity"}
KINDS = {"legacy_program", "measurement", "independent_simulation", "demonstration"}


def number(value, name, *, nonnegative=False):
    if isinstance(value, bool):
        raise ValueError(f"{name}: booleans are not numeric")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name}: a finite number is required") from exc
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f"{name}: invalid finite/nonnegative value")
    return result


def load_rows(path: Path) -> dict:
    result = {}
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"{path.name}: CSV header must match the supplied template")
        for line_number, raw in enumerate(reader, 2):
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"{path.name}:{line_number}: invalid column count")
            row = {name: value.strip() for name, value in raw.items()}
            for name in FIELDS:
                if name not in {"nuclide", "u_standard"} and not row[name]:
                    raise ValueError(f"{path.name}:{line_number}: missing {name}")
            if row["geometry"] not in GEOMETRIES or row["quantity"] not in CONVENTIONS:
                raise ValueError(f"{path.name}:{line_number}: unsupported geometry/quantity")
            if row["unit"] != "1" or row["convention"] != CONVENTIONS[row["quantity"]]:
                raise ValueError(f"{path.name}:{line_number}: normalize units/factor direction explicitly")
            row["energy_keV"] = number(row["energy_keV"], "energy_keV")
            row["value"] = number(row["value"], "value")
            if row["energy_keV"] <= 0 or row["value"] <= 0:
                raise ValueError("Efficiency energies and factors must be positive")
            if row["quantity"] == "full_energy_efficiency" and row["value"] > 1:
                raise ValueError("Full-energy efficiency is an absolute probability between zero and one")
            row["u_standard"] = number(row["u_standard"], "u_standard", nonnegative=True) if row["u_standard"] else None
            evidence = (path.parent/row["source_file"]).resolve()
            if not evidence.is_file() or sha256(evidence.read_bytes()).hexdigest() != row["source_sha256"]:
                raise ValueError(f"{path.name}:{line_number}: source evidence is missing or has changed")
            key = row["case_id"], row["quantity"], row["nuclide"], row["line_id"]
            if key in result:
                raise ValueError(f"{path.name}:{line_number}: duplicate case/quantity/nuclide/line")
            result[key] = row
    if not result:
        raise ValueError(f"{path.name}: no reference/candidate records; an empty comparison cannot pass")
    return result


def validate_plan(plan: dict) -> dict:
    if plan.get("schema_version") != 1 or plan.get("reference_kind") not in KINDS:
        raise ValueError("Unsupported plan schema or reference_kind")
    if type(plan.get("criteria_approved")) is not bool:
        raise ValueError("criteria_approved must be explicit true/false")
    if not isinstance(plan.get("plan_id"), str) or not plan["plan_id"].strip():
        raise ValueError("A controlled plan_id is required")
    if plan["criteria_approved"] and any(not isinstance(plan.get(name), str) or not plan[name].strip()
                                         for name in ("approved_by", "approved_date", "approval_record")):
        raise ValueError("Approved criteria need approver, date and an approval-record identifier")
    programs = plan.get("programs", {})
    for role in ("reference", "candidate"):
        entry = programs.get(role, {})
        if any(not isinstance(entry.get(name), str) or not entry[name].strip() for name in ("name", "version", "build_id")):
            raise ValueError(f"Record the {role} program name, version and build_id")
    rows = plan.get("criteria")
    if not isinstance(rows, list) or not rows:
        raise ValueError("At least one laboratory-defined comparison criterion is required")
    result = {}
    for entry in rows:
        key = entry.get("geometry"), entry.get("quantity")
        if key[0] not in GEOMETRIES or key[1] not in CONVENTIONS or key in result:
            raise ValueError("Invalid or duplicate geometry/quantity criterion")
        result[key] = {name: number(entry.get(name), name, nonnegative=True)
                       for name in ("atol", "rtol", "energy_tolerance_keV")}
        zmax = entry.get("maximum_standardized_difference")
        result[key]["maximum_standardized_difference"] = number(zmax, "maximum_standardized_difference", nonnegative=True) if zmax is not None else None
    return result


def compare_files(reference: Path, candidate: Path, plan_file: Path,
                  covariance_file: Path | None = None) -> dict:
    plan_raw = plan_file.read_bytes()
    plan = json.loads(plan_raw)
    criteria = validate_plan(plan)
    refs, candidates = load_rows(reference), load_rows(candidate)
    if refs.keys() != candidates.keys():
        raise ValueError("Reference and candidate line sets differ; missing/extra lines cannot be ignored")
    covariance = {}
    covariance_raw = None
    if covariance_file is not None:
        covariance_raw = covariance_file.read_bytes()
        records = json.loads(covariance_raw)
        if not isinstance(records, list):
            raise ValueError("Covariance file must contain a list of paired results")
        for row in records:
            key = tuple(row[name] for name in ("case_id", "quantity", "nuclide", "line_id"))
            if key in covariance or key not in refs or not isinstance(row.get("basis"), str) or not row["basis"].strip():
                raise ValueError("Covariance needs a unique known line and an explicit basis")
            covariance[key] = number(row["covariance"], "covariance")
    metrics = []
    for key, ref in refs.items():
        new = candidates[key]
        for name in ("geometry", "detector_id", "sample_id", "input_set_id", "quantity", "unit", "convention"):
            if ref[name] != new[name]:
                raise ValueError(f"{key}: mismatched {name}; confirm the same physical case and conventions")
        criterion = criteria.get((ref["geometry"], ref["quantity"]))
        if criterion is None:
            raise ValueError(f"{key}: no predeclared comparison criterion")
        if abs(ref["energy_keV"]-new["energy_keV"]) > criterion["energy_tolerance_keV"]:
            raise ValueError(f"{key}: energy mismatch; line identifiers are paired explicitly, never by nearest-neighbor guessing")
        delta = new["value"]-ref["value"]
        limit = criterion["atol"]+criterion["rtol"]*abs(ref["value"])
        metric = {"case_id": key[0], "geometry": ref["geometry"], "quantity": key[1],
                  "nuclide": key[2], "line_id": key[3], "energy_keV": ref["energy_keV"],
                  "reference": ref["value"], "candidate": new["value"],
                  "signed_difference": delta, "relative_difference": delta/ref["value"],
                  "tolerance": limit, "tolerance_passed": abs(delta) <= limit,
                  "standardized_difference": None, "uncertainty_check_passed": None}
        zmax = criterion["maximum_standardized_difference"]
        if zmax is not None:
            ur, uc = ref["u_standard"], new["u_standard"]
            if ur is None or uc is None or key not in covariance:
                raise ValueError(f"{key}: standard uncertainties and explicit cross-covariance are required")
            cov = covariance[key]
            if abs(cov) > ur*uc:
                raise ValueError(f"{key}: covariance violates the positive-semidefinite bound")
            # This rearrangement avoids a negative variance from cancellation
            # at perfect positive correlation.
            variance = (uc-ur)**2+2*(uc*ur-cov)
            if variance == 0:
                raise ValueError(f"{key}: zero uncertainty of difference; use a declared numerical criterion instead")
            z = delta/math.sqrt(variance)
            metric["standardized_difference"] = z
            metric["uncertainty_check_passed"] = abs(z) <= zmax
        metric["passed"] = metric["tolerance_passed"] and metric["uncertainty_check_passed"] is not False
        metrics.append(metric)
    numeric = all(metric["passed"] for metric in metrics)
    return {"schema_version": 1, "scope": "paired reference comparison only",
            "plan_id": plan["plan_id"], "reference_kind": plan["reference_kind"],
            "programs": plan["programs"], "criteria_approved": plan["criteria_approved"],
            "approval_metadata_is_not_authenticated": True,
            "numerical_comparison_passed": numeric,
            "controlled_comparison_passed": numeric and plan["criteria_approved"] and plan["reference_kind"] != "demonstration",
            "routine_use_authorized": False,
            "qualification_note": "This comparison cannot approve software, establish independent physical validity or authorize a laboratory release",
            "input_sha256": {"reference_csv": sha256(reference.read_bytes()).hexdigest(),
                             "candidate_csv": sha256(candidate.read_bytes()).hexdigest(),
                             "criteria_json": sha256(plan_raw).hexdigest(),
                             "covariance_json": sha256(covariance_raw).hexdigest() if covariance_raw is not None else None},
            "metrics": metrics}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--criteria", type=Path, required=True)
    parser.add_argument("--covariance", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("Output exists; choose a new filename")
        report = compare_files(args.reference, args.candidate, args.criteria, args.covariance)
        raw = (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()
        if args.output:
            _publish_new(args.output, raw)
        else:
            sys.stdout.write(raw.decode())
        return 0 if report["controlled_comparison_passed"] else 1
    except (OSError, ValueError, KeyError, TypeError, CoincidenceError) as exc:
        print(f"effsuite-compare-lab: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
