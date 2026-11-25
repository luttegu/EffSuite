# EffSuite User Guide — v0.5.2

> **Spectrometry software.** EffSuite reads and writes **Canberra / Mirion
> Genie 2000** files (`.CAL`, `.NLB`, `.CTF`) and **ORTEC GammaVision** files
> (`.EFT`, `.LIB`). GammaVision support follows EFFTRAN and MEFFTRAN exactly
> but is **untested**: I do not have the software, so volunteers are welcome
> to test it and give feedback. Other formats (ORTEC Maestro `.spc` / `.cal`,
> InterWinner) are not supported.

> **WEFFTRAN (well detectors).** The well engine has been patched for ray
> boundary handling and uses a 3D spatial summing model, but it is **not yet
> qualified in the laboratory**. Treat well results as experimental and
> verify them independently.

## 1. Getting started

On the **Start** page, choose what to calculate:

| Choice | Needs | Produces |
|---|---|---|
| **Complete analysis** (recommended) | detector, standard and sample, reference calibration, nuclides | transferred calibration and summing factors |
| **Efficiency transfer only** | detector, standard and sample, reference calibration | transferred sample calibration (`.CAL` / `.EFT`) |
| **True coincidence summing only** | detector, sample, nuclides or a library | summing factors and a corrected `.NLB` / `.CTF` / `.LIB` |

At the top of the window, set **Geometry** (EFFTRAN 5.1 for cylinders,
MEFFTRAN 2.0 for Marinelli beakers, WEFFTRAN for well detectors),
**Software** (Auto by default: GammaVision for `.EFT` / `.LIB`, Genie 2000 for
`.CAL` / `.NLB` / `.CTF`), **Workers** (Auto = number of CPUs minus 2) and the
data folder (**Data folder…**).

Then go through the tabs with **Start guided setup** and **Next**:
**Detector → Standard & Sample → Efficiency → Library / Certificate**. New
materials are created in the **Material Editor** window (section 7).
**Load built-in example** fills
every tab with a working example, and **Open project…** opens a saved
project.

### Software updates

**Help → Check for updates…** asks GitHub for the newest release. When a newer
version exists, a dialog shows its release notes with four choices:

- **Download and install**: downloads `EffSuite_<version>_Setup.exe`, checks its
  size and SHA-256 against the values published on GitHub, closes EffSuite (it
  asks first if the project has unsaved changes) and runs the installer. The
  update installs over the current version in the same folder; data, results
  and settings are kept. In a folder you can write to, the installer runs
  without questions and EffSuite restarts when it is finished. If the
  installation folder needs administrator rights (an all-users installation),
  the installer wizard opens, Windows asks for permission, and the last wizard
  page offers to start EffSuite.
- **Remind me later**: asks again at the next start.
- **Skip this version**: no reminder at startup for this version. A manual
  check still offers it.
- **Don't ask again**: turns off the check at startup. A manual check still
  works; turn the startup check back on with **Help → Check for updates at
  startup**.

EffSuite also checks at every start, a few seconds after the window
opens. The offer waits until no dialog is open and no calculation runs. Turn
this off with **Help → Check for updates at startup**. The check only reads the
public release list on GitHub; nothing is sent except the EffSuite version in
the request header. Without internet access the startup check fails silently.

The update check exists from version 0.4.0; older versions are updated
by running the new installer by hand. In 0.4.0 and 0.5.0, **Download and
install** downloads the installer but does not start it: install 0.5.1 or
later by hand once. Updates from the Help menu work from 0.5.1 on. A copy run from source (not installed) opens the release page instead of
installing; update it with `git pull`. Releases:
<https://github.com/luttegu/EffSuite/releases>.

## 2. Detector and source models

