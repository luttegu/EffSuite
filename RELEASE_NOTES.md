# Release Notes

## EffSuite 0.5.3 (November 2026)

Code cleanup. The engines and all results are identical to 0.5.0.

- **Command line:** a finished calculation or batch run is now reported as `[PASS]` instead of `[SUCCESS]`, like the other `[INFO]` / `[WARN]` / `[ERROR]` messages.
- **Python package:** the `gui` extra is removed. It was identical to `desktop`; install with `pip install -e ".[desktop]"`.
- Unused code removed and comments made plainer. In the geometry drawing code, dimensions are no longer called "quotes" (French *cotes*).

## EffSuite 0.5.2 (November 2026)

Update check at every start. The engines and all results are identical to 0.5.0.

- **Update check at every start.** EffSuite checked at startup only once a day, and any check, including **Help → Check for updates…**, reset that day. After a check or **Remind me later**, a restart showed nothing until the next day. EffSuite now checks at every start; **Remind me later** asks again at the next start. The `update_last_check` setting is no longer used.
- **Don't ask again** button in the update window: turns off the check at startup, as **Help → Check for updates at startup** does. A manual check still works.
- **Users of 0.4.0 and 0.5.0 must install by hand** (see 0.5.1).

## EffSuite 0.5.1 (November 2026)

Software update fixes. The engines and all results are identical to 0.5.0.

- **Download and install did not install.** In 0.4.0 and 0.5.0, **Help → Check for updates… → Download and install** downloaded and verified the installer, then stopped without starting it. Closing the download progress window was treated as pressing **Cancel**. The installer now starts after the download.
  - **Users of 0.4.0 and 0.5.0 must install 0.5.1 by hand**: download `EffSuite_0.5.1_Setup.exe` from the release page and run it. Data, results and settings are kept. Updates from the Help menu work from 0.5.1 on.
  - An installer already downloaded by 0.4.0 or 0.5.0 is in `%TEMP%\EffSuite_update` and can be run from there.
- **Release notes readable in Windows dark mode.** The update window showed dark text on a dark background. EffSuite now always uses its light colours, whatever the Windows colour mode.
- **Update window layout.** Title with the new version, a line with the installed version and download size, a white panel for the release notes, and code names in Cascadia Mono or Consolas.
- README engines badge names EFFTRAN 5.1 and MEFFTRAN 2.0.

## EffSuite 0.5.0 (November 2026)

Engines updated to EFFTRAN 5.1 and MEFFTRAN 2.0 (November 2026). Cylinder results are unchanged, except transferred efficiencies in the last printed digit. Marinelli peak efficiencies and P/T ratios change by up to about 0.4 %, summing factors by up to 0.0006.

- **Marinelli: MEFFTRAN 2.0 routines.** EffSuite now uses the MEFFTRAN 2.0 sources, including their precision: `buildup.f`, `efficiency.f`, `eta.f` and `scatter.f` compute in single precision (`real`), and `total.f` keeps double precision for the geometry but accumulates the Monte Carlo tallies in single precision. The previous EffSuite sources used double precision throughout these routines. The EffSuite safeguards (density fallback, variance and logarithm guards, `e23.15` summing output) are applied as before.
  - On the example of the MEFFTRAN 2.0 distribution, EffSuite now gives the same `total.txt`, `scatter.txt`, `buildup.txt`, `eta.txt`, `efficiency.txt` and `ptt.txt` as the upstream programs, and the same `coin.txt` to its 3 decimals. Compared with the previous build: total efficiency changes by 2·10⁻⁵ (relative), peak efficiency by up to 0.35 %, P/T by up to 0.43 %, and *C* by up to 0.0006 (0.2 %).
  - Windows and Linux Marinelli programs rebuilt; the Linux ones with GNU Fortran 14.4.
  - MEFFTRAN 2.0 reads a 16-line detector file in every stage, which fixes the MEFFTRAN 1.9 format defect. EffSuite still opens 19-line files written by MEFFTRAN 1.9.
