# Validation Evidence — EffSuite 0.3.3

> **This release is not qualified for routine laboratory use.** The evidence
> below supports evaluation. It does not replace a laboratory's own
> qualification against its reference standards.

## Automated tests

`tools/run_tests.py` (or `Run_Tests_Windows.bat`) runs 17 test modules with
166 tests in parallel. All pass on Windows 11 x86-64 (CPython 3.11+, NumPy,
Matplotlib, PySide6) and on Linux x86-64. They use the real bundled native
programs and the real XCOM, and cover:

- **Engines.** Preparation and calculation with the bundled cylinder
  (EFFTRAN 5.0), Marinelli (MEFFTRAN 1.9) and well (WEFFTRAN) engines.
  Further checks:
  - the CLI gives the same results as the shared service in all three
    geometries;
  - serial and parallel runs are bit-for-bit identical (`--verify-serial`);
  - the identity transfer (standard = sample) gives exactly 1;
  - small sum-peak factors stay positive.
- **Bulk density.** The 8-line source density scaling ρ/ρ₀ in all three
  geometries: `Water` at ρ = 2.0 g/cm³ equals `heavy` (H₂O, ρ₀ = 2.0 g/cm³)
  to 6 decimal places. The point-source `vacuum` (ρ = 0) guard works, and
  7-line models still load.
- **Laboratory benchmark cases.**
  - `test_validation_case_207724.py`: cylinder, against a reference
    laboratory dataset (DET002; compared with EFFTRAN 4.8, transfer factors
    within ±0.0001, summing factors within ±0.0004 over 247 lines).
  - `test_validation_det952_mar.py`: Marinelli, against the DET952 laboratory
    dataset.
  - `test_validation_det007_well.py`: well, against an EGSnrc Monte Carlo
    benchmark (17 nuclides, 41 lines), with the extended 12-field detector
    inputs.
- **Summing-factor uncertainty u(C)**: see below.
- **GUI** (offscreen Qt):
  - tabs and forms, and density auto-fill on material selection;
  - background calculation, cancellation, and full input-precision round
    trip;
  - TCS uncertainty inputs, and layout at 1080p and 720p.
- **Materials.**
  - Import of original text, JSON and XLSX materials; XCOM tables for water
    and the reference materials.
  - Weight-scale invariance, and density kept as an independent input.
  - Generated materials used in transfer and Co-60 summing in all three
    geometries.
- **Input and execution safety.**
  - Input units, malformed calibrations, and the original model field
    counts.
  - Native timeouts and errors, parent/continuation grouping, and private
    worker folders.
  - Existing outputs preserved, and cancelled jobs cleaned up.
- **Well model.**
  - Analytic and exhaustive cascade event checks.
  - Geometry and ray cases, summing-in, and inconsistent decay data.
  - Export blocked on failed convergence or probability saturation.
- **Genie adapter.** Safety and round-trip contract with a simulated COM
  transport, including source preservation and tiny-value underflow
  detection.
- **Laboratory comparison tool.** Evidence hashes, matching input sets,
  missing or empty lines, pre-declared tolerance failures, and covariance
  requirements.

Real Genie 2000 CAM round trips (`.NLB`, `.CTF`, `.CAL`) were also executed
on Windows 11 with the installed CamDatasource component.

## Verified in v0.3.0

- **Compiled well ray tracing (`raytrace`).** Compared with the Python
  implementation on the DET007 detector and sample, for the initial and
  refined quadratures, with and without the mount cup:
  - peak and total efficiencies agree to 7·10⁻¹⁴ relative, and 511 keV pair
    probabilities to 1.1·10⁻¹⁴;
  - the saturation check gives the same result;
  - in the DET007 complete analysis, the summing factors (277 lines) agree to
    1.8·10⁻¹⁵ and the transferred efficiencies (41 lines) to 1.3·10⁻¹⁵.

  The permanent test `test_fortran_raytrace_matches_python` requires
  agreement to 10⁻¹².
- **Separate convergence checks.** On DET007, factors differ by at most
  0.037 % (mean 0.007 %) from the v0.2.0 combined refinement. Agreement with
  the Monte Carlo reference is unchanged (mean deviation 10.37 %).
- **Readability rewrite.** Each rewritten module was compared with the
  previous version: results are identical for the three bundled examples, the
  bundled models, material creation, and real Genie/GammaVision files. Purely
  mechanical reformatting was checked by an identical program structure
  (AST).

## Summing-factor uncertainty u(C)

