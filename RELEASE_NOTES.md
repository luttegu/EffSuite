# Release Notes

## EffSuite 0.3.1 (November 2026)

The EFFTRAN and MEFFTRAN Fortran engines and all summing factors are unchanged from 0.3.0.

- **New: uncertainty of the coincidence summing factors, u(C)**. The original EFFTRAN, MEFFTRAN and WEFFTRAN give the factors without uncertainty. EffSuite now reports a relative standard uncertainty (k = 1) for every factor, in all three geometries. The factors themselves are unchanged.
  - Method: sensitivity coefficients ∂ln C/∂ln ε for the peak and total efficiency curves, from four extra runs of the unchanged engine with each curve scaled by ±2 %. They are combined with the relative uncertainties of the computed peak efficiency (default 5 %) and total efficiency (default 10 %), with an optional correlation, plus the engine's numerical uncertainty (Monte Carlo statistics for cylinder/Marinelli, quadrature refinement for wells). This adds about one second per calculation.
  - Shown in the GUI tables and in `summing.csv` (new `tcs_*` columns), `results.json` and `report.html`. Set the inputs in the new **TCS uncertainty inputs** row on the Library / Certificate tab, with the CLI options `--tcs-u-peak`, `--tcs-u-total`, `--tcs-correlation` and `--no-tcs-uncertainty`, or with a `"tcs_uncertainty"` section in the project JSON.
  - Decay-data uncertainties are not included, and exported `.NLB` / `.CTF` / `.LIB` files do not carry u(C). See [docs/TCS_UNCERTAINTY.md](docs/TCS_UNCERTAINTY.md).
  - The GUI summing tables gained a column: "Not Computed" (`*`) is now the fifth column.
  - Changing the u(C) inputs or the **Calculate u(C)** check box keeps the summing factors and transferred efficiencies on screen, and recalculates u(C) at once from the stored sensitivities (no new engine run).
- **Documentation reorganised** into `docs/` with an index ([docs/README.md](docs/README.md)). README, release notes and third-party notices stay at the top level, and the installer puts the documents in `{app}\docs`.
  - `EFFTRAN_MEFFTRAN_WEFFTRAN_CHANGES.md` and `SCIENTIFIC_AUDIT_REPORT.md` are merged into one topic-organised [docs/CHANGES_FROM_ORIGINALS.md](docs/CHANGES_FROM_ORIGINALS.md). `WEFFTRAN_FIX.md` is now [docs/WELL_SPATIAL_MODEL.md](docs/WELL_SPATIAL_MODEL.md).
  - Corrected outdated statements:
    - CLI exit-code meanings, the automatic worker count, and the `efficiency.csv` columns;
    - the coincidence output format (`f15.3` → `e23.15`), GUI button names, and the default data and result folders;
    - the compiler (GCC 15.2), and the test count (16 modules, 155 tests);
    - the well transfer uncertainty (only wells keep the 0.5 % terms), and the WEFFTRAN source comparison (`mine.f`, `scatter.f` and `efficiency.f` also differ);
    - the decay-data audit (224 of 227 records; Pa-234, Th-227 and W-187 rejected), and the legacy well calculation (`effsuite-well-coincidence`; there is no `--engine original` option).
  - The bundled EFFTRAN/MEFFTRAN README and notice copies are updated to the 5.0 / 1.9 distributions.
  - `Build_Windows.bat` copies `docs/` into `dist\EffSuite\docs`, and the PyInstaller spec and installer ship the same documents.
- **Licence notice restored in the well `peak.f`**: the EffSuite copy of WEFFTRAN `peak.f` had lost Tim Vidmar's permission notice from its header comment; it is restored as in the original. Only comments changed. The bundled `peak.exe` (used only by the legacy `effsuite-well-coincidence` calculation) is unchanged, and its build manifest records the new source hash with a note.

## EffSuite 0.3.0 (November 2026)

The EFFTRAN and MEFFTRAN Fortran engines are unchanged. Cylindrical and Marinelli results are identical to 0.2.0.