- **Cylinder: EFFTRAN 5.1.** The stages EffSuite runs are unchanged from 5.0, so cylinder results are unchanged, except `transfer` (next item). The sources are now the 5.1 files with the EffSuite safeguards (text differences only), and the Windows programs give byte-identical output to the previous build. The 5.1 change is in the Excel workbooks (Form controls instead of ActiveX).
- **`transfer.f` in single precision.** EffSuite's stage-isolated `transfer.f` (cylinder and Marinelli) now computes in single precision, in the order of operations of EFFTRAN 5.1 and MEFFTRAN 2.0; it used double precision. On the transfer examples of both distributions, its 16 efficiencies equal those of the upstream `transfer.exe`. Windows and Linux programs rebuilt.
- **Linux engines were out of date.** The Linux cylinder and Marinelli programs were still the v0.1.1 builds, without bulk density and without the uncertainty column of `total.txt`. All 20 are rebuilt with GNU Fortran 14.4 from the current sources; their output files equal the Windows ones, except a few summing factors that differ by 2·10⁻⁷ (relative). The Linux well programs `mine`, `total`, `scatter` and `efficiency` were also v0.1.1 builds, without density scaling and the path-length fix for tall samples; they are rebuilt from the unchanged sources and now give the same output files as the Windows programs.
- **Data.** `kordaten.txt`, the materials and the Detector, Sample and Standard models are unchanged in 5.1/2.0 (upstream only moved the Nb-94 record). EffSuite keeps W-187, which upstream still lacks.
- **`heavy` is no longer bundled.** MEFFTRAN 2.0 no longer ships `heavy.txt` (H₂O at ρ₀ = 2.0 g/cm³), so the bundled materials are now the 19 of EFFTRAN 5.1 and MEFFTRAN 2.0. A project or source model that uses `heavy` stops with a missing-material error. Use `water` with a bulk density of 2.0 g/cm³ on line 8 of the source model, which gives the same results, or copy `heavy.txt` from a 0.4.0 installation (`assets\common\Composition` and `Material`) into your data folder.
- **Engine build.** `tools/build_engines.py` puts the compiler's folder first on `PATH`, so that another MinGW on `PATH` (for example EGSnrc's) cannot supply an older `ld.exe` that produces programs Windows refuses to start.
- READMEs, notices, About box, CLI banner and documentation name EFFTRAN 5.1 and MEFFTRAN 2.0. Details in [CHANGES_FROM_ORIGINALS.md](docs/CHANGES_FROM_ORIGINALS.md), section 1.9.

## EffSuite 0.4.0 (November 2026)

The engines and all results are unchanged.

- **User folder on PCs without Genie 2000.** EffSuite no longer creates `C:\GENIE2K` on machines that do not have it.
  - `C:\GENIE2K\EffSuite` is used only when it already exists or when Genie 2000 is installed (`C:\GENIE2K` exists). Existing `C:\GENIE2K\EffSuite` folders are kept, with or without Genie 2000.
  - Otherwise the user folder is `Documents\EffSuite`, or `%USERPROFILE%\EffSuite` when Documents is synchronised by OneDrive and `Documents\EffSuite` does not exist yet.
  - Installer: without Genie 2000, the program goes to `%LOCALAPPDATA%\Programs\EffSuite` and `EFFSUITE_ROOT` is no longer set, so Data and Results are no longer created inside the program folder. Installations where an earlier version already set `EFFSUITE_ROOT` to the program folder keep it.
  - **Help → About EffSuite** shows the user folder in use. `EFFSUITE_ROOT` still overrides the choice.
  - The GUI start-up error log `gui_startup.log` is written to `Logs` in the user folder (it was always `Documents\EffSuite\Logs`).
