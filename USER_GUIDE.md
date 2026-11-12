# EffSuite User Guide — v0.1.5

> **Spectrometry Software Compatibility Notice (Genie 2000 & GammaVision):**  
> EffSuite supports **Canberra / Mirion Genie 2000** formats (`.CAL`, `.NLB`, `.CTF`, and `.CNF`) as well as **ORTEC GammaVision** formats (`.EFT` efficiency calibration and `.LIB` nuclide library).  
> **GammaVision Notice (Untested — Volunteers Welcome):** GammaVision support has been implemented exactly as EFFTRAN and MEFFTRAN do it, but I cannot test it because I do not have the software. Volunteers are welcome to test and provide feedback.  
> Other spectrometry formats (such as ORTEC Maestro `.spc` / `.cal` or InterWinner) are **not supported**.

> **WEFFTRAN Qualification Status Notice:**  
> The WEFFTRAN (Well detector) engine has been patched for Fortran ray boundary handling and 3D spatial summing, but is **not yet fully tested or qualified in the laboratory**. Treat all well-type detector outputs as experimental and independently verify all values.

## Reproduce an original EFFTRAN / MEFFTRAN / WEFFTRAN case

Choose the matching application at the top (`EFFTRAN` 4.9, `MEFFTRAN` 1.8, or `WEFFTRAN`). In Detector, load the original
detector text file. In Source, load the original Standard and Sample text
files (7-line legacy models and 8-line models with explicit `Source density [g/cm³]` are both supported; when you change `Source material` in the GUI, `Source density [g/cm³]` automatically fills with the nominal density from `Composition/<material>.txt` and can be freely adjusted). Do not infer dimensions from the model name. Original cylinder,
Marinelli and well formats differ and are checked separately.

Use your original installation's data folder when comparing against its
materials/decay dataset. Select it explicitly with the button above the tabs.
The material lists update to that folder. The result records data hashes.

In Efficiency, import the standard Genie `.CAL`, GammaVision `.EFT`, or a two/three-column text/CSV file:
energy in keV, efficiency as a fraction, optional relative uncertainty in
percent. For example, efficiency 0.05 means 5%; uncertainty 3 means 3% relative.
The calibration must have 2–93 points with strictly increasing energies.
Paste table cells from a spreadsheet into the first three columns if preferred.

Press **Transfer from Standard to Sample**. Inspect transferred values and
the Standard/Sample graph. Save the project. Repeat with:

```bat
CLI.bat run your_project.effsuite.json --out your_new_result_folder
```

The project embeds detector/source values, calibration and nuclides. External
Genie templates and custom data-folder references remain paths; retain those
files when moving a project to another PC. Each result directory includes a
snapshot of the used model/material inputs and native intermediate files.

## Coincidence summing

Open Library, type the nuclides, and select **Calculate selected nuclides**.
The standard calibration is not needed for this task. Alternatively open a
Genie `.NLB` / `.CTF` or a GammaVision `.LIB` library and process its nuclides. Original parent/continuation decay
records stay together. Workers run in separate processes and private folders.

The correction table uses the original integer-keV bins. An asterisk means
not computed, missing, invalid or blocked by a numerical check; hover over it
for the reason. Do not interpret a positive factor alone as physical validation.
Genie matching requires the same nuclide and a unique line within 1 keV;
missing/ambiguous/invalid matches block export.

WEFFTRAN calculates local coincident counts throughout the sample, including
material above the crystal. It then forms a ratio of integrated counts and
checks quadrature refinement. Probability saturation and failed refinement
block Genie export. Unsupported annihilation pair sum-in channels are blocked.

## Files and recovery

The default user folder is `Documents\EffSuite`:

| Folder | Contents |
|---|---|
| Data | Default location for all inputs: Calibration, Composition, Detector, Material, Standard, NuclideLibrary |
| Projects | Default Save/Open project location |
| Results | One new directory per calculation |
| Export | Default CSV/Genie export location |
| Recovery | `last_project.json`, saved before calculation |
| Logs | GUI startup error log |

Recovery currently preserves the last calculation inputs. Open that JSON from
File → Open project after a crash. It is not a continuous keystroke autosave.
A cancelled or failed calculation does not publish a partial result directory.
Save your project before replacing it with another example or changing mode.

The result `results.json` is the canonical report. `efficiency.csv` and
`summing.csv` are convenient comparison tables; `report.html` is self-contained
and can be opened offline. Native logs and input snapshots support investigation.
The legacy uncertainty column preserves the original transfer assumptions.

## Genie export

CAL import/export and NLB/CTF processing need Windows with registered Genie CAM
components. The adapter attempts the installed 32-bit and 64-bit COM hosts.
It resolves numeric CAM identifiers from the registered vendor type library.
The source file is read/copied; export writes a separate destination and checks
it by reopening. Never select an existing filename for Genie output.

A CAL export requires a vendor CAL template with the same point count as the
transferred calibration. A CAL imported as the reference supplies that template.
For text/CSV inputs, the GUI asks for a template. CLI example:

```bat
CLI.bat cylinder --detector my_detector.txt --sample my_sample.txt --standard my_standard.txt --calibration reference.CAL --export-cal
```

Use `--library original.NLB` or `--certificate original.CTF` to calculate its
nuclides and export a corrected copy into the new result directory. Each
abundance/rate is divided by C; the displayed correction multiplies activity.
An unrecognized line stops the export rather than assigning C=1.

Real CAM operation, Windows packaging and your laboratory's physical cases
remain release checks. This evaluation build does not authorize routine use.

## GammaVision export (untested)

> **GammaVision support is untested.** It has been implemented as EFFTRAN is doing it, but I cannot test it because I do not have the software. Volunteers are welcome to test it and provide feedback.

EffSuite 0.1.5 handles ORTEC GammaVision files the way EFFTRAN and MEFFTRAN do, in pure Python (no vendor components, any OS):

- **Library (`.LIB`)**: nuclide, energy and gamma yield are read; on export each yield is divided by the summing
  factor C (lines with no match within 1 keV keep their yield). A `<name>_gv.txt` report (energy, old yield, new yield,
  factor, applied flag) is written beside the output, like EFFTRAN `gv.txt`.
- **Efficiency (`.EFT`)**: efficiency and uncertainty are read (EFFTRAN or MEFFTRAN layout). Export rewrites a template
  `.EFT` with the same number of points, keeping the other columns and trailer lines.
- **Selection**: automatic from the extension (`.LIB`, `.EFT` = GammaVision). Override with the GUI **Software** selector,
  `--software genie|gammavision` in the CLI, or the `EFFSUITE_SOFTWARE` environment variable.
- Certificates (`.CTF`) and `.CAL` files remain Genie-only. As for Genie, never reuse an existing output filename.

```bat
CLI.bat cylinder --detector d.txt --sample s.txt --standard st.txt --calibration ref.EFT --export-cal --library nuclides.LIB --software gammavision
```

## Material creation

The Material tab, editable Excel workbook and `CLI.bat material` are described
in [MATERIALS.md](MATERIALS.md). Generated data folders can be selected for
efficiency transfer and coincidence summing in all three application modes.
