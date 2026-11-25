"""Standard uncertainty of the true coincidence summing (TCS) correction factors.

The original EFFTRAN 5.1, MEFFTRAN 2.0 and WEFFTRAN programs give each summing
correction factor C as a single value with no uncertainty. EffSuite adds one,
without changing the physics engines:

1. Sensitivity coefficients. The TCS factor depends on the full-energy peak
   efficiency curve eps_P(E) and on the total efficiency curve eps_T(E) of the
   sample geometry. We scale one complete curve by exp(+h) and then by exp(-h)
   (h = step, default 2 %), recalculate C with the unchanged engine, and take
   the central difference of ln C:

       S_P = d ln C / d ln eps_P ~ [ln C(eps_P e^h) - ln C(eps_P e^-h)] / 2h
       S_T = d ln C / d ln eps_T ~ [ln C(eps_T e^h) - ln C(eps_T e^-h)] / 2h

   Each S is the relative change of C per relative change of the efficiency
   (S_T = 0.08 means 10 % more total efficiency gives 0.8 % more C).

2. Combination (GUM law of propagation, first order):

       u_r(C)^2 = (S_P u_P)^2 + (S_T u_T)^2 + 2 rho S_P S_T u_P u_T + u_num^2

   u_P and u_T are the relative standard uncertainties of the model's peak and
   total efficiencies (user settings, defaults 5 % and 10 %), rho their
   correlation (default 0). u_num is the numerical uncertainty of the engine
   itself: the Monte Carlo statistical uncertainty of the efficiency
   integration (cylinder/Marinelli, column 4 of total.txt) or the change of C
   under quadrature refinement (well).

The result is a standard uncertainty (coverage factor k = 1) relative to C, in
percent. Decay-data uncertainties (emission probabilities, conversion
coefficients, level lifetimes) are NOT included: the decay libraries contain no
uncertainties. See docs/TCS_UNCERTAINTY.md for the full description.
"""
from __future__ import annotations

from dataclasses import replace
import math
from typing import Callable

from .parallel_coincidence import CoincidenceError, SharedInputs, _number

# Default settings. They are deliberately round "model quality" assumptions,
# not measured values: each laboratory should set its own (see docs/TCS_UNCERTAINTY.md).
DEFAULTS = {
    "enabled": True,
    "peak_efficiency_percent": 5.0,    # u_P: relative standard uncertainty of the computed peak efficiency
    "total_efficiency_percent": 10.0,  # u_T: relative standard uncertainty of the computed total efficiency
    "peak_total_correlation": 0.0,     # rho between the peak and total efficiency errors
    "step_percent": 2.0,               # h: finite-difference step of the sensitivity runs
}

# Per-line result fields (same names in results.json and summing.csv).
FIELDS = ("tcs_u_rel_percent", "tcs_u_peak_percent", "tcs_u_total_percent",
          "tcs_u_numerical_percent", "tcs_sensitivity_peak", "tcs_sensitivity_total")

NOT_INCLUDED = [
    "Decay data (emission probabilities, conversion coefficients, X-ray yields, level lifetimes): "
    "the EFFTRAN/WEFFTRAN decay libraries contain no uncertainties",
    "Energy dependence of the efficiency errors: each curve is scaled as a whole (fully correlated "
    "across energies), which is the dominant mode of a detector-model error",
    "Angular correlation of the cascade photons (not modelled by the engines)",
    "Random summing, dead time and the uncertainty of the uncorrected peak areas",
]


def empty_fields() -> dict:
    """The per-line fields when no uncertainty is available (all None)."""
    return dict.fromkeys(FIELDS)


def zero_fields() -> dict:
    """The per-line fields of a line with no coincidence at all (C = 1 exactly)."""
    return dict.fromkeys(FIELDS, 0.0)


def _real(value, name: str, low: float, high: float) -> float:
    """A real number between low and high (true/false and text are refused)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CoincidenceError(f"TCS uncertainty: {name} must be a number")
    if not low <= value <= high:
        raise CoincidenceError(f"TCS uncertainty: {name} must be between {low:g} and {high:g}")
    return float(value)


def validate_settings(raw) -> dict:
    """Check the project's "tcs_uncertainty" section; missing keys get the defaults."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise CoincidenceError("tcs_uncertainty must be an object (dictionary)")
    unknown = set(raw) - set(DEFAULTS)
    if unknown:
        raise CoincidenceError("Unknown tcs_uncertainty setting(s): " + ", ".join(sorted(unknown)))
    settings = {**DEFAULTS, **raw}
    if not isinstance(settings["enabled"], bool):
        raise CoincidenceError("TCS uncertainty: enabled must be true or false")
    settings["peak_efficiency_percent"] = _real(settings["peak_efficiency_percent"], "peak_efficiency_percent", 0, 100)
    settings["total_efficiency_percent"] = _real(settings["total_efficiency_percent"], "total_efficiency_percent", 0, 100)
    settings["peak_total_correlation"] = _real(settings["peak_total_correlation"], "peak_total_correlation", -1, 1)
    settings["step_percent"] = _real(settings["step_percent"], "step_percent", .1, 10)
    return settings