- **Software update check.** **Help → Check for updates…** compares the installed version with the newest GitHub release (pre-releases included) and shows its release notes.
  - **Download and install** downloads the installer, verifies its size and SHA-256 against GitHub, closes EffSuite after the unsaved-project prompt and runs the installer in place. Data, results and settings are kept. **Remind me later** and **Skip this version** are also offered.
  - EffSuite checks once a day at startup; turn it off with **Help → Check for updates at startup**. Settings are stored in `%APPDATA%\EffSuite\settings.json` (`update_check_at_startup`, `update_last_check`, `update_skipped_version`).
  - Installer: a silent upgrade started with `/RELAUNCH=1` restarts EffSuite when it finishes.
  - EffSuite 0.3.3 and older have no update check: install this release once by hand; later releases can then be installed from **Help → Check for updates…**.
  - New CLI command `check-update` reports the newest release without installing it.
  - A copy run from source opens the release page instead of installing.
- **Plainer GUI text.** Buttons, menus, tabs and group titles use sentence case without emoji; buttons for open, save, folder, run, stop, next, refresh, apply and clear show an icon. Some labels changed:
  - The first tab is **Start** (was Welcome). **Check Transfer Only** / **Check Summing Only** are now **Calculate transfer only** / **Calculate summing only**. The geometry preview's **Full-Screen / All Quotes…** is now **Large view…**, and its "Detector Only" choice is **Detector only**.
  - Help menu: **Workflow guide**, **Materials and density guide**, **Command line and batch guide**, **Disclaimer…**, **About EffSuite**.
- **New GUI look.** Light grey window with white cards and one blue accent. Green is kept for the final run button and the Material Editor's **Apply**.
  - The step tabs are drawn as a segmented control. Group titles sit above their card, and the step line at the top of each page is no longer boxed.
  - Buttons have five roles: default, primary, tinted, success and danger. Their line icons are drawn in the button's text colour, replacing the Windows stock icons.
  - Fields have rounded corners and a blue focus ring. Check boxes and radio buttons fill with the accent colour when selected. The log is a dark console.
  - The top bar labels are now **Geometry**, **Software** and **Workers**, without colon or bold.
  - Page margins and spacing are slightly larger. The exports dialog after a complete analysis is wider (720 px), so its labels and buttons are no longer cut off, and the disclaimer and exports dialogs fit their content height.
  - Colours, radii and the stylesheet are defined once, in `src/effsuite/gui_theme.py`. Behaviour and calculations are unchanged.
- **Built-in help corrected.** It now names the bundled engines as EFFTRAN 5.0 and MEFFTRAN 1.9 (it said 4.9 and 1.8). The two different GammaVision notices are merged into one. The credit line matches the README. The CLI start-up banner also showed EFFTRAN 4.8 / MEFFTRAN 1.7; it now shows 5.0 / 1.9.
- **CLI help.** Shorter option descriptions, `FILE` / `DIR` / `N` metavars, `--calibration` now lists `.EFT`, and `--output-cal` / `--output-nlb` name the GammaVision `.EFT` / `.LIB` files they also accept. `--version` credits Claude, as the banner does.
- **Documentation.** Plainer prose across the user and technical documents, with GUI label references updated.

## EffSuite 0.3.3 (November 2026)

The engines, their sources and all results are unchanged.

- **Licence and copyright notices completed.**
  - New root `LICENSE` (GPL-3.0 text, identical to `third_party/GPL-3.txt`). EffSuite is licensed as **GPL-3.0-or-later**, declared in `pyproject.toml` (`license = "GPL-3.0-or-later"`; build requirement raised to setuptools 77). The installer installs it as `LICENSE.txt` with a Start-menu shortcut.
  - New `NOTICE.txt` in each engine `source/` folder, in `native/` and in `assets/xcom/`. They give Tim Vidmar's permission notice for the EFFTRAN 5.0 and MEFFTRAN 1.9 sources, which do not carry it in each file, and identify the Numerical Recipes routines (`sobseq`, `rtbis`), including the two WEFFTRAN `total.f` files whose Numerical Recipes notice line is missing. The Fortran files themselves are not modified.
  - `THIRD_PARTY_NOTICES.md` corrected and extended: copyright years per engine, where each notice is kept, the Numerical Recipes routines, the non-commercial restriction on NIST XCOM, libquadmath (LGPL-2.1, statically linked), Qt/PySide6 (LGPL-3.0), the Python runtime and packages, and trademarks.
  - New `third_party/LGPL-2.1.txt` and `third_party/LGPL-3.txt` (official texts from gnu.org).
  - The frozen Windows build now includes the licence files of the Python runtime and of every bundled package in `_internal/licenses/` (with the LGPL-3.0 and GPL-3.0 texts added for PySide6 and Shiboken6, whose wheels carry only the Qt commercial licence file).