* **Detector.** Load a detector text file, or type the dimensions. 16-line
  (MEFFTRAN) and 19-line (EFFTRAN) detector files are both accepted. Well
  detectors accept optional extended fields (mount cup, mantle and bottom dead
  layers, sample offset); see
  [CHANGES_FROM_ORIGINALS.md, section 2.5](CHANGES_FROM_ORIGINALS.md#25-optional-extended-well-detector-inputs).
* **Standard & Sample** (named **Sample** with True coincidence summing only). Load or enter the sample and the standard side by
  side. The standard (reference calibration source) is needed only for
  efficiency transfer: with **True coincidence summing only** the Standard
  column is hidden and only the sample is used. Its values are kept and
  come back when you choose a workflow with efficiency transfer.
  * Both 7-line source files and 8-line source files (with
    `Source density [g/cm³]`) load.
  * Choosing a `Source material` fills the density with the nominal value
    from `Composition/<material>.txt`; you can then change it.
  * Do not infer dimensions from a model's name.
* The cross-section view updates as you type and shows every dimension.

## 3. Efficiency transfer

In **Efficiency**, import the standard calibration with
**Import standard efficiency (.CAL / .EFT / CSV)…**. It accepts a Genie `.CAL`, a GammaVision
`.EFT`, or a two- or three-column text/CSV file. You can also paste cells from
a spreadsheet into the first three columns.

The columns are:
* energy in keV;
* efficiency as a fraction (0.05 means 5 %);
* optionally, the relative uncertainty in percent (3 means 3 % relative).

The calibration needs 2 to 93 points with strictly increasing energies.

Press **Calculate transfer only**, or the run button in the page footer, then
inspect the transferred values and the standard/sample graph.

The **Sample u [%]** column keeps the original programs' transfer
uncertainty:
* **Cylinder and Marinelli:** the reference uncertainty combined with the
  Monte Carlo statistics of the standard and sample efficiencies;
* **Wells:** fixed 0.5 % + 0.5 % terms.

Neither is a complete uncertainty budget.

## 4. Coincidence summing

In **Library** (or **Certificate**), either type the nuclides
(`Co-60, Cs-134, Eu-152`) or open a Genie `.NLB` / `.CTF` or a GammaVision
`.LIB`; its nuclides fill in automatically. Then press
**Calculate summing only**, or the run button. No standard calibration is
needed. Parent and continuation decay records stay together, and workers run
in separate processes and private folders.

The table shows the summing factor *C*, where *A*<sub>corrected</sub> = *C* · *A*.
A factor below 1 is allowed, for summing-in. It also shows **u(C)** (see
below) and an asterisk `*` for lines without a usable factor.

* **Asterisk.** `*` means not computed, missing, invalid or blocked by a
  numerical check; hover over it for the reason.
* **Matching.** Library lines are matched to the calculated factors by
  nuclide, in standard spelling ("Co60" = "CO-60"), and by energy within
  1 keV.
* **Export.** A line without a usable factor is exported with its original
  abundance or rate. An ambiguous match (two different factors equally close)
  blocks the export.
* **Interpretation.** The factors use the original integer-keV bins. A
  positive factor alone is not a physical validation.

**Wells.** WEFFTRAN calculates the local coincident counts throughout the
sample, including material above the crystal. It then forms a ratio of the
integrated counts.

* **Convergence.** The result is checked twice, with twice as many directions
  and with twice as many sample points. Both checks must change the factors
  by less than 1 %.
* **Blocked export.** Failed convergence or probability saturation blocks the
  Genie export, and so do unsupported annihilation-pair sum-in channels.
* **Unusable decay data.** If a nuclide's decay data cannot be used (for
  example inconsistent conversion coefficients), it is reported as not
  corrected and its lines are exported unchanged. All other nuclides are
  calculated normally.

Details: [WELL_SPATIAL_MODEL.md](WELL_SPATIAL_MODEL.md).

### Uncertainty of the summing factors, u(C)

The original EFFTRAN, MEFFTRAN and WEFFTRAN give no uncertainty for *C*.
EffSuite adds the relative standard uncertainty **u(C)** (k = 1, percent). It
appears in the table and in `summing.csv`, `results.json` and `report.html`.

* **Method.** It is propagated from the uncertainties of the peak and total
  efficiencies that the detector model computes. The sensitivity coefficients
  come from rerunning the unchanged engine with each efficiency curve scaled
  by ±2 %.
* **Numerical part.** The engine's own numerical uncertainty is added: Monte
  Carlo statistics for cylinder and Marinelli, quadrature refinement for
  wells.