# ---------------------------------------------------------------------------
# Sensitivity coefficients
# ---------------------------------------------------------------------------

def _central_difference(plus: float | None, minus: float | None, step: float) -> float | None:
    """d ln C / d ln eps from C at eps*e^step and eps*e^-step (None if a factor is unusable)."""
    if plus is None or minus is None or not (plus > 0 and minus > 0):
        return None
    value = (math.log(plus) - math.log(minus)) / (2 * step)
    return value if math.isfinite(value) else None


def _rows(raw: bytes) -> list[list[float]]:
    """Rows [energy, value, second value] of efficiency.txt or buildup.txt."""
    return [[_number(token) for token in line.split()[:3]] for line in raw.splitlines() if line.strip()]


def _curve_bytes(rows: list[list[float]]) -> bytes:
    """Write rows back with 10 significant digits (the engines read them list-directed)."""
    return "".join(f"{e:.9e} {a:.9e} {b:.9e}\n" for e, a, b in rows).encode("ascii")


def scaled_inputs(inputs: SharedInputs, peak_scale: float, total_scale: float) -> SharedInputs:
    """Cylinder/Marinelli engine inputs with the peak (efficiency.txt) and total
    (buildup.txt) efficiency curves multiplied by the given factors.

    Both columns of each file are scaled (the mean and the second-moment
    efficiency of the sample volume), so their ratio is kept. Total efficiency
    is capped at 1 and peak efficiency at the total efficiency.
    """
    peak, total = _rows(inputs.efficiency), _rows(inputs.buildup)
    if len(peak) != len(total):
        raise CoincidenceError("Efficiency and buildup curves have different lengths")
    new_total = [[e, min(1., a * total_scale), min(1., b * total_scale)] for e, a, b in total]
    new_peak = [[e, min(a * peak_scale, t[1]), min(b * peak_scale, t[2])]
                for (e, a, b), t in zip(peak, new_total)]
    return SharedInputs(_curve_bytes(new_peak), _curve_bytes(new_total), inputs.library)


def parse_coin(raw: bytes) -> dict[tuple[str, int], float | None]:
    """{(nuclide, energy): factor} from coin.txt bytes (None for a non-positive factor)."""
    factors = {}
    for line in raw.splitlines():
        factor = _number(line[20:].strip())
        factors[(line[:10].decode("ascii").strip(), int(line[10:20]))] = factor if factor > 0 else None
    return factors


def cascade_sensitivities(inputs: SharedInputs, run: Callable[[SharedInputs], bytes],
                          step: float) -> dict[tuple[str, int], tuple[float | None, float | None]]:
    """S_P and S_T of every cylinder/Marinelli line.

    ``run`` calculates coin.txt bytes for given engine inputs (the unchanged
    coincidence program). Four runs: peak x e^+-step, total x e^+-step.
    """
    up, down = math.exp(step), math.exp(-step)
    peak_plus, peak_minus = parse_coin(run(scaled_inputs(inputs, up, 1.))), parse_coin(run(scaled_inputs(inputs, down, 1.)))
    total_plus, total_minus = parse_coin(run(scaled_inputs(inputs, 1., up))), parse_coin(run(scaled_inputs(inputs, 1., down)))
    keys = set(peak_plus) | set(peak_minus) | set(total_plus) | set(total_minus)
    return {key: (_central_difference(peak_plus.get(key), peak_minus.get(key), step),
                  _central_difference(total_plus.get(key), total_minus.get(key), step)) for key in keys}


def scaled_local(local, peak_scale: float, total_scale: float):
    """Well model: the local (per sample point) efficiencies multiplied by the given factors.

    Total is capped at 1 and peak at total. The precomputed 511-keV pair terms
    follow: the probability that at least one annihilation photon is detected
    scales with the total efficiency, the single-photon peak term with the
    peak efficiency.
    """
    import numpy as np
    total = np.minimum(local.total * total_scale, 1.)
    peak = np.minimum(local.peak * peak_scale, total)
    pair_miss = None if local.pair_miss is None else np.clip(1 - total_scale * (1 - local.pair_miss), 0., 1.)
    pair_single = None if local.pair_single_peak is None else np.clip(local.pair_single_peak * peak_scale, 0., 1.)
    return replace(local, peak=peak, total=total, pair_miss=pair_miss, pair_single_peak=pair_single)