- **WEFFTRAN (well detectors) is about 9 times faster and uses 14 times less memory**:
  - **Compiled ray tracing**: the inner ray-tracing loop of the spatial well model now runs in a new Fortran program, `raytrace` (`assets/engines/well/source/raytrace.f90`, built with `tools/build_raytrace.py`). It reproduces the Python formulas operation by operation: factors agree with the Python version to about 1e-14. The Python code remains as an automatic fallback when the program is not built for the platform (set `EFFSUITE_PYTHON_RAYTRACE=1` to force it).
  - **Lighter convergence check**: the numerical refinement now refines the directions and the sample points in two separate checks, both of which must pass, instead of refining both at once. Factors change by at most 0.04 % (DET007 validation case), far inside the 1 % convergence tolerance.
  - **Memory**: directions are processed in blocks. Peak memory fell from about 12 GB to under 1 GB, which removes out-of-memory failures on laboratory PCs.
  - DET007 complete analysis: 108 s → 12.5 s.
- **WEFFTRAN: one nuclide with unusable decay data no longer stops the whole calculation**. For example, `TH-227.txt` has transitions whose K + L conversion coefficients exceed the total coefficient; Th-227 is now reported as not corrected (its library lines are exported unchanged, with a warning) and every other nuclide is calculated. Before, no nuclide got a result.
- **Genie 2000 export is about 4 times faster**: an export now starts PowerShell once instead of three times (write, save, reopen and check in one session; the read-back check is kept). Files already read are not read again. In the GUI, the "Export" buttons copy the file that the calculation already exported and verified.
- **Corrected files are never silently left uncorrected**:
  - A well model that failed its convergence checks, or an ambiguous factor, now blocks the export (before, the file was written uncorrected and marked "verified").
  - Library nuclide names are compared in standard spelling ("Co60" = "CO-60").
  - CLI: with both `--library` and `--certificate`, every certificate line is corrected.
  - NaN or infinite engine values are an error (they were silently replaced by 1e-15).
- **Other corrections**:
  - GUI: opening a new library clears the previous summing result; switching between cylindrical/Marinelli and well no longer copies detector values into the wrong fields; loading an example keeps the data folder; the export dialogs offer only the file's real format; the laboratory's own materials appear at start-up.
  - Well detector files with `key = value` lines: optional fields no longer shift into the wrong slot.
  - A mistyped material name gives an error instead of a density of 1.0.
  - Cancel or a time limit gives a clean "Calculation cancelled" / "exceeded" message (a `PermissionError` appeared before on Windows).
  - XCOM tables are saved in the laboratory data folder, never in the program folder; XCOM runs once per material and session, and Cancel works during it.
  - Creating a material reports a failed write instead of claiming success.
  - CLI: `--output-*` never overwrites a file and reports an output that could not be produced; one failing batch job no longer stops the batch; a mistyped file name gives "File not found"; interactive mode returns a real exit code.
  - GammaVision `.EFT` exports keep the template's Windows line endings; the `_gv.txt` report is always rewritten.
- **Built-in well example**: now a complete analysis (efficiency transfer + summing), like the cylindrical and Marinelli examples.
- **GUI responsiveness**: typing in the forms is about 30 times faster (redrawing waits until typing pauses).
- **Removed duplicate or unused files**: the alias materials `Afs`, `Apple_ashed` and `Ashed rain filter` (identical to `Ashed air filter`, `Ashed apple` and `Rain_filter_ashed`), the unusable attenuation tables `test`, `ultima_gold` and `Rainfilterashed`, and leftovers of a test material (`cellulose_0229`). Projects using a removed alias stop with a clear "Material not found" message; choose the equivalent name. The original WEFFTRAN sources `peak_org.f` and `total_org.f` moved to `native/wefftran_original/` (no longer installed).
- **Code readability**: every module was rewritten or reformatted for readability (one statement per line, descriptive names, docstrings and comments), with old-versus-new result comparisons for every module.

## EffSuite 0.2.0 (November 2026)

