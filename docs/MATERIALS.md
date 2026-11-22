# Materials and XCOM — EffSuite v0.3.2

The original Material.xls takes up to ten chemical formulas, relative weights
and a separately entered bulk density. Its Save action runs XCOM to create a
mass-attenuation table, then stores the density/composition text. EffSuite now
implements that complete workflow through one shared GUI/CLI service.

You only need a new material when the **chemical composition** changes. To
change only the **bulk density** of an existing matrix, for example soil or a
solution at another packing density, enter the new `Source density [g/cm³]`:
in the **Standard & Sample** tab, on line 8 of the source `.txt` file, or with
`--sample-density` in the CLI. The engines then scale the attenuation
coefficient $\mu(E)$ by $\rho / \rho_0$, in all three geometries.

When a model names a material that has a `Composition/<name>.txt` but no
`Material/<name>.txt`, EffSuite generates the table with XCOM as soon as a
calculation needs it. The table is saved in your data folder, never in the
program folder.

## Where materials are stored

Only the **original materials of EFFTRAN 5.0 and MEFFTRAN 1.9** are bundled
with the program (20 materials: CLYC, CZT, CsI, Ge, LaBr3, NaI, air,
aluminium, beryllium, cellulose, copper, heavy, iron, lead, plexiglass,
polystyrene, silica, soil, vacuum, water). They are read-only and always
available.

Every other material belongs to the user and is kept in **your data folder**,
in its `Composition` and `Material` subfolders (one `<name>.txt` file in
each). Materials are searched in this order, the first match wins:

1. the project's own data folder (**📁 Data Folder…** in the GUI, `--data-dir` in the CLI);
2. your default data folder;
3. the legacy folder `Documents\EffSuite\Data` (read only, for older installations);
4. the bundled original materials.

A user file with the same name as an original therefore replaces it for that
user. New materials (Material Editor, `CLI.bat material`, automatic XCOM
tables) are saved in the data folder in use, never in the program folder.

**Default data folder.** `<EffSuite user folder>\Data`, that is
`C:\GENIE2K\EffSuite\Data` (or `Documents\EffSuite\Data` when `C:\GENIE2K`
cannot be written). To change it for every session:

- GUI: **Tools → 📁 Default Data Folder…** (**↺ Reset Default Data Folder** goes back);
- CLI: `CLI.bat config --data-dir D:\Lab\EffSuite_Data` (`config` alone shows
  the folders in use, `config --reset-data-dir` goes back).

The choice is saved in `%APPDATA%\EffSuite\settings.json` and used by both the
GUI and the CLI. The `EFFSUITE_DATA` environment variable, when set, takes
precedence (useful for a shared network folder). The `Composition` and
`Material` subfolders are created when the folder is chosen.

Materials that were bundled with EffSuite 0.3.1 and earlier but are not
originals (e.g. `Plastic_vial`, `HeavyWater`, `polyethylene`, the ashed food
matrices) are no longer installed. Copy them from an earlier installation's
`assets\common\Composition` and `Material` folders into your data folder if
your models use them. `HeavyWater` is identical to the original `heavy`.

## GUI

Open the Material Editor with **🧪 Materials…** on the Detector or Sample &
Standard page, with **Tools → Material Editor…**, or with **✏️ Edit** next to a material field
(which loads that material). The editor is a separate window: the Detector and
Standard & Sample pages stay usable while it is open. Enter a new material name, density
in g/cm³, and formulas such as H2O, NaCl, SiO2 or CaO with relative weights.
The normalized mass fractions are displayed beside the inputs. Choose the
output data folder (default: your data folder) and press **✔ Apply**. A new
or empty folder gets `Composition` and `Material` subfolders; the bundled
originals are not copied into it. Replacing an existing material, or using the
name of an original material, asks for confirmation first. Save a modified
material under a new name to keep the original.

After successful generation, the selected data folder and material lists update
at once. When the editor was opened with **✏️ Edit**, the new material is
selected in that field (for a source matrix, its density is filled in too);
otherwise choose it in the appropriate Detector, Sample or Standard field. Existing
calculation results are cleared. **Store Definition JSON** saves an editable
composition; **Load Composition / Excel** accepts that JSON, original
Composition/*.txt, the new workbook, or the original Material.xls layout.

The material draft itself is saved separately from a detector/source project.
Save its JSON before switching application mode. A calculation project records
its selected data-folder path; retain that folder when moving to another PC.

## Excel

`Material_Composition.xlsx` is an editable, macro-free input workbook. The
original cell locations are retained: formulas C9:C18, weights D9:D18, density
D20. The new material name is D4. Normalized percentages are formula results
in column E. Edit input cells as values, save the workbook, then load it in
Material or pass it to the CLI. Excel itself does not run XCOM; the application
performs that step after import. The importer recomputes normalization from
input values, so stale cached formula results cannot change the material.

The new workbook and original `.xls` inputs use the same importer contract.
Formula expressions in input cells of an XLSX are rejected with an instruction
to Paste Values. No workbook macros are executed. The supplied example is H2O,
weight 1, density 1 g/cm³; replace it with your actual inputs.

## CLI

```bat
CLI.bat material --name Salt_water --density 1.05 --compound H2O=90 --compound NaCl=10
CLI.bat material --input Material_Composition.xlsx
CLI.bat material --input my_material.json --library D:\EffSuite_Data
CLI.bat material --input C:\EFFTRAN\Composition\water.txt --name My_water
```

Use `--save-definition my_material.json` to retain direct command-line inputs.
`--density` and `--name` can override a loaded definition explicitly.
`--library` chooses the output data folder (default: your data folder, see
above). `--base-data` copies another data folder (for example an original
EFFTRAN installation) into a new, empty output folder. Composition and
material files are common across EFFTRAN, MEFFTRAN and WEFFTRAN; they share a
single data folder.

Use the resulting data directory in an ordinary calculation:

```bat
CLI.bat cylinder --detector High-energy --sample Water --standard Solution --calibration reference.csv --data-dir D:\EffSuite_Data
CLI.bat well --detector well --sample Sample --nuclides Co60 Cs134 Eu152 --data-dir D:\EffSuite_Data
```

The source model must name the newly created material in the relevant original
material field. Using `--data-dir` alone does not replace a model's selection.

## Input meaning and generated files

| Input | Meaning |
|---|---|
| Compound | Flat XCOM formula with conventional case and integer atom counts |
| Weight | Nonnegative relative mass weight; at least one must be positive |
| Density | Supplied bulk density in g/cm³, strictly positive |

Weights may be fractions, percentages or masses in a common unit. XCOM
normalizes by their sum. These are mass weights, not volume fractions.
Bulk density is not inferred from compound densities. Parenthesized formulas,
isotope labels and named mixtures are not supported by the original XCOM
formula parser; expand the chemical formula, for example CaO2H2 for Ca(OH)2.
Do not silently substitute a formula when chemical identity is uncertain.

Output contains `Composition/<name>.txt`, `Material/<name>.txt` and
`Material_Metadata/<name>.json`. The composition retains the entered weights
and density. The material table contains mass interaction coefficients in
cm²/g, on the original XCOM standard energy grid with absorption edges. The
legacy detector engine reads density from Composition when forming linear
attenuation coefficients. Metadata records input text, XCOM binary/data hashes
and the generated table hash. Generation is isolated in a private directory;
failed generation does not publish a new material pair.

The bundled source is the XCOM 3.1 version supplied with original EFFTRAN,
not a claim to contain the latest NIST dataset. Its source/README notices are
retained. The automated tests run XCOM and use the generated materials on
Windows and Linux; independent laboratory qualification remains pending.