def well_sensitivities(local, evaluate: Callable, step: float) -> dict[tuple[str, int], tuple[float | None, float | None]]:
    """S_P and S_T of every well line.

    ``evaluate(local)`` returns ((nuclide, {"corrections": [...]} or {"error": ...}), ...)
    for the given local efficiencies (the unchanged cascade calculation).
    """
    def factors(peak_scale, total_scale):
        found = {}
        for name, item in evaluate(scaled_local(local, peak_scale, total_scale)):
            for row in item.get("corrections", ()):
                found[(name, row["energy_kev"])] = row["factor"]
        return found
    up, down = math.exp(step), math.exp(-step)
    peak_plus, peak_minus, total_plus, total_minus = factors(up, 1.), factors(down, 1.), factors(1., up), factors(1., down)
    keys = set(peak_plus) | set(peak_minus) | set(total_plus) | set(total_minus)
    return {key: (_central_difference(peak_plus.get(key), peak_minus.get(key), step),
                  _central_difference(total_plus.get(key), total_minus.get(key), step)) for key in keys}


# ---------------------------------------------------------------------------
# Combination
# ---------------------------------------------------------------------------

def line_uncertainty(s_peak: float | None, s_total: float | None, settings: dict,
                     numerical: float | None) -> dict:
    """Per-line fields from the sensitivities, the settings and the numerical term.

    ``numerical`` is the relative numerical uncertainty of C (a fraction), or
    None when unknown (it is then left out of the total).
    """
    if s_peak is None or s_total is None:
        return empty_fields()
    u_p = settings["peak_efficiency_percent"] / 100
    u_t = settings["total_efficiency_percent"] / 100
    rho = settings["peak_total_correlation"]
    peak_part, total_part = s_peak * u_p, s_total * u_t
    # A quadratic form with |rho| <= 1 is never negative; max() removes roundoff.
    variance = max(0., peak_part**2 + total_part**2 + 2 * rho * peak_part * total_part)
    if numerical is not None:
        variance += numerical**2
    return {"tcs_u_rel_percent": 100 * math.sqrt(variance),
            "tcs_u_peak_percent": 100 * abs(peak_part),
            "tcs_u_total_percent": 100 * abs(total_part),
            "tcs_u_numerical_percent": None if numerical is None else 100 * numerical,
            "tcs_sensitivity_peak": s_peak, "tcs_sensitivity_total": s_total}


def monte_carlo_uncertainty(total_txt: bytes) -> float | None:
    """Largest relative Monte Carlo uncertainty (fraction) in column 4 of total.txt.

    EFFTRAN 5.1 / MEFFTRAN 2.0 total.f writes it; older 3-column files give None.
    """
    values = []
    for line in total_txt.splitlines():
        fields = line.split()
        if len(fields) < 4:
            return None
        values.append(_number(fields[3]))
    return max(values) if values else None


def summary(settings: dict, numerical_kind: str, monte_carlo: float | None = None) -> dict:
    """The "tcs_uncertainty" section of results.json: settings, method and limits."""
    out = {
        "enabled": settings["enabled"],
        "settings": dict(settings),
        "quantity": "relative standard uncertainty of the TCS correction factor C (coverage factor k = 1), percent",
        "method": "first-order propagation with sensitivity coefficients S = d ln C / d ln eps, from central "
                  "differences of the unchanged engine with the peak and total efficiency curves scaled by exp(+-h)",
        "equation": "u_r(C)^2 = (S_P u_P)^2 + (S_T u_T)^2 + 2 rho S_P S_T u_P u_T + u_num^2",
        "numerical_component": numerical_kind,
        "not_included": NOT_INCLUDED,
        "documentation": "docs/TCS_UNCERTAINTY.md",
    }
    if monte_carlo is not None:
        out["monte_carlo_relative_uncertainty_percent"] = 100 * monte_carlo
    return out


def recompute(row: dict, settings: dict) -> float | None:
    """u_r(C) in percent of one result line for other settings, without running the engine.

    The sensitivities and the numerical term stored in the line do not depend
    on u_P, u_T or rho, so this gives exactly what a new calculation would.
    None when the calculation is switched off or the line has no sensitivities
    (for example a run made with the calculation switched off).
    """
    if not settings["enabled"]:
        return None
    numerical = row.get("tcs_u_numerical_percent")
    return line_uncertainty(row.get("tcs_sensitivity_peak"), row.get("tcs_sensitivity_total"), settings,
                            None if numerical is None else numerical / 100)["tcs_u_rel_percent"]


def match_uncertainty(result: dict, nuclide: str, energy: float, settings: dict | None = None) -> float | None:
    """u_r(C) in percent of the result line closest to (nuclide, energy) within 1 keV, or None.

    With ``settings``, the value is recalculated for those settings (see recompute);
    otherwise it is the value stored by the calculation.
    """
    from .model_io import canonical_nuclide
    wanted = canonical_nuclide(nuclide)
    nearby = [row for row in result.get("summing", ())
              if canonical_nuclide(row["nuclide"]) == wanted and abs(row["energy_keV"] - energy) < 1.0]
    if not nearby:
        return None
    row = min(nearby, key=lambda row: abs(row["energy_keV"] - energy))
    return row.get("tcs_u_rel_percent") if settings is None else recompute(row, settings)
