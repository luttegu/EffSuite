"""Audit WEFFTRAN's printed intermediates without changing its equations.

A missing or invalid correction is never represented by a multiplier of one.
These checks do not qualify the scientific model or the Genie COM writer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

from .parallel_coincidence import CoincidenceError


def spectrum(raw: bytes, filename: str) -> dict[int, float]:
    values: dict[int, float] = {}
    for number, line in enumerate(raw.splitlines(), 1):
        fields = line.split()
        if len(fields) != 2:
            raise CoincidenceError(f"{filename}:{number}: expected energy and value")
        try:
            energy = int(fields[0])
            value = float(fields[1].replace(b"D", b"E").replace(b"d", b"e"))
        except ValueError as exc:
            raise CoincidenceError(f"{filename}:{number}: malformed value") from exc
        if energy in values or not 1 <= energy <= 3000 or not math.isfinite(value):
            raise CoincidenceError(f"{filename}:{number}: duplicate, nonfinite or out-of-range value")
        values[energy] = value
    return values


@dataclass(frozen=True)
class Correction:
    energy_kev: int
    status: str
    factor: float | None
    legacy_factor: float | None
    denominator: float
    cancellation_ratio: float
    numerator: float
    peak: float
    emissions2: float

    def to_object(self) -> dict:
        return asdict(self)


def audit_corrections(emissions: bytes, peak: bytes, emissions2: bytes,
                      correct: bytes, *, minimum_ratio: float = 1e-3) -> tuple[Correction, ...]:
    """Identify nonpositive counts and cancellation in x / (peak - x2 + x).

    `minimum_ratio` is an explicit export review policy, not a physics cutoff.
    The ratio is |denominator|/(|peak|+|x2|+|x|); below 0.001 the absolute
    summand errors can be amplified by over 1000. Set it to zero to disable
    that policy. Positive factors below one are supported (summing-in).
    Intermediates are rounded legacy text, not hidden full-precision values.
    """
    if not math.isfinite(minimum_ratio) or not 0 <= minimum_ratio <= 1:
        raise CoincidenceError("minimum_ratio must be between zero and one")
    x = spectrum(emissions, "emissions.txt")
    p = spectrum(peak, "peak.txt")
    x2 = spectrum(emissions2, "emissions2.txt")
    c = spectrum(correct, "correct.txt")
    expected = set(range(1, 3001))
    if set(x) != expected or set(p) != expected or set(x2) != expected:
        raise CoincidenceError("Intermediate spectra must contain all 3000 energy bins")
    results = []
    for energy in sorted((set(c) | {e for e in x if x[e] > 0}) - {1}):
        numerator, peaked, second = x[energy], p[energy], x2[energy]
        denominator = peaked - second + numerator
        scale = abs(peaked) + abs(second) + abs(numerator)
        ratio = abs(denominator) / scale if scale else 0.
        factor = c.get(energy)
        if numerator <= 0:
            status = "no_direct_peak"
        elif min(peaked, second) < 0 or denominator <= 0 or (factor is not None and factor <= 0):
            status = "invalid"
        elif factor is None:
            status = "missing"
        elif ratio < minimum_ratio:
            status = "review_cancellation"
        else:
            status = "candidate"
        results.append(Correction(energy, status, factor if status == "candidate" else None,
                                  factor, denominator, ratio, numerator, peaked, second))
    return tuple(results)


def plan_nlb_updates(lines: tuple[tuple[str, float, float], ...],
                     corrections: dict[str, tuple[Correction, ...]]) -> tuple[dict, ...]:
    """Prepare abundance/C edits; do not access CAM or write an NLB file.

    Every requested line must have one candidate within the legacy strict
    one-keV window. Any missing, ambiguous or failed match aborts the plan.
    A successful plan is still subject to scientific qualification and CAM
    round-trip validation. The input library remains unchanged.
    """
    updates = []
    for nuclide, energy, abundance in lines:
        if not (math.isfinite(energy) and energy > 0 and math.isfinite(abundance) and abundance >= 0):
            raise CoincidenceError("NLB energy and abundance must be finite physical values")
        rows = corrections.get(nuclide, ())
        nearby = [row for row in rows if abs(row.energy_kev - energy) < 1.]
        if not nearby:
            raise CoincidenceError(f"{nuclide} {energy:g} keV: correction missing")
        distance = min(abs(row.energy_kev - energy) for row in nearby)
        closest = [row for row in nearby if abs(row.energy_kev - energy) == distance]
        if len(closest) != 1:
            raise CoincidenceError(f"{nuclide} {energy:g} keV: ambiguous correction")
        row = closest[0]
        if row.status != "candidate" or row.factor is None:
            raise CoincidenceError(f"{nuclide} {energy:g} keV: {row.status}; export blocked")
        corrected = abundance / row.factor
        if not math.isfinite(corrected):
            raise CoincidenceError(f"{nuclide} {energy:g} keV: abundance overflow")
        updates.append({"nuclide": nuclide, "energy_kev": energy, "factor": row.factor,
                        "original_abundance": abundance, "corrected_abundance": corrected})
    return tuple(updates)