## EffSuite 0.3.2 (November 2026)

The engines and the results for the same inputs are unchanged from 0.3.1.

- **Only the original materials are bundled.** The program now installs the 20 materials of the EFFTRAN 5.0 and MEFFTRAN 1.9 distributions (CLYC, CZT, CsI, Ge, LaBr3, NaI, air, aluminium, beryllium, cellulose, copper, heavy, iron, lead, plexiglass, polystyrene, silica, soil, vacuum, water). The 51 other materials of earlier versions (laboratory matrices, `Plastic_vial`, `HeavyWater`, `polyethylene`…) are removed: **copy them into your data folder** if your models use them (`HeavyWater` = the original `heavy`).
  - Each user keeps their own materials and models in **their data folder** (default `C:\GENIE2K\EffSuite\Data`). Search order: project data folder, default data folder, legacy `Documents\EffSuite\Data`, bundled originals.
  - **New: choose the default data folder.** GUI **Tools → 📁 Default Data Folder…** / **↺ Reset Default Data Folder**; CLI `config` (show), `config --data-dir DIR`, `config --reset-data-dir`. Saved in `%APPDATA%\EffSuite\settings.json`; the `EFFSUITE_DATA` environment variable takes precedence. The `Composition` and `Material` subfolders are created as needed, also in an existing data folder that had none.
  - A new material library no longer receives a copy of the bundled materials (use `--base-data` to copy a folder explicitly). Creating a material with the name of an original asks before shadowing it.
  - Well runs and the spatial model now find materials in every data folder, not only in the project's.
  - The GUI Load / Store model and calibration dialogs open in the data folder in use (`Detector`, `Sample`, `Standard`, `Calibration`), not always in `<EffSuite root>\Data`. The top bar shows the data folder in use.
  - The bundled well example models use `polystyrene` instead of `Plastic_vial`; the default new-source materials are `water` / `polystyrene`.
  - Tests run with an isolated, empty data folder; the two laboratory materials needed by the validation cases are in `tests/data/materials`.

- **Material Editor in its own window.** The Material tab is replaced by a separate, non-modal window, so you can create or modify a material while filling in the Detector and Standard & Sample pages.
  - Open it with the new **🧪 Materials…** button on the Detector and Standard & Sample pages, with **Tools → Material Editor…**, or with **✏️ Edit** next to a material field (which loads that material).
  - **✔ Apply** (formerly "Create Material and Attenuation Table") runs XCOM and updates every material list at once. When the window was opened with **✏️ Edit**, the material is selected in that field, and for a source material its density is filled in, also when an existing material is overwritten under the same name. The window shows which field Apply will update, and stays open.
  - What you type in the window is kept across geometry changes. Apply is unavailable while a calculation runs. Closing the main window closes the editor.
- **Source tab renamed "Standard & Sample"** (just **"Sample"** with True Coincidence Summing Only, where the Standard is not needed), with the Standard column first, as in the original EFFTRAN.
  - With **True Coincidence Summing Only**, the Standard column (and the Standard choice in the geometry preview) is hidden: the summing factors need only the detector and the sample. The page title and the **Next** button say "Sample", and the Standard values are kept for when you switch back to a workflow with efficiency transfer.
- Documentation updated: new "Where materials are stored" section in the Materials guide, the `config` command in the CLI guide, the data folder in the User Guide, the bundled well models in Changes from the Originals, and the new window and tab name throughout; test count now 166 (17 modules).

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

