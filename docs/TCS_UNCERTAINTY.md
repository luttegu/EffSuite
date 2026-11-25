# Uncertainty of the True Coincidence Summing Correction Factors

EffSuite gives every true coincidence summing (TCS) correction factor *C* a
**relative standard uncertainty u(C)** (coverage factor *k* = 1, in percent).
This document describes what is calculated, the inputs you must provide, how to
read the results and what is not included.

> **Not in the original programs.** EFFTRAN 5.1, MEFFTRAN 2.0 and WEFFTRAN give
> *C* as a single value: `coin.f` / `correct.f` write only nuclide, energy and
> factor, and the *Coincidence Summing* workbooks show only "Correction Factor".
> The only uncertainty in the originals is the efficiency-transfer uncertainty
> (`transfer.f`). u(C) is an EffSuite addition and has no original reference
> to compare with. The factors *C* themselves are unchanged.

---

## 1. What *C* depends on

For each gamma line, the engine computes

  *C* = (peak counts expected without summing) / (peak counts expected with summing),

so that *A*<sub>corrected</sub> = *C* · *A*. Both counts come from the cascade
(decay) data and from two efficiency curves of the sample geometry, which
the detector model computes:

| Curve | Symbol | Role in summing | Engine file (cylinder / Marinelli) |
|---|---|---|---|
| Full-energy peak efficiency | ε<sub>P</sub>(E) | **summing-in**: two photons both fully absorbed add into a sum peak | `efficiency.txt` |
| Total efficiency | ε<sub>T</sub>(E) | **summing-out**: a coincident photon depositing *any* energy removes a count from the peak | `buildup.txt` |

The well model uses the same two quantities, but at every point of the sample
volume (ray-traced local efficiencies).

The decay data (`kordaten.txt`, `Decay_Data`) contain no uncertainties.
Therefore u(C) covers only the efficiency inputs and the numerics (see
section 6).

## 2. Method

### 2.1 Sensitivity coefficients

The relative sensitivity of *C* to each curve is

  *S*<sub>P</sub> = ∂ ln *C* / ∂ ln ε<sub>P</sub>,  *S*<sub>T</sub> = ∂ ln *C* / ∂ ln ε<sub>T</sub>.

*S* = 0.08 means that 10 % more efficiency gives 0.8 % more *C*.

EffSuite computes them numerically with the unchanged engine. A whole
curve is multiplied by e<sup>+h</sup>, then by e<sup>−h</sup> (step *h*,
default 2 %), *C* is recalculated each time, and the central difference is
taken:

  *S* ≈ [ln *C*(ε·e<sup>h</sup>) − ln *C*(ε·e<sup>−h</sup>)] / 2*h*

That is four extra runs: peak ±, total ±. For cylinder and Marinelli, only
`coincidence.exe` is rerun, which adds about one second. The Monte Carlo
efficiency stages are not repeated. For wells, only the cascade evaluation is
repeated on the already ray-traced local efficiencies.

Details of the scaling:

* Both columns of each engine file are scaled: the volume-mean efficiency and
  the second-moment efficiency used for the coincidence terms. Their ratio,
  which describes the spatial non-uniformity of the sample, is kept.
* Physical limits are kept. Total efficiency is capped at 1, and peak
  efficiency is capped at the total efficiency.
* Well model: the precomputed annihilation-pair terms follow the curves. The
  probability that at least one 511 keV photon is detected scales with the
  total efficiency, and the single-photon peak term scales with the peak
  efficiency.
* The central difference is exact for a power-law dependence and has an error
  of order *h*² otherwise. The factors *C* themselves come from the normal
  run; the sensitivity runs never change them.

### 2.2 Combination

First-order propagation (GUM, JCGM 100:2008, eq. 13):

  u<sub>r</sub>(*C*)² = (*S*<sub>P</sub> u<sub>P</sub>)² + (*S*<sub>T</sub> u<sub>T</sub>)² + 2 ρ *S*<sub>P</sub> *S*<sub>T</sub> u<sub>P</sub> u<sub>T</sub> + u<sub>num</sub>²

* u<sub>P</sub> and u<sub>T</sub> are the relative standard uncertainties of the
  model's peak and total efficiencies. These are your inputs (section 3).
* ρ is the correlation between the peak and total efficiency errors.
* u<sub>num</sub> is the numerical uncertainty of the engine itself:

| Geometry | u<sub>num</sub> |
|---|---|
| Cylinder, Marinelli | Monte Carlo statistical uncertainty of the efficiency integration: the largest value *s*<sub>MC</sub> of column 4 of `total.txt` (written by EFFTRAN 5.1 / MEFFTRAN 2.0 `total.f`; the integration stops at 1 %). The same error enters peak and total efficiency together, so u<sub>num</sub> = \|*S*<sub>P</sub> + *S*<sub>T</sub>\| · *s*<sub>MC</sub>. |
| Well | Relative change of *C* in the numerical refinement check (×2 directions and ×2 sample points, the larger change). It is left out when the refinement check is switched off. |

