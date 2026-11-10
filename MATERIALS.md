# Material composition — EffSuite v0.1.3

The original Material.xls takes up to ten chemical formulas, relative weights
and a separately entered bulk density. Its Save action runs XCOM to create a
mass-attenuation table, then stores the density/composition text. EffSuite now
implements that complete workflow through one shared GUI/CLI service.

Starting with **EffSuite v0.1.3** (integrating `EFFTRAN 4.9` and `MEFFTRAN 1.8` and extending the feature to `WEFFTRAN`), you only need to generate a new XCOM material when the **chemical composition** changes. If you only need to change the **bulk density** of an existing sample matrix (such as soil or aqueous solution at a different packing density), simply enter the new `Source density [g/cm³]` directly in the **Source** tab (or on line 8 of the source `.txt` file, or via `--sample-density` in the CLI); the engine scales the linear attenuation coefficient $\mu(E)$ by $\rho / \rho_0$ automatically.

## GUI

Open **Material**. Enter a new material name, density in g/cm³, and formulas
such as H2O, NaCl, SiO2 or CaO with relative weights. The normalized mass
fractions are displayed beside the inputs. Choose the output data folder and
press **Create Material and Attenuation Table**. A new data folder is seeded
from the bundled common materials data or explicitly selected original data.
An existing data folder receives the newly named material without replacing
existing material files. Save a modified material under a new name.

After successful generation, the selected data folder and material lists update.
Choose the new material in the appropriate Detector or Source field. Existing
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
`--base-data` selects the original data directory to copy when creating a new
output library. Composition and material files are common across EFFTRAN,
MEFFTRAN and WEFFTRAN; they share a single common directory (defaulting to
`Documents/EffSuite/Data`).

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
retained. Linux execution and downstream use were checked; Windows XCOM
execution and independent laboratory qualification remain pending.