- **Aligned with EFFTRAN 5.0 and MEFFTRAN 1.9.** All source routines, data libraries and macro workflows were compared with Tim Vidmar's updated distributions (`EFFTRAN 5.0` and `MEFFTRAN 1.9`).
  - **Marinelli transfer uncertainty from Monte Carlo statistics.** The Monte Carlo uncertainty propagation already used for cylinders (EFFTRAN 5.0) now also covers Marinelli beakers (MEFFTRAN 1.9). `total.f` writes a 4-column output ($E, t, \sqrt{t_2}, s$) and `transfer.f` propagates it through $u = \sqrt{u_{\text{ref}}^2 + (100\,s_{\text{std}})^2 + (100\,s_{\text{sample}})^2}$, as in MEFFTRAN 1.9, in double precision.
  - **GCC 15.2.** All 34 native Fortran 77 programs recompiled with GCC 15.2.0 (`w64devkit`). This fixes the `WinError 623` DLL relocation failures of the old MinGW GCC 7.3.0 builds. The flags `-finit-local-zero` and `-fno-strict-aliasing` were added to make stack and memory behaviour deterministic.
  - **MEFFTRAN 1.9 detector format.** The MEFFTRAN 1.9 macro writes 19-line detector models, which `ptt.f`/`eta.f` read, while `mine.f`/`total.f` read 16 lines. EffSuite now accepts both 16-line and 19-line detector files.
  - **Materials.** Added `heavy.txt` ($\text{H}_2\text{O}$, $\rho_0 = 2.0\text{ g/cm}^3$), so that upstream projects using it load unchanged.
  - **Installer.** Multi-threaded compression in the Inno Setup script.

## EffSuite 0.1.5 (November 2026)

- **Aligned with EFFTRAN 4.9 and MEFFTRAN 1.8.** The native engines were compared again with the updated releases in `C:\PGM\EFFTRAN` and brought in line.
  - **Cylinder transfer uncertainty.** The cylinder efficiency transfer formula now includes EFFTRAN 4.9's Monte Carlo statistical uncertainty, the 4th column of `total.txt` ($u = \sqrt{u_{ref}^2 + (100\,s_{std})^2 + (100\,s_{sample})^2}$). The full-precision `format(3e15.5)` is kept.
  - **Decay data.** The upstream decay schemes in `kordaten.txt` are kept, including $^{234}\text{Pa}$ with transition `41 43`. $^{94}\text{Nb}$ and $^{187}\text{W}$ were checked to be present.
  - Documentation and audit reports updated for the public release.

## EffSuite 0.1.4 (November 2026)

- **GammaVision support (implemented as in EFFTRAN/MEFFTRAN, untested).** EffSuite now reads and writes ORTEC GammaVision files the way EFFTRAN (`gv.f`, `EFFTRAN.EFT`) and MEFFTRAN (`MEFFTRAN.EFT`) do, in pure Python, without vendor COM components.
  - **Nuclide library (`.LIB`).** 128-byte direct-access binary records (`EFFTRAN.Lib` layout from `gv.f`) are read, and written without changing the source file. Gamma yields are divided by the summing factors $C$, the written file is reopened to verify it, and a `<name>_gv.txt` audit report like EFFTRAN's `gv.txt` is written beside it.
  - **Efficiency (`.EFT`).** Both the EFFTRAN 11-token (`EFFTRAN.EFT`) and the MEFFTRAN 5-token (`MEFFTRAN.EFT`) text layouts are read. Exports leave the source file unchanged, are verified by reading them back, and keep the source metadata and `FitType` trailer lines.
  - **Genie 2000 vs. GammaVision labels.** Every GUI dialog, button, status message, `results.json` export entry (`"software": "Genie"` or `"GammaVision"`) and `report.html` table states whether an exported file is for **Genie 2000** (`.CAL`, `.NLB`, `.CTF`) or **GammaVision** (`.EFT`, `.LIB`).
  - **Selection.** The backend is chosen from the file extension (`.LIB` / `.EFT` = GammaVision; `.CAL` / `.NLB` / `.CTF` = Genie 2000). Override it with `--software genie|gammavision`, the GUI **Software** selector, or `EFFSUITE_SOFTWARE`.
  - **Scope.** Genie `.CAL`/`.NLB`/`.CTF` support is unchanged (`genie.py`). GammaVision support is in `gammavision.py`, dispatched by `software.py`. Certificates (`.CTF`) and `.CAL` binary files remain Genie-only.