### 2.3 What the sensitivities look like

Typical behaviour, also checked by the tests:

* **Pure summing-out.** Example: Co-60 at 1173 keV, which loses counts when
  the 1332 keV photon is detected. Here *C* = 1/(1 − ε<sub>T</sub>(1332)), so
  *S*<sub>T</sub> = *C* − 1 exactly and *S*<sub>P</sub> = 0. A 10 % error in
  total efficiency gives a 10 % error in the *correction* (*C* − 1), not in *C*.
* **Summing-in.** Example: the Co-60 crossover line at 2159 keV. *S*<sub>P</sub>
  is negative, because more peak efficiency means more sum-in counts and
  therefore a smaller *C*.
* **Pure sum peak.** Example: Co-60 at 2506 keV. *C* ∝ 1/ε<sub>P</sub>, so
  *S*<sub>P</sub> = −1.
* **No coincidence.** *C* = 1 and *S* = 0, so u(C) = 0.

## 3. Inputs

| Setting (project JSON `tcs_uncertainty`) | GUI (Library / Certificate tab) | CLI option | Default |
|---|---|---|---|
| `peak_efficiency_percent`: u<sub>P</sub>, % | u(ε peak) | `--tcs-u-peak` | 5 |
| `total_efficiency_percent`: u<sub>T</sub>, % | u(ε total) | `--tcs-u-total` | 10 |
| `peak_total_correlation`: ρ, −1 … 1 | correlation | `--tcs-correlation` | 0 |
| `enabled` | **Calculate u(C)** check box | `--no-tcs-uncertainty` turns it off | true |
| `step_percent`: *h*, 0.1 … 10 % | — | — | 2 |

Example project section:

```json
"tcs_uncertainty": {
  "peak_efficiency_percent": 4.0,
  "total_efficiency_percent": 8.0,
  "peak_total_correlation": 0.5
}
```

Missing keys get the defaults. Unknown keys and out-of-range values are
refused before any calculation starts.

### 3.1 Choosing the values

**The defaults are round assumptions, not measured values.** Replace them with
values that describe your own detector model:

* **u<sub>P</sub>, peak efficiency.** Use the model's agreement with
  measurement. Compute the peak efficiency of a measured calibration geometry
  with the same detector model and compare it with the measured efficiency.
  The RMS relative deviation over the energy range of interest is a reasonable
  estimate.
* **u<sub>T</sub>, total efficiency.** This is usually the dominant input, and
  it is harder to verify because total efficiency is rarely measured directly.
  If you can, check it with single-line sources (for example Cs-137, Mn-54 or
  Zn-65) as total counts divided by emission rate. Otherwise take a value at
  least as large as u<sub>P</sub>. Total efficiency is more sensitive than
  peak efficiency to material around the crystal (end cap, holder, shielding)
  that the model may describe only approximately.
* **ρ, correlation.** Errors in crystal–sample distance, crystal size or
  window thickness move peak and total efficiency in the same direction
  (ρ > 0). The sign matters:
  * For lines where *S*<sub>P</sub> and *S*<sub>T</sub> have the same sign,
    a positive ρ increases u(C).
  * For summing-in lines, where *S*<sub>P</sub> < 0 < *S*<sub>T</sub>, a
    positive ρ decreases u(C).
  * If you are unsure, run with ρ = 0 and with ρ = 1 and keep the larger
    value for each line.
* **Energy dependence.** Each curve is scaled as a whole, which treats the
  error as fully correlated across energies. This is the dominant mode of a
  detector-model error, and for a summing correction it is usually the
  conservative choice, because the coincident photons' contributions add up
  coherently.

## 4. Results

Every summing line in `results.json` and `summing.csv` has these fields:

| Field | Meaning |
|---|---|
| `tcs_u_rel_percent` | u<sub>r</sub>(*C*), relative standard uncertainty of *C*, % (*k* = 1) |
| `tcs_u_peak_percent` | \|*S*<sub>P</sub>\| u<sub>P</sub>, peak efficiency contribution, % |
| `tcs_u_total_percent` | \|*S*<sub>T</sub>\| u<sub>T</sub>, total efficiency contribution, % |
| `tcs_u_numerical_percent` | u<sub>num</sub>, % (empty when unknown) |
| `tcs_sensitivity_peak` | *S*<sub>P</sub> |
| `tcs_sensitivity_total` | *S*<sub>T</sub> |

* An **empty cell** (`null` in JSON) means that no uncertainty is available:
  the line is uncorrected (`*`), or the calculation was switched off.
* A library line of a nuclide without any coincidence has *C* = 1 and
  u(C) = 0.

The `tcs_uncertainty` section of `results.json` records the settings, the
equation, the numerical component used, the Monte Carlo uncertainty
(cylinder/Marinelli) and the list of effects not included. `report.html`
shows a **u(C) / % (k=1)** column and a short paragraph with the inputs. The
GUI shows **u(C) [%] (k=1)** next to the summing factor.

