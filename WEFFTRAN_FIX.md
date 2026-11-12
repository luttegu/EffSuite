# WEFFTRAN tall-sample correction: spatial backend v0.2.0

The reproduced negative/near-singular summing failure is repaired in the new
`effsuite-well-spatial` backend. It passes the numerical regression checks
below. Laboratory qualification and Windows execution still need verification.

The v0.3 suite connects this backend to the original-style GUI and main CLI,
with automatic native response preparation. A simple current command is:

```bat
CLI.bat well --detector DET07 --sample Plastic_vial_5mL --nuclides Co60 Cs134 Eu152
```

The lower-level v0.2 commands below remain available for detailed diagnostics.
The original workbook itself is not modified. The full independent scientific
engine rewrite and laboratory qualification remain incomplete.

## Calculation change

The old correction was `emissions / (peak - emissions2 + emissions)`. It
combines mean-efficiency and second-moment estimates by subtraction. When
local efficiencies differ sufficiently, this denominator can approach zero
or become negative. An independent three-photon analytic test reproduces
this failure with valid local detection probabilities.

The replacement evaluates the cascade at spatial quadrature nodes, integrates
predicted counts, then forms the ratio:

```text
C(E) = sum(weight * direct_peak_counts(E, position))
       / sum(weight * coincident_peak_counts(E, position))
```

Positive integration weights preserve nonnegative predicted peak counts.
Correction factors themselves are not averaged. The entire sample volume is
included, including material above the crystal. Ray/material intersections
are limited to the actual finite crystal and well.

The 511-keV pseudo-transition representing an annihilation pair now uses
zero/single-detection pair probabilities, avoiding the legacy high-efficiency
expression `1 - 2*T`. This treatment assumes independent photon directions.
Large physical factors remain allowed. Invalid, missing, zero-peak or
unconverged results are not replaced with one or clipped to a maximum.

## Reproduced DET07 / Eu-152 case

Crystal height: 69 mm. Sample height: 50 mm. Sample bottom/top coordinates:
37.5 / 87.5 mm. The upper 18.5 mm extends above the crystal.

| Legacy bin (keV) | Old factor | Spatial factor |
|---|---:|---:|
| 316 | -89.258 | 12.02176 |
| 665 | -262.43 | 11.42813 |
| 906 | 6256.5 | 11.10238 |

These are computational regression results using the supplied detector,
materials and decay records, not certified detector corrections. Energies
are the legacy program's integer-keV bins.

## Run with your selected Python

Extract the project, open a terminal in its directory, and use your selected
interpreter. No code selects a different Python version.

```bat
python -m pip install -e ".[spatial]"
```

Fresh preparation for the selected detector/sample, followed by parallel
nuclide calculations:

```bat
effsuite-well-spatial --original "C:\WEFFTRAN" --detector "C:\WEFFTRAN\Detector\DET07.txt" --sample "C:\WEFFTRAN\Sample\Plastic_vial_5mL.txt" --nuclide CO-60 --nuclide CS-134 --nuclide EU-152 --workers 4 --verify-serial --output well_results.json
```

Choose a sample file containing your actual height/composition. This mode
requires the compiled original `mine`, `energy`, `total`, `scatter`, `buildup`,
`eta`, `ptt` and `efficiency` executables in the installation, or an explicit
`--engine-dir`. They supply the existing peak-to-total and build-up models.
They run in a private job directory; the original installation is read-only.

Alternatively, after a completed original `coin1.bat` preparation:

```bat
effsuite-well-spatial --original "C:\WEFFTRAN" --inputs "C:\WEFFTRAN" --nuclide EU-152 --workers 1 --output eu152_results.json
```

That directory must contain `detector.txt`, `source.txt`, `total.txt`,
`efficiency.txt`, `buildup.txt`, `ptt.txt` and `param.txt` from the **same**
completed preparation. Do not retain response files from a different
sample/detector. Fresh-preparation mode avoids this mismatch.

Use `python -m effsuite.well_spatial` instead of the console command to
invoke a particular interpreter explicitly.

## Convergence and export

Default execution compares two quadratures, doubling the radial, axial,
polar and azimuthal orders. The initial orders are 4/8/32/64 and the returned
refined orders are 8/16/64/128. The axial integration splits at the crystal
rim. Every reported factor must meet the numerical refinement criterion.

The default `--rtol 0.01` is a numerical test, **not a 1% uncertainty claim**.
Use `--radial`, `--axial`, `--polar` and `--azimuth` to start more finely.
`--no-refinement` is diagnostic-only and disables legacy text export.

