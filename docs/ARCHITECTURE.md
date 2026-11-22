# EffSuite Architecture — v0.3.2

*For developers. The physics is described in
[CHANGES_FROM_ORIGINALS.md](CHANGES_FROM_ORIGINALS.md), and the well model in
[WELL_SPATIAL_MODEL.md](WELL_SPATIAL_MODEL.md).*

## Calculation flow

The GUI (`gui.py`) and the CLI (`app_cli.py`) build the same versioned JSON
project and call `suite.run_project`:

1. **Check** (`validate_project`). `model_io.py` validates:
   * 8-field source models, accepting 7-line files and taking the nominal
     density from `Composition/<material>.txt`;
   * detector models, including the optional 12-field well parameters;
   * calibration units and the `tcs_uncertainty` settings.
2. **Prepare.** Each step gets a private folder inside a hidden job folder
   (`.effsuite-job-*`). The bundled data, overlaid by the laboratory's data
   folder, and the models are copied there under the file names the Fortran
   programs expect. A material without an attenuation table is generated with
   XCOM.
3. **Efficiency transfer.**
   * Cylinder and Marinelli: the Fortran `total` program for the standard and
     the sample, then `transfer`.
   * Wells: the ray-traced response (`spatial_summing.well_peak_efficiencies`).
4. **Coincidence summing.**
   * **Cylinder and Marinelli:** the preparation stages (`mine` … `efficiency`)
     run first. `parallel_coincidence.calculate_parallel` then runs the
     unchanged `coincidence` program over groups of nuclides, in parallel
     subprocesses with private folders. A parent and its `b` continuation
     records stay together.
   * **Wells:** `well_spatial.calculate_spatial` with `spatial_summing.py`.
     The ray tracing runs in the compiled `raytrace` program
     (`assets/engines/well/source/raytrace.f90`, built by
     `tools/build_raytrace.py`). Python writes all inputs to one binary file,
     and several copies of the program each compute a share of the sample
     points; the Python loop is the fallback. Nuclide cascades are then
     evaluated per sample point, in threads. A nuclide with unusable decay
     data is reported and skipped.
   * **u(C):** `tcs_uncertainty.py` reruns the unchanged cascade calculation
     four times, with the peak and then the total efficiency curve scaled by
     e<sup>±h</sup>. For cylinder and Marinelli it uses scaled `efficiency.txt`
     and `buildup.txt` through `calculate_parallel`; for wells, scaled local
     efficiencies through `calculate_spatial(sensitivity_step=…)`. It combines
     the sensitivity coefficients with the project settings (see
     [TCS_UNCERTAINTY.md](TCS_UNCERTAINTY.md)).
5. **Match and export.** The factors are matched to the user's library lines.
   Corrected Genie/GammaVision copies are written and verified.
6. **Publish.** `results.json`, `efficiency.csv`, `summing.csv` and
   `report.html` are written. The job folder is then renamed to the result
   folder; a cancelled or failed job publishes nothing.

Native programs are always separate processes supervised from Python, with
cancellation, time limits and SHA-256 hashes recorded in `results.json`.

## Modules (`src/effsuite`)

| Module | Role |
|---|---|
| `suite.py` | the calculation service shared by GUI and CLI (`run_project`), result files and report |
| `model_io.py` | detector, source and calibration models in the original field order; validation |
| `parallel_coincidence.py` | parallel runner of the cylinder/Marinelli `coincidence` program; also `effsuite-coincidence` |
| `well_spatial.py` | well summing: convergence checks, report; also `effsuite-well-spatial` |
| `spatial_summing.py` | well response (ray tracing, scattering, pair probabilities) and per-point cascade counts |
| `tcs_uncertainty.py` | summing-factor uncertainty u(C): settings, sensitivity runs, combination |
| `well_parallel.py` | legacy WEFFTRAN subtraction calculation with the original stages (`effsuite-well-coincidence`) |
| `correction_diagnostics.py` | audit of WEFFTRAN's printed intermediate values |
| `software.py` | chooses the vendor backend per file (`.LIB`/`.EFT` = GammaVision, otherwise Genie; `--software` or `EFFSUITE_SOFTWARE` override) |
| `genie.py` | Genie 2000 `.CAL` / `.NLB` / `.CTF` through the installed CAM components and the bundled PowerShell bridge (`assets/genie_cam.ps1`); one PowerShell start per read or export, exports verified by reopening |
| `gammavision.py` | GammaVision `.LIB` / `.EFT` in pure Python (layouts from EFFTRAN `gv.f` and `EFFTRAN.EFT`), exports verified by reopening |
| `materials.py`, `material_gui.py` | compositions, XCOM generation in an isolated folder, Material Editor window |
| `lab_comparison.py` | controlled comparison with archived reference outputs (`effsuite-compare-lab`, `Compare_Lab.bat`) |
| `geometry_view.py` | dimensioned cross-section drawings |
| `gui.py` | Qt desktop. A QObject worker in a QThread supervises jobs; widgets are updated only in the GUI thread. A recovery snapshot precedes each calculation. |
| `app_cli.py` | command line, batch runner, interactive mode |
| `paths.py` | user folder, data and results locations |

## Repository layout

```text
EffSuite/
├── README.md, RELEASE_NOTES.md, THIRD_PARTY_NOTICES.md
├── docs/                         # documentation (see docs/README.md) and the project web page
├── src/effsuite/                 # Python package (modules above)
│   └── assets/
│       ├── common/               # Composition, Material and well Decay_Data shared by all geometries
│       ├── engines/<geometry>/   # Fortran sources, Windows/Linux programs + build manifests,
│       │                         # bundled models, kordaten.txt (cylinder/Marinelli)
│       ├── xcom/                 # NIST XCOM 3.1 source, data and programs
│       ├── examples/             # built-in example projects
│       └── templates/            # Material_Composition.xlsx
├── native/                       # historical WEFFTRAN geometry patches and original references
├── tests/                        # automated tests (tools/run_tests.py)
├── tools/                        # build, validation and release utilities
├── examples/                     # validation evidence (JSON) and example inputs
├── comparison/                   # templates for the laboratory comparison tool
├── installer/                    # Inno Setup script
├── third_party/                  # original notices and licences
└── *.bat                         # Windows setup, launch, test and build scripts
```

## Native programs

* Each `assets/engines/<geometry>/bin/<platform>/` folder holds the programs
  and a `build_manifest.json` with the source and binary hashes, the compiler
  and the flags.
* `tools/build_engines.py` builds the original stages, `tools/build_raytrace.py`
  builds the well ray tracer, and `tools/build_xcom.py` builds XCOM.
* The cylinder and Marinelli coincidence output format is widened from
  `f15.3` to `e23.15` in a temporary compilation copy, and the sources stay
  unchanged.

## Building and testing

```bat
Setup_Windows.bat                          :: create .venv and install dependencies
.venv\Scripts\python.exe tools\run_tests.py :: all test modules in parallel (or Run_Tests_Windows.bat)
Build_Windows.bat                          :: PyInstaller: dist\EffSuite\EffSuite_GUI.exe and EffSuite_CLI.exe
Build_Installer.bat                        :: Inno Setup installer (installer\EffSuite.iss)
python tools\set_version.py 0.3.2          :: set the version everywhere
```