- **Bug fix (`--output-cal`, `--output-nlb`, `--output-ctf`).** In `app_cli.py`, the direct output flags and the batch summary columns looked up `cal_output`/`nlb_output`/`ctf_output` instead of taking the exported file from `genie_exports` in the published output directory.
- **Call for testers**: GammaVision has been implemented as EFFTRAN is doing it, but I cannot test it because I do not have the software. **Volunteers are welcome to test it and provide feedback.**

## EffSuite 0.1.3 (November 2026)

- **EFFTRAN 4.9 and MEFFTRAN 1.8, with fixes for upstream bugs.**
  - New 8-line source model format: the 8th line of `Sample/*.txt` and `Standard/*.txt` holds the **Source density `[g/cm³]` (`rho`)**, which scales the nominal reference attenuation table (`Composition/<material>.txt`, density `rho0`) by $\rho / \rho_0$.
  - **Upstream loop-bound bug in `mine.f` and `scatter.f`.** Upstream `EFFTRAN 4.9` and `MEFFTRAN 1.8` looped `do j=1,ne` instead of `do j=1,ns` when scaling `smu(j)` and `smuc(j)`. `mine.f` was left completely unscaled (`ne=0`), and `scatter.f` unscaled above $\sim 30\text{ keV}$ (`ne=25` out of $ns \approx 80\text{–}105$ XCOM rows). EffSuite uses `do j=1,ns` in all engines, and `Water` at $\rho = 2.0\text{ g/cm}^3$ now matches `HeavyWater` ($\rho_0 = 2.0\text{ g/cm}^3$) exactly.
  - **Upstream `log(0)` for `Point.txt` (`vacuum`, `rho = 0.00`).** An `if (rho.le.0.) rho=rho0` guard in `mine.f`, `total.f`, `scatter.f` and `eta.f` prevents `log(0.0) = -Infinity` / `NaN` for point sources.
  - **Full gamma energy precision in `transfer.f`.** The scientific format `format(3e15.5)` is kept instead of upstream's `f12.1` truncation, and so are EffSuite's Monte Carlo variance floor (`max(0., ...)`) and $10^{-15}$ efficiency floor.
  - In-memory `coin.txt` caching in `cylindrical/source/gv.f`, with array bounds protection.
  - Added `HeavyWater.txt` ($\text{H}_2\text{O}$ at $\rho_0 = 2.0\text{ g/cm}^3$) to `assets/common/Composition/` and `assets/common/Material/`.
- **8-line source density for WEFFTRAN (`well`), the GUI and the CLI.**
  - Sample density scaling ($\rho / \rho_0$) now also applies to WEFFTRAN (`spatial_summing.py` and the native `well` Fortran sources).
  - **GUI (`Source` tab and CAD view).** A `Source density [g/cm³]` spinbox below `Source material` in the Standard and Sample forms, for cylindrical, Marinelli and well. Choosing a material fills in its nominal density from `Composition/<material>.txt`; a density loaded from a file or project is kept. The 2D CAD view shows `ρ=<val> g/cm³`.
  - **Backward compatibility.** Existing 7-line `.txt` source files and 7-element `.effsuite.json` project files still load, with `Source density` taken from `Composition/<material>.txt`.
  - **CLI.** `--sample-density` sets the 8th source parameter (`source[7]`) directly and leaves the shared `Composition/*.txt` files unchanged.