- **EFFTRAN 5.0 & MEFFTRAN 1.9 Alignment & Physics Harmonization**:
  - Fully audited all source routines, data libraries, and macro workflows against Tim Vidmar's updated upstream distributions (`EFFTRAN 5.0` and `MEFFTRAN 1.9`).
  - **Dynamic Marinelli Monte Carlo Transfer Uncertainty**: Extended dynamic Monte Carlo uncertainty propagation from Cylindrical (EFFTRAN 5.0) to Marinelli beaker geometries (MEFFTRAN 1.9). Evaluated via 4-column output in `total.f` ($E, t, \sqrt{t_2}, s$) and propagated in `transfer.f` through $u = \sqrt{u_{\text{ref}}^2 + (100\,s_{\text{std}})^2 + (100\,s_{\text{sample}})^2}$, reaching full metrological parity while preserving double-precision floating-point arithmetic.
  - **Toolchain Modernization & GCC 15.2 Hardening**: Recompiled all 34 native Fortran 77 binaries using GCC 15.2.0 (`w64devkit`). Resolved Windows NT memory relocation issues (`WinError 623` DLL relocation error) observed with obsolete MinGW GCC 7.3.0 toolchains. Enhanced build flags with `-finit-local-zero` and `-fno-strict-aliasing` for robust stack and memory determinism.
  - **Upstream MEFFTRAN 1.9 Model Compatibility Shield**: Handled upstream detector format divergence (where MEFFTRAN 1.9 macro writes 19-line detector models read by `ptt.f`/`eta.f`, while `mine.f`/`total.f` read 16 lines), ensuring seamless execution for both 16-line and 19-line detector configurations.
  - **Material Library**: Added `heavy.txt` ($\text{H}_2\text{O}$, $\rho_0 = 2.0\text{ g/cm}^3$) to standard composition matrices for 100% interoperability with upstream project definitions.
  - **Installer & Packaging Optimizations**: Multi-threaded compression tuning in InnoSetup installer configuration.

## EffSuite 0.1.5 (November 2026)

- **EFFTRAN 4.9 & MEFFTRAN 1.8 Full Alignment & Verification**:
  - Re-audited and fully harmonized native engines with the updated official releases in `C:\PGM\EFFTRAN`.
  - **Cylindrical Efficiency Transfer Uncertainty**: Incorporated EFFTRAN 4.9's 4th-column Monte Carlo statistical uncertainty from `total.txt` into the cylindrical efficiency transfer formula ($u = \sqrt{u_{ref}^2 + (100\,s_{std})^2 + (100\,s_{sample})^2}$), preserving full precision `format(3e15.5)`.
  - **Decay Library & Scheme Alignment**: Retained upstream decay schemes in `kordaten.txt` (including $^{234}\text{Pa}$ with transition `41 43`) and verified inclusion of $^{94}\text{Nb}$ and $^{187}\text{W}$.
  - Documentation and audit reports updated for public release.

## EffSuite 0.1.4 (November 2026)

- **GammaVision support (implemented as in EFFTRAN/MEFFTRAN, untested)**: EffSuite now reads and writes ORTEC GammaVision files exactly the way EFFTRAN (`gv.f`, `EFFTRAN.EFT`) and MEFFTRAN (`MEFFTRAN.EFT`) do, in pure Python without requiring vendor COM components.
  - **Nuclide library (`.LIB`)**: 128-byte direct-access binary records (`EFFTRAN.Lib` layout from `gv.f`) are read and written non-destructively; gamma yields are divided by the coincidence-summing factors $C$, round-trip verified by reopening, and accompanied by a `<name>_gv.txt` audit report matching EFFTRAN's `gv.txt`.
  - **Efficiency (`.EFT`)**: Both EFFTRAN 11-token (`EFFTRAN.EFT`) and MEFFTRAN 5-token (`MEFFTRAN.EFT`) text layouts are read and exported non-destructively with round-trip verification, preserving source metadata and `FitType` trailer lines.
  - **Unambiguous Genie 2000 vs. GammaVision Identification**: Every GUI dialog, button, status message, `results.json` export entry (`"software": "Genie"` or `"GammaVision"`), and `report.html` table explicitly states whether an exported file is for **Genie 2000** (`.CAL`, `.NLB`, `.CTF`) or **GammaVision** (`.EFT`, `.LIB`).
  - **Selection**: Auto-detected from file extension (`.LIB` / `.EFT` = GammaVision; `.CAL` / `.NLB` / `.CTF` = Genie 2000), with manual override via `--software genie|gammavision`, the GUI **Software** selector, or `EFFSUITE_SOFTWARE`.
  - **Scope**: Genie `.CAL`/`.NLB`/`.CTF` support is unchanged (`genie.py`). GammaVision support is in `gammavision.py`, dispatched by `software.py`. Certificates (`.CTF`) and `.CAL` binary files remain Genie-only.
