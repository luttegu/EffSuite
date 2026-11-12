# EffSuite 0.1.5 Architecture & Implementation

`app_cli.py` and `gui.py` call `suite.run_project` using the same versioned
JSON project. `model_io.py` validates 8-field source models (with 7-line backward
compatibility and nominal density lookup from `Composition/<material>.txt`),
detector models (including optional 12-field extended well parameters), and calibration
units. The service prepares native inputs automatically in a private job
folder, supervises cancellable executable stages, and publishes completed
JSON/CSV/HTML output in a new directory.

Cylinder and Marinelli summing use `parallel_coincidence.py`; parent/continuation
records run together in isolated subprocess directories. Well summing uses
`well_spatial.py` and `spatial_summing.py`, with multithreaded 3D spatial-angular
ray-tracing across quadrature points and thread-pooled nuclide cascade evaluation.
`software.py` selects the vendor backend per file (`.LIB`/`.EFT` = GammaVision, otherwise Genie;
override with `--software` or `EFFSUITE_SOFTWARE`).
`genie.py` calls the installed vendor CAM components through the bundled PowerShell
bridge and verifies exported copies by reopening them.
`gammavision.py` reads and writes ORTEC GammaVision `.LIB` libraries and `.EFT` efficiency files in pure Python
(layout taken from EFFTRAN `gv.f` and `EFFTRAN.EFT`), also verifying exported copies by reopening them.

The desktop uses Qt Widgets and the original workbook tab/form arrangement.
A QObject worker in a QThread supervises jobs; scientific native routines run
in separate processes. GUI widgets are updated only in the GUI thread.
A recovery snapshot precedes each calculation. `lab_comparison.py` checks
explicitly paired reference exports against declared laboratory criteria.

Assets contain native source, bundled Linux/Windows programs, original data,
reference binaries and source/binary build manifests. Current execution and
qualification limits are in VALIDATION.md and WEFFTRAN_FIX.md.

MaterialEditor in `material_gui.py` and the `material` CLI command share
`materials.py`. Composition validation/import and XCOM generation are separate
from the detector calculation service. XCOM runs in an isolated directory;
a material definition, attenuation table and provenance metadata are published
under a newly named material. Density remains a supplied bulk-property input.