- **Bundled models.**
  - The cylinder (`EFFTRAN`) and Marinelli (`MEFFTRAN`) `Standard/` folders keep only the official distribution models (`Point.txt`, `Solution.txt`, `Standard.txt`).
  - The `WEFFTRAN` (`well`) models have generic names (`Detector/well.txt`, `Sample/Sample.txt`, `Standard/Standard.txt`) and use a generic `Plastic_vial` container material.
- **Multithreaded well ray tracing and parallel test runner.**
  - Spatial quadrature ray tracing (`spatial_summing.py`) and nuclide cascade evaluation (`well_spatial.py`) run in threads. 3D well calculations are about 3 times faster, and results stay identical to a serial run (`--verify-serial`).
  - New `tools/run_tests.py` (called by `Run_Tests_Windows.bat`) runs all 14 test suites in parallel across CPU cores.
- **Uninitialised arrays in `coincidence.f`.** `s(3000)` and `s1(3000)` are now zeroed before the nuclide loop label `123 continue` in the `cylindrical` and `marinelli` `coincidence.f`, so no memory contents carry over between nuclides.

## EffSuite 0.1.2 (November 2026)

- **Extended well detector geometry and holder backscatter.**
  - Optional extended well-detector parameters (`mantle_dead_layer`, `bottom_dead_layer`, `holder_thickness`, `sample_offset`, `holder_material`). 7-line files still load, and the live 2D CAD view draws the new parts.
  - Verified against the DET007 EGSnrc Monte Carlo benchmark and the DET952 Marinelli laboratory dataset.
- **Repository and packaging cleanup.** Unified asset structure, updated Windows installer (`EffSuite.iss`), and added attribution and the mandatory scientific disclaimers.

## EffSuite 0.1.0-beta (November 2026)

- **Beta release.** First public evaluation and qualification release.
- **Fortran numerical safeguards against NaN.**
  - The variance accumulator in MEFFTRAN/EFFTRAN `total.f` is guarded against negative floating-point cancellation (`sqrt(max(0.d0, ...))`). This fixes the `NaN` / `Exit code 2` crash in the Monte Carlo integration.
  - Non-positive peak and total efficiency outputs are clamped to $10^{-15}$ in `efficiency.f` and `parallel_coincidence.py`, so the cascade coincidence interpolation no longer crashes on $\log(0)$.
  - All native Fortran engines (cylindrical, Marinelli, well) recompiled for Windows x64.
- **GUI layout and high-DPI displays.**
  - Welcome tab reorganised: calculation workflow and coincidence target selection side by side, with no vertical scrollbars at $1920 \times 1080$.
  - The `#PageFooter` navigation bar sits outside the scroll areas on every tab, so the action buttons (`Start Guided Setup`, `Next`, `Run`) are always visible.
  - Custom-painted antialiased radio buttons (`PaintedRadio`), so check indicators stay solid on Windows 11 at every display scaling from 100% to 200%.
  - Editable dropdown popups have explicit contrast styling; they were drawn dark on dark.
  - CAD-style cross-section drawing that scales from 720p to 4K.
- **GenTran / EffSuite CLI integration.**
  - Exit code 1 means a valid completion with uncorrected low-energy transitions marked (`*`); fatal crashes use exit code 2.
  - Standard output and error are read asynchronously, which avoids subprocess buffer deadlocks.
  - Calibration model name parsing no longer trips over file extensions (index mismatches).
- **Per-user installer and licensing.**
  - The Inno Setup installer uses `PrivilegesRequired=lowest`, so no administrator rights are needed.
  - Visible live licence status, and operation as an unactivated community edition.

## EffSuite 0.0.9 evaluation release

- Material tab with formula/weight/density inputs and automatic XCOM generation.
- Editable Excel composition workbook and original XLS/text import.
- Simple `material` CLI command using the same service.
- Original EFFTRAN-style bottom tabs and detector/source/calibration forms.
- Shared GUI/CLI service for EFFTRAN, MEFFTRAN and WEFFTRAN.
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