Set the inputs in the **TCS uncertainty inputs** row above the table:

| Input | Default | Meaning |
|---|---|---|
| u(ε peak) | 5 % | relative standard uncertainty of the computed peak efficiency |
| u(ε total) | 10 % | relative standard uncertainty of the computed total efficiency |
| correlation | 0 | correlation between the two errors (−1 to 1) |

**The defaults are assumptions. Enter values that describe your own detector
model.**

* **Calculate u(C)** (check box) switches the calculation on or off; the
  factors are the same either way.
* Changing these inputs after a calculation updates the u(C) column,
  and the factors and the transferred efficiencies stay on screen. The result
  folder keeps the values of the last run, so run again to save the new ones.
* Decay-data uncertainties are not included.
* The exported `.NLB` / `.CTF` / `.LIB` files do not carry u(C), so add it to
  your activity budget yourself.

[TCS_UNCERTAINTY.md](TCS_UNCERTAINTY.md) explains the method, how to choose
the inputs, and the limitations.

## 5. Results, projects and recovery

Each calculation creates a new result folder:

| File | Contents |
|---|---|
| `results.json` | the complete result: all values, warnings, settings, and SHA-256 hashes of programs, data and inputs |
| `efficiency.csv` | energy, standard and sample efficiency, transfer factor, transfer uncertainty |
| `summing.csv` | nuclide, energy, factor *C*, status, u(C) and its components (`tcs_*` columns; an empty cell means no uncertainty is available) |
| `report.html` | self-contained report that opens offline |
| exported files | corrected Genie / GammaVision files (section 6) |

The folder also holds the native logs and a snapshot of the inputs used. A
cancelled or failed calculation publishes no result folder.

**Projects.** A saved project (`*.effsuite.json`) contains the detector and
source values, the calibration, the nuclides and the u(C) inputs. It can be
re-run without the GUI:

```bat
CLI.bat run your_project.effsuite.json --out your_new_result_folder
```

Genie templates and a custom data folder are stored as paths, so keep those
files when moving a project to another PC.

**User folder.** Chosen on first start, in this order:

1. `C:\GENIE2K\EffSuite` if it already exists, or if Genie 2000 is installed
   (`C:\GENIE2K` exists). EffSuite never creates `C:\GENIE2K` itself.
2. `Documents\EffSuite`. When Documents is synchronised by OneDrive and this
   folder does not exist yet, or Documents cannot be written,
   `%USERPROFILE%\EffSuite` is used instead, so engine runs are not disturbed
   by cloud synchronisation.
3. `%LOCALAPPDATA%\EffSuite`, then the temp folder, if the folders above
   cannot be written.

The `EFFSUITE_ROOT` environment variable overrides this choice. **Help →
About EffSuite** shows the folder in use.

| Folder | Contents |
|---|---|
| Data | your data folder, default location for all inputs: Calibration, Composition, Detector, Material, Sample, Standard, NuclideLibrary, Certificates |
| Projects | default Save/Open project location |
| Results | one new folder per calculation |
| Export | default CSV/Genie export location |
| Recovery | `last_project.json`, saved before each calculation |
| Logs | GUI start-up error log (`gui_startup.log`) |