- **Bug fix (`--output-cal`, `--output-nlb`, `--output-ctf`)**: Fixed a result-key mismatch in `app_cli.py` where direct output flags and batch summary columns looked up `cal_output`/`nlb_output`/`ctf_output` instead of resolving the exported file from `genie_exports` in the published output directory.
- **Call for testers**: GammaVision has been implemented as EFFTRAN is doing it, but I cannot test it because I do not have the software. **Volunteers are welcome to test it and provide feedback.**

## EffSuite 0.1.3 (November 2026)

- **Integration of EFFTRAN 4.9 & MEFFTRAN 1.8 (with Upstream Bug Fixes)**:
  - Integrated the new 8-line source model format introducing explicit **Source density `[g/cm³]` (`rho`)** as the 8th line of `Sample/*.txt` and `Standard/*.txt`, scaling the nominal reference attenuation table (`Composition/<material>.txt`, density `rho0`) by $\rho / \rho_0$.
  - **Fixed upstream `do j=1,ne` loop-bound bug in `mine.f` and `scatter.f`**: Upstream `EFFTRAN 4.9` and `MEFFTRAN 1.8` looped `do j=1,ne` instead of `do j=1,ns` when scaling `smu(j)` and `smuc(j)`, leaving `mine.f` completely unscaled (`ne=0`) and `scatter.f` unscaled above $\sim 30\text{ keV}$ (`ne=25` out of $ns \approx 80\text{–}105$ XCOM rows). Fixed in EffSuite to `do j=1,ns` across all engines so `Water` at $\rho = 2.0\text{ g/cm}^3$ matches `HeavyWater` ($\rho_0 = 2.0\text{ g/cm}^3$) to 100% precision.
  - **Fixed upstream `Point.txt` (`vacuum`, `rho = 0.00`) `log(0)` singularity**: Added `if (rho.le.0.) rho=rho0` guard in `mine.f`, `total.f`, `scatter.f`, and `eta.f` to prevent `log(0.0) = -Infinity` / `NaN` when calculating point sources.
  - **Preserved full gamma energy precision in `transfer.f`**: Kept scientific format `format(3e15.5)` instead of upstream's `f12.1` truncation, and preserved EffSuite's Monte Carlo variance floor (`max(0., ...)`) and $10^{-15}$ efficiency floor.
  - Integrated in-memory `coin.txt` caching in `cylindrical/source/gv.f` with array bounds protection.
  - Added `HeavyWater.txt` ($\text{H}_2\text{O}$ at $\rho_0 = 2.0\text{ g/cm}^3$) to `assets/common/Composition/` and `assets/common/Material/`.
- **Extended 8-Line Source Density Scaling to WEFFTRAN (`well`), GUI, and CLI**:
  - Extended 8th-line sample density scaling ($\rho / \rho_0$) to WEFFTRAN (`spatial_summing.py` and native `well` Fortran sources).
  - **GUI (`Source` Tab & CAD View)**: Added `Source density [g/cm³]` spinbox directly below `Source material` in both Standard and Sample forms across Cylindrical, Marinelli, and Well modes. Selecting a material automatically populates its nominal density from `Composition/<material>.txt`, while preserving custom densities on file/project load. Live 2D CAD view now displays `ρ=<val> g/cm³`.
  - **Backward Compatibility**: Existing 7-line `.txt` source files and 7-element `.effsuite.json` project files load seamlessly and auto-populate `Source density` from `Composition/<material>.txt`.
  - **CLI**: `--sample-density` now sets the 8th source parameter (`source[7]`) directly without mutating global `Composition/*.txt` files.
- **Standardized Model Library & Generic WEFFTRAN Example**:
  - Cleaned bundled `Standard/` model directories in Cylindrical (`EFFTRAN`) and Marinelli (`MEFFTRAN`) to retain only official distribution models (`Point.txt`, `Solution.txt`, `Standard.txt`).
  - Standardized `WEFFTRAN` (`well`) bundled models to generic names (`Detector/well.txt`, `Sample/Sample.txt`, `Standard/Standard.txt`) using generic `Plastic_vial` container material.
- **Multithreaded WEFFTRAN 3D Spatial Ray-Tracing & Parallel Test Runner**:
  - Multithreaded spatial quadrature ray-tracing (`spatial_summing.py`) and nuclide cascade evaluation (`well_spatial.py`), reducing 3D well calculation times by ~3x while preserving exact serial equivalence (`--verify-serial`).
  - Added `tools/run_tests.py` (invoked by `Run_Tests_Windows.bat`) to execute all 14 test suites concurrently across CPU cores.
