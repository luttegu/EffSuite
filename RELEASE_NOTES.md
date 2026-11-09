# Release Notes

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
