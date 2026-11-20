# Well Detectors: Spatial Summing Model

*EffSuite v0.3.1. Reference for the WEFFTRAN (well detector) summing
calculation. The GUI and the main CLI use it automatically; this page also
covers the lower-level `effsuite-well-spatial` command.*

> **Qualification:** the well model passes the numerical and regression
> checks below, but it has not been qualified against laboratory measurements.
> Treat well results as experimental and verify them independently.

Why the original calculation was replaced, and how the new model compares with
it and with a Monte Carlo benchmark, is in
[CHANGES_FROM_ORIGINALS.md, section 2](CHANGES_FROM_ORIGINALS.md#2-well-detectors-wefftran).

## Calculation

The original factor `emissions / (peak - emissions2 + emissions)` combines
mean-efficiency and second-moment estimates by subtraction. When local
efficiencies vary strongly over the sample, the denominator can approach zero
or become negative. An independent three-photon analytic test reproduces this
with valid local detection probabilities.

EffSuite evaluates the cascade at spatial quadrature points, integrates the
predicted counts, and then forms the ratio:

```text
C(E) = sum(weight * direct_peak_counts(E, position))
       / sum(weight * coincident_peak_counts(E, position))
```

Positive weights keep the predicted peak counts non-negative. The factors
themselves are not averaged. The whole sample is included, including material
above the crystal. Ray/material intersections are limited to the actual
finite crystal and well.

The 511 keV pseudo-transition, which represents an annihilation pair, uses
exact zero- and single-detection probabilities for antiparallel photons,
instead of the legacy high-efficiency expression `1 - 2*T`. Large physical
factors are allowed. Invalid, missing, zero-peak or unconverged results are
never replaced by one or clipped.

The local peak and total efficiencies come from the compiled `raytrace`
program (`assets/engines/well/source/raytrace.f90`, built by
`tools/build_raytrace.py`; double precision, no fast-math). It agrees with
the Python implementation to about 10⁻¹⁴. The Python code is used
automatically when the program is not built for the platform; set
`EFFSUITE_PYTHON_RAYTRACE=1` to force it.

### Reproduced DET07 / Eu-152 case

Crystal height 69 mm. Sample height 50 mm, with bottom and top at 37.5 and
87.5 mm, so the upper 18.5 mm is above the crystal.

| Legacy bin (keV) | Old factor | Spatial factor |
|---|---:|---:|
| 316 | −89.258 | 12.02176 |
| 665 | −262.43 | 11.42813 |
| 906 | 6256.5 | 11.10238 |

These are computational regression results using the supplied detector,
materials and decay records, not certified corrections. Energies are the
legacy integer-keV bins.

## Convergence and export

Each calculation compares the initial quadrature with two refined ones:

| Quadrature | Orders (radial/axial/polar/azimuthal) | Role |
|---|---|---|
| Initial | 4 / 8 / 32 / 64 | reference for both checks |
| Twice the directions | 4 / 8 / 64 / 128 | its factors are the reported ones |
| Twice the sample points | 8 / 16 / 32 / 64 | second check |

Both checks must change every reported factor by less than `rtol`, otherwise
export is blocked. The axial integration is split at the crystal rim. (Up to
v0.2.0, a single 8/16/64/128 refinement was used.)

The default `rtol = 0.01` is a numerical test, **not a 1 % uncertainty
claim**. The change of *C* under refinement is, however, used as the
numerical component of the summing-factor uncertainty u(C) (see
[TCS_UNCERTAINTY.md](TCS_UNCERTAINTY.md)).

## Parallel execution

The detector response is calculated once per quadrature for all selected
nuclides. The nuclides are then evaluated in parallel threads that share the
response arrays. A parent and its `b` record stay together. `--workers 1` is
serial, and `0` selects the number of CPUs minus 2. `--verify-serial` checks
that the parallel results equal a serial run.

A nuclide whose decay data cannot be used is reported in `failed_nuclides`
and listed as missing. Its library lines are exported unchanged, and the
other nuclides are calculated normally.

## Command line (`effsuite-well-spatial`)

The normal entry points are the GUI and `CLI.bat well …` (see the
[User Guide](USER_GUIDE.md)):

```bat
CLI.bat well --detector DET07 --sample Plastic_vial_5mL --nuclides Co60 Cs134 Eu152
```

The lower-level command is meant for detailed diagnostics. Install the
package with `python -m pip install -e ".[spatial]"`, or call
`python -m effsuite.well_spatial` to choose the interpreter explicitly.

Fresh preparation for a detector and sample, then parallel nuclide
calculations:

```bat
effsuite-well-spatial --original "C:\WEFFTRAN" --detector "C:\WEFFTRAN\Detector\DET07.txt" --sample "C:\WEFFTRAN\Sample\Plastic_vial_5mL.txt" --nuclide CO-60 --nuclide CS-134 --nuclide EU-152 --workers 4 --verify-serial --output well_results.json
```

This mode needs the compiled `mine`, `energy`, `total`, `scatter`, `buildup`,
`eta`, `ptt` and `efficiency` stages in the installation, or an explicit
`--engine-dir`. They run in a private job folder, and the original
installation is not written.

Using the files of a completed original `coin1.bat` preparation:

```bat
effsuite-well-spatial --original "C:\WEFFTRAN" --inputs "C:\WEFFTRAN" --nuclide EU-152 --workers 1 --output eu152_results.json
```

That folder must contain `detector.txt`, `source.txt`, `total.txt`,
`efficiency.txt`, `buildup.txt`, `ptt.txt` and `param.txt` from the **same**
preparation. Response files left from another sample or detector give wrong
results; fresh preparation avoids this.

Options: `--radial`, `--axial`, `--polar` and `--azimuth` set the initial
orders, and `--rtol` the convergence criterion. `--no-refinement` is for
diagnostics only and disables the legacy text export.

For one nuclide, a converged two-column `correct.txt`-style result is
available:

```bat
effsuite-well-spatial --original "C:\WEFFTRAN" --inputs "C:\WEFFTRAN" --nuclide EU-152 --format correct --output eu152_corrected.txt
```

The text export requires convergence, valid factors and no probability
saturation; the JSON output keeps the failure diagnostics. Existing output
files are never overwritten.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | refinement passed |
| 1 | incomplete or unconverged diagnostic result |
| 2 | input, execution or export error |
| 130 | interrupted |

This command does not edit `.NLB` files. Genie and GammaVision export goes
through the main GUI/CLI. The legacy subtraction calculation remains
available for comparison as `effsuite-well-coincidence` (`well_parallel.py`).

## Validation evidence

Current tests run on Windows 11 and Linux
(`tests/test_validation_det007_well.py`, `tests/test_well_spatial.py`,
`tests/test_spatial_summing.py`). See also [VALIDATION.md](VALIDATION.md).

The v0.2 source-based evidence was produced on Linux (CPython 3.12, NumPy,
GNU Fortran 13 builds of the supplied sources). It is in
`examples/wefftran_spatial_validation.json`, reproducible with
`tools/validate_spatial_fix.py`:

- Co-60, Cs-134, Eu-152 and Na-22 at sample heights of 3.25, 31.499, 31.5,
  31.501, 32.5, 50, 69.1 and 100 mm.
- All reported factors positive and finite, and all refinement checks
  passing; the largest coarse/fine change is below 0.32 %.
- No probability saturation.
- Serial and four-process results identical.
- The factor changes by about 0.0201 % from 31.499 to 31.501 mm, across the
  crystal-rim boundary.
- Constant point-response comparisons with the original native routines
  (Co-60, Cs-134, Ba-133): maximum difference below 0.0073 %, against a 0.01 %
  criterion for the rounded native outputs.
- Analytic and exhaustive event checks for cascades, summing-in, time cuts,
  spatial averaging, parent records, annihilation pairs and export failures.

```bat
python tools\validate_spatial_fix.py --original C:\WEFFTRAN --compiler gfortran --report new_validation.json
```

v0.3.0 changes, checked on DET007:

| Change | Effect |
|---|---|
| Compiled ray tracing | summing factors agree with the Python version to 1.8·10⁻¹⁵ |
| Separate direction and point refinement | reported factors change by at most 0.037 % |
| Speed and memory | 12.5 s and 0.9 GB, instead of 108 s and 12 GB |

## Scope and remaining qualification

The model assumes isotropic, independent emission directions, with no
angular correlation. It keeps the legacy timing and transition-energy bin
conventions. It is a deterministic approximation, not a Monte Carlo
transport.

It does not add the 1022 keV annihilation-pair sum peak or mixed pair sum-in
channels. A 1022 keV line is blocked from export; other pair sum-in channels
need case-specific qualification. A numerically converged result is not proof
that the physical model is accurate.

The PL column is read as a β⁺ branch only for nuclides configured
explicitly; the default is Na-22, matching the supplied record. Other records
use L-capture semantics. For other library conventions, use the API's
`beta_plus_pl` setting rather than inferring the decay mode from the size of a
probability.

The structural decay-data audit (`examples/decay_library_audit.json`) passes
224 of 227 parent groups. The three rejected records need verified nuclear
data:

| Record | Problem |
|---|---|
| Pa-234 | invalid or duplicate transition indices |
| Th-227 | a transition with total conversion coefficient 0 but L coefficient 13.6 |
| W-187 | a transition with total conversion coefficient 0.0153 but K coefficient 118 |

These data were not guessed or edited. The audit is not a qualification of
every nuclide in real detector geometries.

Background on the original method:
[Vidmar et al., 2011](https://doi.org/10.1016/j.apradiso.2011.02.042) and
[Vidmar and Kanisch, 2010](https://doi.org/10.1016/j.apradiso.2010.02.016).
These references describe the original approach; they do not validate this
implementation.