u(C) ([TCS_UNCERTAINTY.md](TCS_UNCERTAINTY.md)) is an EffSuite addition with
no original reference. `tests/test_tcs_uncertainty.py` checks it against
analytic limits, using the real engines in all three geometries:

- *S*<sub>T</sub> = *C* − 1 for Co-60 at 1173 keV (within 0.002 for cylinder
  and Marinelli, and 2 % for the well);
- *S*<sub>P</sub> = −1 for the 2506 keV sum peak;
- *S*<sub>P</sub> < 0 for the 2159 keV summing-in line.

It also checks the propagation formula, the physical limits of the scaled
curves, and that the factors are identical with and without the uncertainty
calculation. u(C) depends on assumed efficiency uncertainties (defaults 5 %
peak and 10 % total, not laboratory-qualified), and excludes decay-data
uncertainties.

## Native programs

- **Windows.** 35 x86-64 programs: 10 cylinder, 10 Marinelli, and 15 well
  stages including `raytrace`. They are built with GNU Fortran 15.2.0
  (w64devkit), using `-finit-local-zero -fno-strict-aliasing`.
- **Linux.** Built with GNU Fortran 13.3.
- **Records.** Each `assets/engines/*/bin/*/build_manifest.json` records the
  source and binary hashes, the compiler version and the flags.

The coincidence output format of the cylinder and Marinelli engines is
changed from `f15.3` to `e23.15` in a temporary compilation copy. The
arithmetic source is unchanged, and the original sources are kept. No claim
of bitwise identity across compilers is made.

## Materials and XCOM

The editable XLSX was recalculated and rendered. Water and a 50/50 mixture
were checked, and the formula scan reported no errors. The importer reads the
input values and recomputes the normalisation rather than trusting cached
formula results. No native Microsoft Excel session was available for a
target-application check.

XCOM 3.1 source and data come from the original EFFTRAN package, and the
automated tests run it on Windows and Linux. The build manifests record a
temporary removal of DOS end-of-file characters from compiler include files;
the numerical statements are unchanged.

## Well spatial model: earlier evidence

The v0.2 source-based regression evidence is kept, labelled with its original
source hashes and compiler profile. The current tests extend it; they do not
retroactively change those hashes. It covers:

- four nuclides at eight heights from 3.25 to 100 mm, including the
  crystal-rim boundary;
- all factors positive, and refinement changes below 0.32 % (0.0201 % across
  the rim);
- serial and parallel results identical;
- constant-response comparisons with the original native routines, within
  0.0073 %.

A structural decay-data audit passes 224 of 227 parent groups and rejects
three inconsistent records. This is not a whole-library physical
qualification. Details: [WELL_SPATIAL_MODEL.md](WELL_SPATIAL_MODEL.md).

Earlier parallel-reference and geometry findings remain under `examples/`:

- 225 cylinder/Marinelli parent groups per supplied dataset;
- 227 well parent groups and 33 continuation records;
- 2,000 interior ray checks and 4,000 independent geometry comparisons.

These are historical results, not claims about every case under the current
build.

## GammaVision

The `.LIB` and `.EFT` backend was checked only against the sample
`EFFTRAN.Lib` and `EFFTRAN.EFT` shipped with EFFTRAN 4.9: 55 library lines
read back, and write/re-read round trips. It has **not** been validated with
real GammaVision files or the GammaVision software.

## Limitations and pending checks

Model assumptions that remain:

- **Well model:** isotropic, independent emission directions; legacy timing
  and integer-keV binning; unsupported annihilation-pair sum-in channels are
  blocked.
- **Transfer uncertainty:** cylinder and Marinelli combine the reference
  uncertainty with the Monte Carlo statistics; wells keep the original fixed
  0.5 % + 0.5 % terms.
- **Summing-factor uncertainty u(C):** depends on assumed efficiency
  uncertainties and excludes decay data.
- None of these is a complete uncertainty budget.

Still needed before routine use:

- Controlled comparison with the laboratory's own original EFFTRAN/MEFFTRAN
  cases (identical models, materials, calibration and decay data), beyond the
  three benchmark cases above.
- Independent physical measurements or reference calculations for the well
  model over the intended geometry, energy and material range.
- Systematic testing of the installed program (PyInstaller build, Inno Setup
  installation) on the laboratory's PCs, and of GammaVision with the real
  software.
- Laboratory acceptance criteria, a complete uncertainty treatment, change
  control and a documented release approval.