- **Fortran Uninitialized Array Fix (`coincidence.f`)**:
  - Explicitly zeroed `s(3000)` and `s1(3000)` prior to nuclide loop label `123 continue` in `cylindrical` and `marinelli` `coincidence.f` to prevent uninitialized memory carry-over.

## EffSuite 0.1.2 (November 2026)

- **Extended WEFFTRAN Detector Geometry & Holder Backscatter**:
  - Added optional extended well-detector parameters (`mantle_dead_layer`, `bottom_dead_layer`, `holder_thickness`, `sample_offset`, `holder_material`) with full 7-line backward compatibility and live 2D CAD rendering.
  - Verified against DET007 EGSnrc Monte Carlo benchmark and DET952 Marinelli laboratory dataset.
- **Repository & Packaging Cleanup**:
  - Unified asset structure, updated Windows installer (`EffSuite.iss`), and added attribution and mandatory scientific disclaimers.

## EffSuite 0.1.0-beta (November 2026)

- **Beta Release Transition**: Initial public evaluation and qualification release.
- **Fortran Numerical Safeguards & NaN Elimination**:
  - Guarded variance accumulator in MEFFTRAN/EFFTRAN `total.f` against negative floating-point cancellation (`sqrt(max(0.d0, ...))`), resolving the `NaN` / `Exit code 2` crash in Monte Carlo integration.
  - Clamped non-positive peak and total efficiency outputs to $10^{-15}$ in `efficiency.f` and `parallel_coincidence.py` to prevent $\log(0)$ crashes during cascade coincidence interpolation.
  - Recompiled all native Fortran calculation engines (cylindrical, Marinelli, well) for Windows x64.
- **Responsive GUI & High-DPI Display Support**:
  - Reorganized Welcome tab with side-by-side calculation workflow and coincidence target selection, eliminating vertical scrollbars at standard $1920 \times 1080$ resolution.
  - Pinned `#PageFooter` navigation bar outside scroll areas across all tabs so action buttons (`Start Guided Setup`, `Next`, `Run`) are always visible.
  - Custom-painted antialiased radio buttons (`PaintedRadio`) to ensure solid check indicators on Windows 11 under all display scaling settings (100% to 200%).
  - Fixed editable dropdown popups with explicit contrast styling to avoid dark-on-dark render defects.
  - Responsive CAD-style cross-section rendering dynamically scaling from 720p to 4K.
- **GenTran / EffSuite CLI Integration**:
  - Exit code 1 recognized as valid completion with uncorrected low-energy transitions marked (`*`), with fatal crashes isolated to exit code 2.
  - Asynchronous standard stream capture to avoid subprocess buffer deadlocks.
  - Cleaned calibration model name parsing to avoid file extension index mismatches.
- **Per-User Installer & Licensing Flexibility**:
  - Inno Setup installer configured with `PrivilegesRequired=lowest` for non-admin installation.
  - Added visible live licence status and unactivated community edition operation.

## EffSuite 0.0.9 evaluation release

- Material tab with formula/weight/density inputs and automatic XCOM generation.
- Editable Excel composition workbook and original XLS/text import.
- Simple `material` CLI command using the same service.
- Original EFFTRAN-style bottom tabs and detector/source/calibration forms.
- Functional shared GUI/CLI service for EFFTRAN, MEFFTRAN and WEFFTRAN.
- Automatic native response preparation and parallel nuclide calculations.
- Corrected spatial well summing integrated into the desktop and main CLI.
- One-command replay of GUI projects; simple model-name/file inputs.
- Bundled Windows x64 and Linux numerical kernels, source and hash manifests.
- High-precision native coincidence text output to preserve small factors.
- Cancellable background jobs, pre-calculation recovery and protected outputs.
- JSON/CSV/HTML-SVG reports; Genie vendor-CAM adapter with guarded copy export.
- Windows setup/launch/test scripts and PyInstaller/Inno Setup build recipes.
- Strict optional laboratory-reference comparison tool and input templates.

136 automated checks passed in the Linux authoring environment. Windows,
real Genie CAM and independent physical/laboratory qualification remain pending.
