# Validation Evidence — EffSuite 0.1.3 (November 2026)

## Executed Application Checks

**All 14 test suites (150+ checks) passed** on Windows 11 x86-64 (CPython 3.12+, NumPy, Matplotlib, PySide6) via the parallel runner (`tools/run_tests.py` / `Run_Tests_Windows.bat`) and on Linux x86-64.

The tests include:

- Actual bundled native cylinder (`EFFTRAN 4.9`), Marinelli (`MEFFTRAN 1.8`), and well (`WEFFTRAN`) preparation and calculations.
- 8-line source model bulk density scaling (`rho / rho0`) verified across all three geometries (`Water` at `rho = 2.0 g/cm³` matches `HeavyWater` at `rho0 = 2.0 g/cm³` to 6 decimal places), point-source `vacuum` (`rho = 0.00`) positivity guard, and 7-line backward compatibility.
- Real laboratory benchmark validations:
  - `test_validation_case_207724.py`: Cylindrical EFFTRAN validation against reference laboratory dataset.
  - `test_validation_det952_mar.py`: Marinelli MEFFTRAN validation against DET952 laboratory dataset.
  - `test_validation_det007_well.py`: Well WEFFTRAN validation against EGSnrc Monte Carlo benchmark (17 nuclides, 41 lines) and extended 12-field detector parameters (mantle/bottom dead layers, Cu holder Compton backscatter, sample offset).
- CLI/shared-service equality for all three modes, serial/parallel bit-for-bit agreement (`--verify-serial`), identity transfer for each geometry, and positive small sum-peak factors.
- Real offscreen Qt tab/forms, GUI `Source density [g/cm³]` auto-fill from `Composition/<material>.txt` on material selection, custom density preservation, background calculation lifecycle, cancellation event routing, full input-precision round trip, and responsive layout on 1080p and 720p.
- Original material text/JSON/XLSX import, actual XCOM water/reference tables,
  relative-weight scale invariance and independent bulk-density input. Generated
  materials feed both transfer and Co-60 summing in all three geometries.
- Actual GUI material generation and automatic material-list refresh.
- Input units, malformed calibration, original model field counts, native
  timeouts/errors, parent/continuation grouping, private worker directories,
  existing-output preservation and cancelled-job cleanup.
- Spatial cascade analytic/exhaustive event checks, well geometry/ray cases,
  summing-in, inconsistent decay data, convergence/saturation export blocking.
- Genie adapter safety/round-trip contract checks with a **simulated COM
  transport**, including source preservation and tiny-value underflow detection.
- Strict comparison evidence hashes, matching input sets, missing/empty lines,
  predeclared tolerance failure, and covariance requirements.

GUI screenshots in `docs/screenshots` show actual Qt rendering of the original
Detector/Source/Efficiency tabs and well detector form. They use supplied
example models, not laboratory-qualified detector parameters.

## Native builds

35 Windows x86-64 numerical programs were cross-compiled with GNU Fortran
12/MinGW; Linux programs were built with GNU Fortran 13. Each engine/platform
folder includes source/compiled-source/binary hashes, exact commands and any
output-format change. All 35 new Windows programs were inspected as PE files;
their DLL imports are limited to KERNEL32.dll and msvcrt.dll. See
`build_evidence/windows_imports.json`. This inspection is not Windows execution.

Cylinder/Marinelli coincidence output was changed from `f15.3` to `e23.15`
in a temporary compilation copy. The arithmetic source is unchanged. The
original source and supplied reference Windows binaries are retained. No
claim of cross-compiler bitwise identity is made.

## Material workbook and XCOM

The editable XLSX was recalculated and rendered. Water and 50/50 mixture input
changes were checked; the formula scan reported no errors. The importer reads
authoritative input values and recomputes normalization rather than trusting
cached formula outputs. Its GUI/CLI execution tests use the actual bundled XCOM.
No native Microsoft Excel session was available for a target-application check.

XCOM 3.1 source/data came from the supplied original EFFTRAN package. Its
Windows/Linux build manifests record temporary removal of DOS EOF control
characters from compiler include files; numerical statements are unchanged.
The added Windows XCOM binary was import-inspected and remains unexecuted here.

## Spatial well evidence retained from v0.2

The prior source-based regression evidence is retained, labelled by its
original source hashes and compiler profile. Current application tests extend
that evidence; they do not retrospectively change those historical hashes.

`examples/wefftran_spatial_validation.json` and WEFFTRAN_FIX.md record:

- Co-60, Cs-134, Eu-152 and Na-22 at eight heights from 3.25 to 100 mm,
  including 31.499/31.5/31.501 mm around the crystal-rim boundary.
- All reported factors positive/finite and all refinement checks passing;
  maximum coarse/fine change below 0.32%, rim-boundary change below 0.0201%.
- Identical serial/four-process computed results, without probability saturation.
- Constant-response comparisons for Co-60, Cs-134 and Ba-133 against original
  native routines; maximum relative difference below 0.0073% against the
  diagnostic 0.01% criterion for the rounded native outputs.
- Structural/synthetic-response audit: 224 parent groups accepted and three
  supplied records rejected for inconsistent transition/conversion data.
  This is not a whole-library physical qualification.

Earlier parallel reference and geometry findings remain under `examples`:
225 cylinder/Marinelli parent groups per supplied dataset, 227 well parent
groups/33 continuation records, 2,000 interior ray checks and 4,000 independent
geometry comparisons. Their historical scheduling/source results are not
claims about every case under the current Windows build.

## Pending release checks

**This release is not qualified for routine laboratory use.**

- Native Windows execution on the user's Windows 11 and selected Python.
- Real registered Genie CAM CAL/NLB/CTF import/export, reopened record checks,
  vendor file metadata behavior, and architecture/COM host selection.
- Actual PyInstaller GUI/CLI executable build and Inno Setup installation.
- Controlled comparison with the user's original EFFTRAN/MEFFTRAN cases,
  including identical models, materials, calibration and decay data.
- Independent physical measurements/reference cases for the well spatial
  change and intended geometry/energy/material scope.
- Laboratory acceptance criteria, complete uncertainty treatment, change
  control and documented routine-release approval.

Retained well assumptions include isotropic independent emission directions,
spatially uniform per-energy peak-to-total/build-up approximations and legacy
timing/integer-keV binning. Unsupported annihilation pair sum-in channels are
blocked. Transfer uncertainty output retains the original hard-coded 0.5%
standard/sample contributions; it is not a complete uncertainty budget.