### Example

Bundled cylinder example, defaults (u<sub>P</sub> = 5 %, u<sub>T</sub> = 10 %,
ρ = 0, *s*<sub>MC</sub> = 1.0 %):

| Nuclide | E / keV | *C* | *S*<sub>P</sub> | *S*<sub>T</sub> | peak % | total % | num. % | **u(C) %** |
|---|---|---|---|---|---|---|---|---|
| Co-60 | 1173 | 1.0759 | 0.000 | +0.076 | 0.00 | 0.76 | 0.08 | 0.76 |
| Co-60 | 1332 | 1.0784 | 0.000 | +0.078 | 0.00 | 0.78 | 0.08 | 0.79 |
| Co-60 | 2159 | 0.92572 | −0.142 | +0.078 | 0.71 | 0.78 | 0.06 | 1.06 |
| Co-60 | 2506 (sum peak) | 8.4·10⁻⁷ | −1.000 | 0.000 | 5.00 | 0.00 | 1.00 | 5.10 |
| Cs-134 | 605 | 1.1122 | 0.000 | +0.111 | 0.00 | 1.11 | 0.11 | 1.11 |
| Cs-134 | 1365 | 0.86379 | −0.209 | +0.090 | 1.05 | 0.90 | 0.12 | 1.38 |

### Using u(C) in an activity uncertainty budget

*A*<sub>corrected</sub> = *C* · *A*, so u(C) adds in quadrature to the other
relative components:

  u<sub>r</sub>(*A*<sub>corrected</sub>)² = u<sub>r</sub>(*A*)² + u<sub>r</sub>(*C*)² + …

u(C) is not independent of the efficiency calibration when the
calibration geometry itself needed a summing correction, or when the same
detector-model error affects the efficiency transfer. In those cases, treat
the correlation in your own budget.

**Exported libraries.** Genie `.NLB` / `.CTF` and GammaVision `.LIB` files
receive the corrected yields or rates (divided by *C*). Their uncertainty
fields are **not** changed. Add u(C) to your activity budget yourself, from
`summing.csv` or `results.json`.

## 5. Settings and reproducibility

* Switching the calculation off (`"enabled": false`, `--no-tcs-uncertainty`,
  or the **Calculate u(C)** check box) removes the four sensitivity runs. The
  factors are identical either way, and this is tested.
* In the GUI, changing u(ε peak), u(ε total) or the correlation after a
  calculation updates the u(C) column at once, without a new run. The stored
  sensitivity coefficients and numerical term do not depend on these inputs,
  so the values equal those of a new calculation. The summing factors and the
  efficiency transfer stay on screen. The saved result folder keeps the values
  of the last run; run again to save the new ones. Unticking **Calculate
  u(C)** only hides the column. A result calculated with it unticked has no
  sensitivities, so ticking it afterwards needs a new run.
* The sensitivity runs use the same engines, inputs and worker settings as the
  main run. Their results are deterministic.
* The settings used are stored in `project.effsuite.json` and in
  `results.json`. Saved projects and the GUI recovery snapshot keep them.

## 6. Not included

u(C) is the uncertainty of the *model* factor that comes from the efficiency
inputs and the numerics. It does **not** include:

1. **Decay data**: emission probabilities, internal conversion coefficients,
   K/L X-ray yields, level lifetimes, and β⁺/EC branching. The decay libraries
   contain no uncertainties. For lines with large corrections, check the
   effect of the dominant cascade intensities separately.
2. **Energy-dependent efficiency errors.** A model that is right at high
   energy and wrong at low energy (for example a dead-layer error) is
   represented only through the whole-curve scaling.
3. **Model limitations of the engines**: angular correlation of the cascade
   photons (not modelled), and, for wells, the limitations listed in
   `well_spatial_diagnostics.limitations`.
4. **Random (chance) summing, dead time, pile-up**, and the uncertainty of the
   measured peak areas.

## 7. Verification

`tests/test_tcs_uncertainty.py` checks:

* settings validation and defaults;
* the combination formula (uncorrelated, ρ = ±1, numerical term);
* the central difference, which reproduces exact power-law sensitivities;
* that scaled curves keep 0 ≤ ε<sub>P</sub> ≤ ε<sub>T</sub> ≤ 1;
* that u(C) follows the factor through library matching;
* with the real engines (cylinder, Marinelli, well):
  * *S*<sub>T</sub> = *C* − 1 for Co-60 at 1173 keV;
  * *S*<sub>P</sub> = −1 for the 2506 keV sum peak;
  * *S*<sub>P</sub> < 0 for the 2159 keV summing-in line;
  * u(C) scales linearly with u<sub>T</sub>;
  * the factors are identical with and without the uncertainty calculation.

Implementation: `src/effsuite/tcs_uncertainty.py`, called from
`suite._cascade_summing`, `suite._well_summing` and
`well_spatial.calculate_spatial(sensitivity_step=…)`.