For one nuclide, a converged two-column `correct.txt`-style result is available:

```bat
effsuite-well-spatial --original "C:\WEFFTRAN" --inputs "C:\WEFFTRAN" --nuclide EU-152 --format correct --output eu152_corrected.txt
```

Legacy text export requires convergence, valid factors and no activation of
the legacy probability-saturation rule. JSON retains failure diagnostics.
Existing output files are not overwritten. Exit codes: 0 passing refinement,
1 incomplete/unconverged diagnostic result, 2 input/execution/export error,
130 interruption.

The lower-level text format does not itself edit `.NLB` files or call CAM.
The v0.3 GUI/CLI provides a separate vendor-CAM adapter; real Windows/CAM
verification remains pending. The old Excel `coin2.bat` is not rewired.
The original workbook continues to execute its original stages until its
calculation call is changed. The export-planning guards remain available;
Genie nuclide abundance changes use abundance/C.

## Parallel execution

The detector response is calculated once per quadrature for all selected
nuclides. Each process worker receives immutable response arrays once,
avoiding a large array copy for every nuclide. A parent and its `b` record
stay together. `--workers 1` is serial; zero selects up to four workers.
`--verify-serial` compares complete computed results with serial execution.

## Validation evidence

`examples/wefftran_spatial_validation.json` and `tools/validate_spatial_fix.py`:

- Co-60, Cs-134, Eu-152 and Na-22 at sample heights 3.25, 31.499, 31.5,
  31.501, 32.5, 50, 69.1 and 100 mm.
- Positive finite factors at all reported lines in those cases.
- Passing refinement, with the largest coarse/fine change below 0.32%.
- No activation of probability saturation in those cases.
- Matching serial and four-process computed results.
- Approximately 0.0201% maximum factor change from 31.499 to 31.501 mm,
  across the crystal-rim boundary.
- Constant point-response comparisons against original native routines for
  Co-60, Cs-134 and Ba-133. Maximum difference was below 0.0073%; the test
  criterion is 0.01% for the rounded native stage outputs.

The v0.2 automated suite passed 99 tests, including analytic and exhaustive event
checks for cascades, summing-in, time cuts, spatial averaging, parent records,
annihilation pairs and export failures. Fresh native preparation, CLI output,
legacy text export and existing-output preservation were also exercised.

To reproduce the native-source sweep:

```bat
python tools\validate_spatial_fix.py --original C:\WEFFTRAN --compiler gfortran --report new_validation.json
```

## Scope and remaining qualification

This repairs the reproduced nonphysical subtraction failure. It retains the
legacy virtual-total, peak-to-total and sample build-up approximations.
Peak-to-total and build-up factors remain spatially uniform at each energy.
The model assumes isotropic, independent emission directions and retains
legacy timing and transition-energy bin conventions.

It does not add annihilation-pair 1022-keV sum peaks, mixed pair sum-in
channels, angular correlations, or a complete gamma/X-ray transport model.
Legacy 1022-keV text export is blocked when that unsupported pair channel
is involved. Other affected pair sum-in channels require case-specific
qualification. A numerically converged result is not proof of physical-model
accuracy.

The default PL-column beta-plus interpretation is explicitly configured for
the supplied modified Na-22 record. Other records use L-capture semantics.
For different library conventions use the API's explicit `beta_plus_pl`
configuration rather than inferring decay mode from a probability's size.

The structural/synthetic-response audit passes 225 of 227 parent groups and
rejects two inconsistent supplied records:

| Record | Inconsistency requiring verified nuclear data |
|---|---|
| Th-227 | Total conversion coefficient 0, L coefficient 13.6 in a transition |
| W-187 | Total conversion coefficient 0.0153, K coefficient 118 in a transition |

Those nuclear data were not guessed or edited. See
`examples/decay_library_audit.json`. That audit is not a qualification of all
nuclides in real detector geometries.

Checks ran on Linux with CPython 3.12.14, NumPy and GNU Fortran 13 builds of
the supplied sources. Native Windows execution, Genie CAM round trips and
comparison with detector measurements or independent transport calculations
remain to be qualified. This correction intentionally changes the old faulty
results; it does not claim cross-platform bitwise equivalence.

Original method background: [Vidmar et al., 2011](https://doi.org/10.1016/j.apradiso.2011.02.042)
and [Vidmar and Kanisch, 2010](https://doi.org/10.1016/j.apradiso.2010.02.016).
These references are background, not a validation of this implementation.