**Your data folder.** Only the original EFFTRAN / MEFFTRAN materials are
bundled; your own materials (`Composition`, `Material`) and models
(`Detector`, `Sample`, `Standard`) go in your data folder. Change it for every
session with **Tools → Default data folder…** (or `CLI.bat config --data-dir
<folder>`); **Data folder…** in the top bar changes it for the current
project only. The top bar shows the folder in use. See
[MATERIALS.md](MATERIALS.md#where-materials-are-stored).

**Recovery.** After a crash, open `Recovery\last_project.json` with
**Open project…**. It holds the inputs of the last calculation; it is not a
continuous autosave. Save your project before loading another example or
changing the geometry.

## 6. Genie 2000 and GammaVision export

### Genie 2000

Genie `.CAL` import/export and `.NLB` / `.CTF` processing need Windows with
the Genie CAM components registered. EffSuite tries the installed 32-bit and
64-bit COM hosts.

* **Safe export.** The source file is never changed. The export writes a
  private copy, saves it, reopens it and checks every value, then publishes
  it under a new name (one PowerShell start per export). Existing files are
  never overwritten.
* **In the GUI.** The calculation itself exports the corrected files into its
  result folder. The **Export** buttons then copy that verified file to
  the place you choose.
* **`.CAL` template.** A `.CAL` export needs a vendor `.CAL` template with
  the same number of points as the transferred calibration. A `.CAL` imported
  as the reference supplies it; for a text/CSV calibration the GUI asks for
  one.
* **Corrected values.** Each abundance or rate is divided by *C*. The
  displayed correction multiplies the activity. A line without a usable
  factor keeps its original value. An ambiguous factor or a failed well model
  stops the export.

```bat
CLI.bat cylinder --detector my_detector.txt --sample my_sample.txt --standard my_standard.txt --calibration reference.CAL --export-cal
CLI.bat cylinder --detector my_detector.txt --sample my_sample.txt --library original.NLB --certificate original.CTF
```

`--output-cal`, `--output-nlb` and `--output-ctf` copy the verified file to
a new path, and report an error when that file could not be produced.

### GammaVision (untested)

> **GammaVision support is untested.** It has been implemented as EFFTRAN
> does it, but I cannot test it because I do not have the software.
> Volunteers are welcome to test it and give feedback.

GammaVision files are handled in pure Python, with no vendor components and on
any OS:

- **Library (`.LIB`).** Nuclide, energy and gamma yield are read. On export
  each yield is divided by *C*; lines without a match within 1 keV keep their
  yield. A `<name>_gv.txt` report (energy, old yield, new yield, factor,
  applied flag) is written beside the output, like EFFTRAN `gv.txt`.
- **Efficiency (`.EFT`).** Efficiency and uncertainty are read (EFFTRAN or
  MEFFTRAN layout). The export rewrites a template `.EFT` with the same
  number of points, keeping the other columns and the trailer lines.
- **Selection.** The software is chosen from the extension (`.LIB`, `.EFT` =
  GammaVision). Override it with the GUI **Software** selector,
  `--software genie|gammavision`, or the `EFFSUITE_SOFTWARE` environment
  variable.
- **Genie-only files.** Certificates (`.CTF`) and `.CAL` files are Genie
  only.

```bat
CLI.bat cylinder --detector d.txt --sample s.txt --standard st.txt --calibration ref.EFT --export-cal --library nuclides.LIB --software gammavision
```

## 7. Materials

The Material Editor window, the editable Excel workbook and `CLI.bat material` are
described in [MATERIALS.md](MATERIALS.md). Open the window with
**Materials…** on the Detector or Standard & Sample page, with
**Tools → Material Editor…**, or with **Edit** next to a material field. It
does not block the main window. **Apply: create material and XCOM table**
creates the material and updates
the material lists. Generated data folders can be used
for efficiency transfer and summing in all three applications. A density
change alone needs no new material: edit `Source density [g/cm³]`.

## 8. Reproducing an original EFFTRAN / MEFFTRAN / WEFFTRAN case

1. Choose the matching **Geometry**. Load the original detector file in
   **Detector**, and the original standard and sample files in **Standard & Sample**.
   Cylinder, Marinelli and well formats differ and are checked separately.
2. Select your original installation's data folder with **Data folder…**
   (it then comes before your default data folder and the bundled originals),
   so that the same materials and decay data are used. The material lists
   update, and the result records the data hashes.
3. Import the same calibration and run.

Expected differences from the originals, such as the well model, output
precision and density handling, are listed in
[CHANGES_FROM_ORIGINALS.md](CHANGES_FROM_ORIGINALS.md).

## More information

* Command line and integration with other software:
  [CLI_INTEGRATION_GUIDE.md](CLI_INTEGRATION_GUIDE.md)
* Validation status: [VALIDATION.md](VALIDATION.md)
* All documents: [docs/README.md](README.md)

Real Genie CAM operation on your own PCs, Windows packaging and your
laboratory's physical cases remain release checks. This evaluation build does
not authorise routine use.
