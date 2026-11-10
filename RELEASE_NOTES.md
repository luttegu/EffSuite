# Release Notes

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
