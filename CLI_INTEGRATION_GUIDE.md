# EffSuite CLI Integration Guide

A complete guide for integrating and invoking the **EffSuite Command-Line Interface (CLI)** from external applications (such as C#, Python, C++, Java, MATLAB, shell scripts, or laboratory LIMS).

---

## 1. Overview & Executable Location

EffSuite provides a standalone, high-performance console executable (`EffSuite_CLI.exe`) that executes efficiency transfer and true coincidence summing calculations headlessly without requiring GUI interaction.

### Typical Executable Paths
- **Installed via Inno Setup (Default User Install)**:
  `%LOCALAPPDATA%\Programs\EffSuite\EffSuite_CLI.exe`
- **Genie 2000 Integration Directory**:
  `C:\GENIE2K\EffSuite\EffSuite_CLI.exe`
- **Development / Standalone Build**:
  `C:\PGM\EffSuite\dist\EffSuite\EffSuite_CLI.exe`
- **Python Package / Virtual Environment**:
  `python -m effsuite.app_cli`

---

## 2. Process Exit Codes & Return Status

When executing `EffSuite_CLI.exe` as a subprocess, evaluate the process exit code:

| Exit Code | Meaning | Software Handling Recommendation |
| :---: | :--- | :--- |
| **0** | **Success (Complete)** | All calculations completed successfully. All library gamma lines received positive summing corrections. |
| **1** | **Success (Valid with Uncorrected Lines)** | Valid completion. The transferred `.CAL` / `.EFT` and corrected `.NLB` / `.LIB` / `.CTF` were created and verified. However, certain low-energy lines below the detector/calibration operational limit (e.g., transitions < 40 keV) could not receive summing corrections and are marked with `*` (standard GenTran / EFFTRAN convention). **Treat as success if expected output files exist.** |
| **2** | **Fatal Execution Error** | Runtime failure (e.g., missing engine binary, file I/O error, invalid syntax, or unhandled exception). Inspect `stderr` for details. |
| **>2** | **OS / Subprocess Abort** | Abnormal termination (e.g., process killed by timeout, permission failure). |

> **Critical Integration Rule**: External software should check if `ExitCode == 0 || (ExitCode == 1 && File.Exists(expectedOutputCal))`. Do not treat exit code 1 as a crash.

---

## 3. Invocation Modes & Command Syntax

### Mode A: Direct Parametric Invocations (Recommended for External Software)

Call the specific geometry subcommand (`cylinder` / `efftran`, `marinelli` / `mefftran`, `well` / `wefftran`). All parameters can be passed directly as arguments:

#### 1. Cylindrical Geometry (`cylinder` / `efftran`)
```bash
EffSuite_CLI.exe cylinder ^
  --detector "High-energy" ^
  --standard "Solution" ^
  --sample "Water" ^
  --sample-height 55.0 ^
  --sample-density 1.000 ^
  --sample-material "water" ^
  --calibration "C:\GENIE2K\CAMFILES\Standard.CAL" ^
  --library "C:\GENIE2K\CAMFILES\NUTECH.NLB" ^
  --output-cal "C:\Calculations\Job123\Sample_transferred.CAL" ^
  --output-nlb "C:\Calculations\Job123\Sample_corrected.NLB" ^
  --out "C:\Calculations\Job123\Results" ^
  --workers 4
```

#### 2. Marinelli Beaker Geometry (`marinelli` / `mefftran`)
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

#### 3. Well-Type Detector Geometry (`well` / `wefftran`)
```bash
EffSuite_CLI.exe well ^
  --detector "well" ^
  --sample "Sample" ^
  --standard "Standard" ^
  --sample-height 32.50 ^
  --sample-density 1.000 ^
  --calibration "C:\GENIE2K\CAMFILES\Well_Standard.CAL" ^
  --library "C:\GENIE2K\CAMFILES\NUTECH.NLB" ^
  --output-cal "C:\Calculations\Job125\Well_transferred.CAL" ^
  --output-nlb "C:\Calculations\Job125\Well_corrected.NLB" ^
  --out "C:\Calculations\Job125\Results" ^
  --workers 4
```

#### 4. GammaVision Invocation (`.EFT` Efficiency + `.LIB` Nuclide Library — *Untested*)
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

### Mode B: Project File Replay (`run`)

If a workflow is saved from the GUI (or generated programmatically as JSON), execute it directly with optional inline overrides:

```bash
EffSuite_CLI.exe run "C:\Projects\Sample_207724.effsuite.json" ^
  --out "C:\Calculations\Job126\Results" ^
  --output-cal "C:\Calculations\Job126\Transferred.CAL" ^
  --output-nlb "C:\Calculations\Job126\Corrected.NLB" ^
  --workers 4
```

---

### Mode C: Diagnostic & Self-Test (`doctor`)

To verify the installation, engine binaries, and dependencies from your calling application:

```bash
EffSuite_CLI.exe doctor
```

Returns exit code 0 and prints a machine-readable JSON object:
```json
{
  "version": "0.1.4",
  "dependencies": {
    "numpy": true,
    "matplotlib": true,
    "xlrd": true,
    "PySide6": true
  },
  "engines": {
    "EFFTRAN": { "mine": true, "energy": true, "total": true, "efficiency": true, "coincidence": true, ... },
    "MEFFTRAN": { ... },
    "WEFFTRAN": { ... }
  },
  "qualification": "Beta Build (Experimental Qualification Pending)"
}
```

---

## 4. Parameter Reference Table

| Argument | Type / Format | Description |
| :--- | :--- | :--- |
| `--detector` | String (path or name) | Detector model file path (`.txt`) or name matching a file in `Data/Detector`. |
| `--sample` | String (path or name) | Sample geometry file path (`.txt`) or name in `Data/Sample`. |
| `--standard` | String (path or name) | Standard reference geometry file path (`.txt`) or name in `Data/Standard`. Defaults to `--sample` if omitted. |
| `--calibration` | String (path) | Reference efficiency calibration file (Genie `.CAL`, GammaVision `.EFT`, `.txt`, or `.csv`). |
| `--library` | String (path) | Genie 2000 Nuclide Library (`.NLB`) or GammaVision library (`.LIB`) to apply cascade summing corrections to. |
| `--software` | `genie` \| `gammavision` | Force the vendor backend. Default: auto-detect from the extension (`.LIB`/`.EFT` = GammaVision). **GammaVision is untested** (see README). |
| `--certificate` | String (path) | Genie 2000 Certificate File (`.CTF`) to apply cascade summing corrections to. |
| `--nuclides` | Space- or comma-separated | Specific nuclides to calculate (e.g. `--nuclides "Co-60,Cs-134,Eu-152"`). If omitted, all library nuclides are computed. |
| `--output-cal` | String (path) | Target file path for the transferred sample calibration (Genie `.CAL` or GammaVision `.EFT`). |
| `--output-nlb` | String (path) | Target file path for the summing-corrected nuclide library (Genie `.NLB` or GammaVision `.LIB`). |
| `--output-ctf` | String (path) | Target file path for the summing-corrected Genie certificate (`.CTF`). |
| `--sample-height` | Float (mm) | **Dynamic override**: Sample filling height in mm. |
| `--sample-density`| Float (g/cm³) | **Dynamic override**: Sample bulk density (sets the 8th source parameter `rho`, scaling sample attenuation $\mu(E)$ by $\rho / \rho_0$ across EFFTRAN 4.9, MEFFTRAN 1.8, and WEFFTRAN without mutating global `Composition/*.txt` files). |
| `--sample-material`| String | **Dynamic override**: Matrix material name (must exist in `Data/Composition` or `assets/common/Composition`). |
| `--sample-diameter`| Float (mm) | **Dynamic override**: Outer container diameter in mm. |
| `--sample-gap` | Float (mm) | **Dynamic override**: Endcap/crystal-to-container face distance in mm. |
| `--out` | String (directory) | Destination directory for audit manifests, tables, and logs. Default: `Documents/EffSuite/Results/<timestamp>`. |
| `--workers` | Integer | Number of worker processes: `0` = automatic (CPU core count up to 4), `1` = serial single-process. |
| `--plot-geometry`| Flag or file path | Generates a CAD axial cross-section diagram with all quotes as PNG/PDF. |
| `--verify-serial`| Flag | Cross-verifies parallel outputs against a serial reference run for audit validation. |

---

## 5. Output Files & Formats

Every exported spectrometry file explicitly identifies whether it is for **Genie 2000** (`.CAL`, `.NLB`, `.CTF`) or **GammaVision** (`.EFT`, `.LIB`, plus `<name>_gv.txt`) both by its file extension and inside `results.json` (`"software": "Genie"` or `"GammaVision"`) and `report.html`.

In addition to the destination files specified by `--output-cal` and `--output-nlb`, the directory given to `--out` contains structured outputs for programmatic ingestion:

1. **`results.json`**:
   Comprehensive calculation manifest containing:
   - Numerical efficiency transfer values for all calibration points.
   - Exact summing factors $C$ with cascade component breakdowns.
   - SHA-256 cryptographic hashes of all engine executables, data files, and inputs.
   - Complete runtime diagnostics and timings.
2. **`efficiency.csv`**:
   Tabular efficiency transfer factors:
   `Energy_keV, Reference_Efficiency, Transferred_Efficiency, Transfer_Factor, Uncertainty_Percent`
3. **`summing.csv`**:
   Tabular cascade correction factors:
   `Nuclide, Energy_keV, Summing_Factor_C, Comment` (Comment is `*` for uncomputed/low-energy transitions).
4. **`report.html`**:
   Self-contained interactive HTML audit report with embedded SVG efficiency curves.

---

## 6. Code Examples for Calling from Other Languages

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

## 7. Troubleshooting & Best Practices

1. **Path Spacing**:
   Always wrap file paths containing spaces in double quotes when invoking via shell strings. When using structured process APIs (`ProcessStartInfo.ArgumentList` or Python `subprocess.run(list)`), quoting is handled automatically.
2. **Dynamic Matrix Density**:
   When overriding `--sample-density` with a custom density (e.g. `1.346`), EffSuite automatically checks if an XCOM cross-section file matching that density exists in `Data/Material/`. If not, it invokes the built-in NIST XCOM photon engine automatically on-the-fly. No manual pre-generation step is required.
3. **Parallel Worker Allocation**:
   For maximum efficiency on multi-core lab workstations, specify `--workers 4` or `--workers 0` (automatic). If executing multiple independent sample calculations in parallel from an external scheduler, use `--workers 1` per instance to prevent CPU oversubscription.
4. **CAM File Locks**:
   Ensure that the target `.CAL` and `.NLB` destination files are not opened with exclusive write locks in Genie 2000 Gamma Acquisition & Analysis while EffSuite is writing to them.
