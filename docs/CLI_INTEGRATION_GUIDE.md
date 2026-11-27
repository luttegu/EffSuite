# EffSuite CLI Integration Guide

How to call the **EffSuite Command-Line Interface (CLI)** from other programs (such as C#, Python, C++, Java, MATLAB, shell scripts, or laboratory LIMS).

---

## 1. Overview and executable location

`EffSuite_CLI.exe` is a standalone console program that runs the efficiency transfer and true coincidence summing calculations without the GUI.

### Typical executable paths
- **Installed with the Inno Setup installer (per-user default)**:
  `%LOCALAPPDATA%\Programs\EffSuite\EffSuite_CLI.exe`
- **Installed on a Genie 2000 workstation**:
  `C:\GENIE2K\EffSuite\EffSuite_CLI.exe`
- **Standalone build**:
  `C:\PGM\EffSuite\dist\EffSuite\EffSuite_CLI.exe`
- **From Python (installed package or virtual environment)**:
  `python -m effsuite.app_cli`

---

## 2. Exit codes

When you run `EffSuite_CLI.exe` as a subprocess, check its exit code:

| Exit code | Meaning | How to handle it |
| :---: | :--- | :--- |
| **0** | **Success** | The calculation finished and every reported summing line has a valid correction factor. |
| **1** | **Success with uncorrected lines** | The calculation finished and the results were published, but at least one reported line has no usable factor and is marked `*` (`status` other than `candidate` in `summing.csv`). Typical causes: no decay data for the nuclide, lines the engine does not calculate (for example I-129 X-rays), or, for wells, a failed convergence check (which also blocks the corrected-library export). Exported files keep the original value for those lines. **Treat as success if the expected output files exist.** |
| **2** | **Error** | Invalid input, missing file or engine, or engine failure. The message is on `stderr`. No result folder is published. |
| **130** | **Interrupted** | Ctrl+C. |

> **Integration rule**: accept `ExitCode == 0 || (ExitCode == 1 && File.Exists(expectedOutput))`. Do not treat exit code 1 as a crash, but review the `*` lines in `summing.csv` or `results.json`.

---

## 3. Invocation modes

### Mode A: Geometry subcommands with options (recommended for external software)

Call the specific geometry subcommand (`cylinder` / `efftran`, `marinelli` / `mefftran`, `well` / `wefftran`). All parameters can be passed directly as arguments:

#### 1. Cylindrical geometry (`cylinder` / `efftran`)
```bash
EffSuite_CLI.exe cylinder ^
  --detector "High-energy" ^
  --standard "Solution" ^
  --sample "Water" ^
  --sample-height 55.0 ^
  --sample-density 1.000 ^
  --sample-material "water" ^
  --calibration "C:\GENIE2K\CAMFILES\Standard.CAL" ^
  --library "C:\GENIE2K\CAMFILES\LIBRARY.NLB" ^
  --output-cal "C:\Calculations\Job123\Sample_transferred.CAL" ^
  --output-nlb "C:\Calculations\Job123\Sample_corrected.NLB" ^
  --out "C:\Calculations\Job123\Results" ^
  --workers 4
```

#### 2. Marinelli beaker geometry (`marinelli` / `mefftran`)
```bash
EffSuite_CLI.exe marinelli ^
  --detector "High-energy" ^
  --sample "Sample" ^
  --standard "Standard" ^
  --sample-height 75.0 ^
  --sample-density 1.000 ^
  --sample-material "water" ^
  --calibration "C:\GENIE2K\CAMFILES\Standard_Marinelli.CAL" ^
  --library "C:\GENIE2K\CAMFILES\GammaLab.NLB" ^
  --output-cal "C:\Calculations\Job124\Marinelli_transferred.CAL" ^
  --output-nlb "C:\Calculations\Job124\Marinelli_corrected.NLB" ^
  --out "C:\Calculations\Job124\Results" ^
  --workers 4
```

#### 3. Well-type detector geometry (`well` / `wefftran`)
```bash
EffSuite_CLI.exe well ^
  --detector "well" ^
  --sample "Sample" ^
  --standard "Standard" ^
  --sample-height 32.50 ^
  --sample-density 1.000 ^
  --calibration "C:\GENIE2K\CAMFILES\Well_Standard.CAL" ^
  --library "C:\GENIE2K\CAMFILES\LIBRARY.NLB" ^
  --output-cal "C:\Calculations\Job125\Well_transferred.CAL" ^
  --output-nlb "C:\Calculations\Job125\Well_corrected.NLB" ^
  --out "C:\Calculations\Job125\Results" ^
  --workers 4
```

#### 4. GammaVision (`.EFT` efficiency + `.LIB` nuclide library, *untested*)
> **GammaVision Notice:** GammaVision support has been implemented as EFFTRAN is doing it, but I cannot test it because I do not have the software. Volunteers are welcome to test and provide feedback.
```bash
EffSuite_CLI.exe cylinder ^
  --detector "High-energy" ^
  --standard "Solution" ^
  --sample "Water" ^
  --sample-height 55.0 ^
  --sample-density 1.000 ^
  --calibration "C:\Data\EFFTRAN.EFT" ^
  --library "C:\Data\EFFTRAN.Lib" ^
  --output-cal "C:\Calculations\Job126\Sample_transferred.EFT" ^
  --output-nlb "C:\Calculations\Job126\Sample_corrected.LIB" ^
  --out "C:\Calculations\Job126\Results" ^
  --software gammavision
```

---

### Mode B: Re-running a project file (`run`)

If a workflow is saved from the GUI (or generated programmatically as JSON), execute it directly with optional inline overrides:

```bash
EffSuite_CLI.exe run "C:\Projects\Sample_207724.effsuite.json" ^
  --out "C:\Calculations\Job126\Results" ^
  --output-cal "C:\Calculations\Job126\Transferred.CAL" ^
  --output-nlb "C:\Calculations\Job126\Corrected.NLB" ^
  --workers 4
```

---

### Mode C: Self-test (`doctor`)

To verify the installation, engine binaries, and dependencies from your calling application:

```bash
EffSuite_CLI.exe doctor
```

Prints a machine-readable JSON object. The exit code is 0 when every engine program, XCOM and the required Python packages (NumPy, Matplotlib, xlrd) are present, otherwise 1:
```json
{
  "version": "0.5.4",
  "python": "3.14.10 (...)",
  "interpreter": "C:\\...\\python.exe",
  "dependencies": { "numpy": true, "matplotlib": true, "xlrd": true, "PySide6": true },
  "engines": {
    "EFFTRAN": { "mine": true, "energy": true, "total": true, "scatter": true, "buildup": true, "eta": true, "ptt": true, "efficiency": true, "transfer": true, "coincidence": true },
    "MEFFTRAN": { "...": "same keys as EFFTRAN" },
    "WEFFTRAN": { "...": "same keys, without coincidence" }
  },
  "materials": { "xcom": true, "excel_template": true, "element_data": true },
  "qualification": "Beta Build; experimental qualification pending. Verify installation against reference data"
}
```

### Other commands

| Command | Purpose |
| :--- | :--- |
| `batch jobs.csv --out DIR` | Run every job of a CSV/JSON table (`batch --template jobs.csv` writes an empty template); writes `batch_summary.csv/.json`. |
| `examples [--run cylinder\|marinelli\|well]` | List or run the built-in example projects. |
| `models cylinder\|marinelli\|well` | List the available detector, sample, standard and material names. |
| `plot-geometry --geometry … --detector … --sample … --out FILE` | Draw the dimensioned cross-section (PNG/PDF/SVG). |
| `material …` | Create a material and its XCOM attenuation table (see [MATERIALS.md](MATERIALS.md)). |
| `config [--data-dir DIR \| --reset-data-dir]` | Show the data folders in use, or save / reset the default data folder (your own materials and models). The `EFFSUITE_DATA` environment variable takes precedence. |
| `check-update` | Report whether a newer release is on GitHub, with its release page and installer URL. Exit code 0 when the check worked (up to date or newer release found), 2 when GitHub could not be reached. Installs nothing. |
| `gui` | Open the desktop interface. |

Run any command with `--help` for its full option list.

---

## 4. Parameter reference

| Argument | Type / Format | Description |
| :--- | :--- | :--- |
| `--data-dir` | String (path) | Data folder for this run (materials and models); searched before your default data folder (see `config`) and the bundled originals. |
| `--detector` | String (path or name) | Detector model file path (`.txt`) or name matching a file in `Data/Detector`. |
| `--sample` | String (path or name) | Sample geometry file path (`.txt`) or name in `Data/Sample` or `Data/Standard`. |
| `--standard` | String (path or name) | Standard reference geometry file path (`.txt`) or name in `Data/Standard`. Needed, together with `--calibration`, for an efficiency transfer. |
| `--calibration` | String (path) | Reference efficiency calibration file (Genie `.CAL`, GammaVision `.EFT`, `.txt`, or `.csv`). |
| `--library` | String (path) | Genie 2000 Nuclide Library (`.NLB`) or GammaVision library (`.LIB`) to apply cascade summing corrections to. |
| `--software` | `genie` \| `gammavision` | Force the vendor backend. Default: auto-detect from the extension (`.LIB`/`.EFT` = GammaVision). **GammaVision is untested** (see README). |
| `--certificate` | String (path) | Genie 2000 Certificate File (`.CTF`) to apply cascade summing corrections to. |
| `--nuclides` | Space- or comma-separated | Specific nuclides to calculate (e.g. `--nuclides "Co-60,Cs-134,Eu-152"`). If omitted, all library nuclides are computed. |
| `--export-cal` | Flag | Export the transferred sample calibration (Genie `.CAL` or GammaVision `.EFT`). Automatic when `--calibration` is a `.CAL` / `.EFT` file. |
| `--cal-template` | String (path) | Genie `.CAL` or GammaVision `.EFT` template, needed to export when `--calibration` is a `.txt` / `.csv` file. |
| `--output-cal` | String (path) | Target file path for the transferred sample calibration (Genie `.CAL` or GammaVision `.EFT`). |
| `--output-nlb` | String (path) | Target file path for the summing-corrected nuclide library (Genie `.NLB` or GammaVision `.LIB`). |
| `--output-ctf` | String (path) | Target file path for the summing-corrected Genie certificate (`.CTF`). |
| `--sample-height` | Float (mm) | Overrides the sample filling height [mm]. |
| `--sample-density`| Float (g/cm³) | Overrides the sample bulk density. Sets line 8 of the source model (`rho`); the engines scale the attenuation $\mu(E)$ by $\rho / \rho_0$. `Composition/*.txt` files are not changed. |
| `--sample-material`| String | Overrides the matrix material name (must exist in `Composition` of the `--data-dir`, of your data folder, or among the bundled original materials). |
| `--container-material` | String | Overrides the sample container material name. |
| `--sample-diameter`| Float (mm) | Overrides the outer container diameter [mm]. |
| `--sample-gap` | Float (mm) | Overrides the sample-to-detector positioning gap [mm]. |
| `--out` | String (directory) | Destination directory for audit manifests, tables, and logs. Default: `<user folder>\Results\<timestamp>`, where the user folder is `C:\GENIE2K\EffSuite` when that folder exists or Genie 2000 is installed (`C:\GENIE2K` exists), otherwise `Documents\EffSuite` (`%USERPROFILE%\EffSuite` when Documents is synchronised by OneDrive); `EFFSUITE_ROOT` overrides all of these (see "User folder" in the User Guide). |
| `--save-project` | String (path) | Saves the resolved project JSON, to repeat the run with `run`. |
| `--workers` | Integer | Number of worker processes: `0` = automatic (number of CPUs minus 2, at least 1), `1` = serial single-process. |
| `--plot-geometry`| Flag or file path | Generates a CAD axial cross-section diagram with all dimensions as PNG/PDF. |
| `--verify-serial`| Flag | Cross-verifies parallel outputs against a serial reference run for audit validation. |
| `--tcs-u-peak` | Float (%) | Relative standard uncertainty of the computed peak efficiency, used for u(C). Default 5. Also accepted by `run`. |
| `--tcs-u-total` | Float (%) | Relative standard uncertainty of the computed total efficiency, used for u(C). Default 10. Also accepted by `run`. |
| `--tcs-correlation` | Float (−1 … 1) | Correlation between the peak and total efficiency errors. Default 0. Also accepted by `run`. |
| `--no-tcs-uncertainty` | Flag | Do not calculate u(C); skips the four sensitivity runs. Factors are unchanged. |

In a project JSON, the same settings go in a `"tcs_uncertainty"` object
(`peak_efficiency_percent`, `total_efficiency_percent`,
`peak_total_correlation`, `enabled`, `step_percent`). Command-line options
override the project values. See [TCS_UNCERTAINTY.md](TCS_UNCERTAINTY.md).

---

## 5. Output files

Every exported spectrometry file identifies whether it is for **Genie 2000** (`.CAL`, `.NLB`, `.CTF`) or **GammaVision** (`.EFT`, `.LIB`, plus `<name>_gv.txt`) both by its file extension and inside `results.json` (`"software": "Genie"` or `"GammaVision"`) and `report.html`.

In addition to the destination files specified by `--output-cal` and `--output-nlb`, the directory given to `--out` also contains these files for other programs to read:

1. **`results.json`**:
   Calculation manifest containing:
   - Numerical efficiency transfer values for all calibration points.
   - The summing factor $C$ of every line, with its status.
   - The relative standard uncertainty of each factor, `tcs_u_rel_percent`, with its components and sensitivity coefficients, plus a `tcs_uncertainty` section recording the settings and method.
   - SHA-256 hashes of all engine executables, data files, and inputs.
   - Runtime diagnostics and timings.
2. **`efficiency.csv`**:
   Tabular efficiency transfer factors:
   `energy_keV, standard_efficiency, sample_efficiency, transfer_factor, sample_relative_uncertainty_percent_legacy`
3. **`summing.csv`**:
   Tabular cascade correction factors:
   `nuclide, energy_keV, activity_multiplier, status, tcs_u_rel_percent, tcs_u_peak_percent, tcs_u_total_percent, tcs_u_numerical_percent, tcs_sensitivity_peak, tcs_sensitivity_total`.
   `tcs_u_rel_percent` is u(C) in percent (k = 1). An empty cell means no uncertainty is available (uncorrected line, or `--no-tcs-uncertainty`).
4. **`report.html`**:
   Self-contained HTML report (opens offline) with an embedded SVG chart, the efficiency and summing tables, u(C), and the exported files.

---

## 6. Calling EffSuite from other languages

### C# (.NET / WPF / WinForms)

> **Important**: Always read `StandardOutput` and `StandardError` asynchronously before calling `WaitForExit()` to prevent buffer deadlocks.

```csharp
using System;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;

public class EffSuiteRunner
{
    public static async Task<bool> RunCylinderAnalysisAsync(
        string effSuiteCliPath,
        string detector,
        string standard,
        string sample,
        double sampleHeightMm,
        double sampleDensityGcm3,
        string calibrationCalPath,
        string libraryNlbPath,
        string targetTransferredCal,
        string targetCorrectedNlb,
        string resultDir)
    {
        var arguments = $"cylinder " +
            $"--detector \"{detector}\" " +
            $"--standard \"{standard}\" " +
            $"--sample \"{sample}\" " +
            $"--sample-height {sampleHeightMm.ToString(System.Globalization.CultureInfo.InvariantCulture)} " +
            $"--sample-density {sampleDensityGcm3.ToString(System.Globalization.CultureInfo.InvariantCulture)} " +
            $"--calibration \"{calibrationCalPath}\" " +
            $"--library \"{libraryNlbPath}\" " +
            $"--output-cal \"{targetTransferredCal}\" " +
            $"--output-nlb \"{targetCorrectedNlb}\" " +
            $"--out \"{resultDir}\" " +
            $"--workers 4";

        var psi = new ProcessStartInfo
        {
            FileName = effSuiteCliPath,
            Arguments = arguments,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        using var process = new Process { StartInfo = psi };
        process.Start();

        // Read streams asynchronously to prevent pipe deadlocks
        var stdOutTask = process.StandardOutput.ReadToEndAsync();
        var stdErrTask = process.StandardError.ReadToEndAsync();

        await process.WaitForExitAsync();

        string stdout = await stdOutTask;
        string stderr = await stdErrTask;

        int exitCode = process.ExitCode;

        // ExitCode 0: full success
        // ExitCode 1: valid completion with uncorrected low-energy transitions
        bool isSuccess = (exitCode == 0 || (exitCode == 1 && File.Exists(targetTransferredCal)));

        if (!isSuccess)
        {
            throw new Exception($"EffSuite calculation failed (Exit Code {exitCode}): {stderr}");
        }

        return true;
    }
}
```

---

### Python

```python
import subprocess
from pathlib import Path

def run_effsuite_cylinder(
    cli_path: str,
    detector: str,
    standard: str,
    sample: str,
    height_mm: float,
    density_gcm3: float,
    cal_file: str,
    nlb_file: str,
    output_cal: str,
    output_nlb: str,
    result_dir: str
) -> bool:
    cmd = [
        cli_path, "cylinder",
        "--detector", detector,
        "--standard", standard,
        "--sample", sample,
        "--sample-height", str(height_mm),
        "--sample-density", str(density_gcm3),
        "--calibration", cal_file,
        "--library", nlb_file,
        "--output-cal", output_cal,
        "--output-nlb", output_nlb,
        "--out", result_dir,
        "--workers", "4"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )

    # Accept exit code 0 or 1 if output file exists
    if result.returncode == 0 or (result.returncode == 1 and Path(output_cal).is_file()):
        return True
    
    raise RuntimeError(
        f"EffSuite execution failed (Exit code {result.returncode}):\n{result.stderr}"
    )
```

---

### Windows Batch / PowerShell

#### PowerShell
```powershell
$cli = "C:\GENIE2K\EffSuite\EffSuite_CLI.exe"
$outCal = "C:\Data\Output\Sample.CAL"
$outNlb = "C:\Data\Output\Corrected.NLB"

& $cli cylinder `
  --detector "High-energy" `
  --sample "Water" `
  --standard "Solution" `
  --sample-height 55.0 `
  --sample-density 1.000 `
  --calibration "C:\Data\Standard.CAL" `
  --library "C:\Data\Master.NLB" `
  --output-cal $outCal `
  --output-nlb $outNlb `
  --out "C:\Data\Results" `
  --workers 4

if ($LASTEXITCODE -eq 0 -or ($LASTEXITCODE -eq 1 -and (Test-Path $outCal))) {
    Write-Host "EffSuite calculation completed successfully." -ForegroundColor Green
} else {
    Write-Error "EffSuite failed with exit code $LASTEXITCODE"
}
```

---

## 7. Troubleshooting

1. **Paths with spaces**:
   Always wrap file paths containing spaces in double quotes when invoking via shell strings. When using structured process APIs (`ProcessStartInfo.ArgumentList` or Python `subprocess.run(list)`), quoting is handled automatically.
2. **Matrix density and new materials**:
   `--sample-density` needs no new attenuation table: the engines scale the material's table by $\rho / \rho_0$. A new *composition* needs a material: when a material named in a model has a `Composition/<name>.txt` but no `Material/<name>.txt`, EffSuite runs the bundled XCOM automatically and saves the table in the data folder. Use the `material` command to create one in advance.
3. **Parallel workers**:
   On multi-core lab workstations, use `--workers 4` or `--workers 0` (automatic). If executing multiple independent sample calculations in parallel from an external scheduler, use `--workers 1` per instance to prevent CPU oversubscription.
4. **CAM file locks**:
   Ensure that the target `.CAL` and `.NLB` destination files are not opened with exclusive write locks in Genie 2000 Gamma Acquisition & Analysis while EffSuite is writing to them.
5. **Memory**:
   A CLI run commits about 90–100 MB of memory. It sets `OPENBLAS_NUM_THREADS=1` at start, because numpy's OpenBLAS would otherwise reserve about 30 MB of committed memory per CPU thread (about 750 MB on a 24-thread PC). A value already set in the environment is kept.
