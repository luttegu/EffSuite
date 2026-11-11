# EffSuite — Gamma Spectrometry Efficiency Transfer & Summing Suite

<p align="center">
  <img src="https://img.shields.io/badge/Version-0.1.4-yellow.svg" alt="Version 0.1.4" />
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg" alt="Python Version" />
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20(x64)-0078D6.svg" alt="Windows Platform" />
  <img src="https://img.shields.io/badge/Genie%202000-CAM%20%7C%20CAL%20%7C%20NLB%20%7C%20CTF-8A2BE2.svg" alt="Genie 2000 Integration" />
  <img src="https://img.shields.io/badge/GammaVision-EFT%20%7C%20LIB%20(Untested)-008080.svg" alt="GammaVision Integration (Untested)" />
  <img src="https://img.shields.io/badge/Physics%20Engines-EFFTRAN%204.9%20%7C%20MEFFTRAN%201.8%20%7C%20WEFFTRAN-2ea44f.svg" alt="Physics Engines" />
  <img src="https://img.shields.io/badge/License-GPL--3.0%20%2F%20Vidmar%20Attribution-orange.svg" alt="License" />
</p>

*EffSuite (v0.1.4) built by ChatGPT & Gemini under the supervision of G. Lutter.*

---

> [!WARNING]
> ### ⚠️ Mandatory Scientific Disclaimer & Terms of Use
> **Provided strictly on an AS-IS basis. G. Lutter accepts NO responsibility or liability under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. Users must independently verify all results.**

> [!IMPORTANT]
> ### 📌 File Format & Spectrometry System Compatibility (Genie 2000 & GammaVision)
> EffSuite clearly distinguishes **Canberra / Mirion Genie 2000** files from **ORTEC GammaVision** files by extension and explicit software labels in the GUI, CLI, and exported reports:
> - **Canberra / Mirion Genie 2000**:
>   - **`.CAL`**: Efficiency Calibration Files (imported & exported as `*_sample.CAL` / `*_corrected.CAL`)
>   - **`.NLB`**: Nuclide Library Files (binary, exported as `*_corrected.NLB`)
>   - **`.CTF`**: Certificate / Source Files (exported as `*_corrected.CTF`)
>   - **`.CNF`**: CAM Spectral Files
> - **ORTEC GammaVision** *(implemented as in EFFTRAN/MEFFTRAN — **untested**, volunteers welcome)*:
>   - **`.EFT`**: Efficiency Calibration Files (EFFTRAN 11-token & MEFFTRAN 5-token layouts; imported & exported as `*_sample.EFT` / `*_corrected.EFT`)
>   - **`.LIB`**: Nuclide Library Files (128-byte direct-access binary records as in `gv.f`; exported as `*_corrected.LIB` alongside a `<name>_gv.txt` audit table)
>
> **Automatic & Manual Selection**: `.LIB` and `.EFT` automatically select the GammaVision backend; `.CAL`, `.NLB`, and `.CTF` select Genie 2000. You can also force the backend via the GUI **Software** selector, CLI `--software genie|gammavision`, or `EFFSUITE_SOFTWARE`.
>
> *Other vendor formats (such as ORTEC Maestro `.spc` / `.cal` or InterWinner) are **NOT** supported.*

> [!CAUTION]
> ### ⚠️ WEFFTRAN Qualification Notice (Untested / Experimental)
> **The WEFFTRAN module (Well-type HPGe detector geometry) is NOT fully laboratory tested or physically qualified yet.**
> While the Fortran ray-tracing boundary bug and 3D spatial summing engine have been mathematically implemented, this geometry has not completed empirical laboratory validation against reference standards. Users must treat all WEFFTRAN calculation results as experimental and independently verify them before analytical use.

---

## 📖 Historical Heritage & Attribution

EffSuite is a unified modernization and scientific extension of the classic efficiency transfer and true coincidence summing codes developed by **Dr. Tim Vidmar**:

- **EFFTRAN** (version 4.9 2026) — Cylindrical geometry
- **MEFFTRAN** (version 1.8) — Marinelli beaker geometry
- **WEFFTRAN** — Well-type detector geometry

Official EFFTRAN Project Website: **https://efftran.github.io/**

```text
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
C                                                                       C
C  EFFTRAN (version 4.9 2026)                                           C
C  Copyright (c) 2005-2026                                              C
C  Tim Vidmar                                                           C
C                                                                       C
C  Permission to use, copy, modify, distribute and sell this software   C
C  and its documentation for any purpose is hereby granted without      C
C  fee, provided that the above copyright notice appears in all         C
C  copies and that both that copyright notice and this permission       C
C  notice appear in all supporting documentation. Tim Vidmar makes      C
C  no representations about the suitability of this software for any    C
C  purpose. It is provided 'as is' without express or implied warranty. C
C                                                                       C
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
```

---

## 🚀 Overview

**EffSuite** unites EFFTRAN, MEFFTRAN, and WEFFTRAN under a single high-performance framework designed for high-resolution gamma-ray spectrometry (HPGe) laboratories:

1. **Native Fortran Physics Precision**: Executes verified Fortran numerical engines with updated double-precision numerical token sanitization and scientific format output.
2. **Modern Desktop GUI (Qt6)**: Engineered with a dark GL-GUM Workbench theme, automatic 1080p/4K DPI scaling, live 2D CAD dimension schematics, interactive efficiency curves, and dedicated calculation activity logs.
3. **High-Throughput Parallel Coincidence Summing**: Coincidence summing correction factors ($F_{corr}$) are computed in one go across all nuclides in the calibration or certificate library, leveraging multi-core parallelization (`workers = max(1, os.cpu_count() - 2)`).
4. **Canberra / Mirion Genie 2000 and ORTEC GammaVision Integration**: Directly imports and updates `.CAL` efficiency calibrations, `.NLB` nuclide libraries, and `.CTF` certificate files. File selectors default directly to `C:\GENIE2K\CAMFILES`. GammaVision `.LIB` libraries and `.EFT` efficiency files go through the pure-Python backend in `gammavision.py`.

> [!IMPORTANT]
> **GammaVision has been implemented as EFFTRAN is doing it, but I cannot test it because I do not have the software. Volunteers are welcome to test it and provide feedback.**
5. **Integrated NIST XCOM Cross-Section Engine**: Built-in composition editor and automated NIST XCOM 3.1 calculation for photon attenuation cross-sections ($\mu/\rho$) across 60+ pre-configured gamma materials.
6. **Headless Automation CLI**: Full command-line interface (`EffSuite_CLI.exe` or `python -m effsuite.app_cli`) enabling automated LIMS integration and batch recalculations.

---

## ⚡ Quick Start on Windows

### Option 1: Standalone Windows Installation (Recommended for Labs)
1. Download or compile the installer (`installer/EffSuite.iss`).
2. Run the installer. It installs per-user without requiring Administrator rights to:
   ```text
   C:\GENIE2K\EffSuite\          (or %LOCALAPPDATA%\Programs\EffSuite\)
   ```
3. Launch **EffSuite GUI** from the Start Menu or desktop shortcut.

### Option 2: Running from Source (Python Virtual Environment)
1. Clone or extract the repository to a local directory (e.g., `C:\PGM\EffSuite`).
2. Run `Setup_Windows.bat`. It detects your 64-bit Python (`3.11` to `3.14`), initializes `.venv`, and installs dependencies:
   ```cmd
   Setup_Windows.bat
   ```
   *(Optional)* To target a specific Python installation:
   ```cmd
   Setup_Windows.bat "C:\Python314\python.exe"
   ```
3. Launch the desktop interface:
   ```cmd
   Start_GUI.bat
   ```

---

## 🖥️ Graphical User Interface (GUI)

The GUI follows the intuitive workflow of analytical gamma spectrometry:

```
[ Detector ] ➔ [ Source ] ➔ [ Efficiency ] ➔ [ Certificate / Library ] ➔ [ Material ] ➔ [ Calculate ]
```

* **Detector Tab**: Configure crystal diameter, length, dead layers, core hole, endcap distance, and materials. Features a live 2D CAD schematic with real-time dimension callouts.
* **Source Tab**: Define standard calibration source and unknown sample side by side (fill height, container wall/bottom, density, and matrix composition).
* **Efficiency Tab**: Import experimental calibration points from Genie 2000 `.CAL`, GammaVision `.EFT`, or CSV/text, compute transfer factors, preview interactive log-log efficiency curves, and export transferred `.CAL` (Genie 2000) or `.EFT` (GammaVision).
* **Certificate / Library Tab**: Open Genie `.NLB` / `.CTF` files (from `C:\GENIE2K\CAMFILES`) or GammaVision `.LIB` libraries, or input nuclides manually (e.g. `Co-60, Cs-134, Eu-152`). Calculates coincidence summing corrections in a single parallel pass and exports clearly labeled Genie (`.NLB` / `.CTF`) or GammaVision (`.LIB` + `_gv.txt`) files.
* **Material Tab**: Add or edit custom chemical formulas and densities. Calls the embedded NIST XCOM engine to generate photon cross-section attenuation files on the fly.
* **Activity & Audit Log**: High-contrast console (`#38bdf8` cyan on dark background) reporting engine stages, ray-tracing counts, and convergence diagnostics in real time.

---

## 💻 Command-Line Interface (CLI) & Automation

EffSuite provides a headless CLI (`EffSuite_CLI.exe` or `CLI.bat`) for batch automation and scripting:

### 1. Re-running a Saved GUI Project
```cmd
CLI.bat run "C:\MyLab\Soil_Sample_01.effsuite.json" --out "C:\MyLab\Results_01"
```

### 2. Parametric Invocation (Cylindrical Geometry)
```cmd
CLI.bat cylinder ^
  --detector High-energy ^
  --standard Solution ^
  --sample Soil ^
  --sample-height 45.0 ^
  --nuclides Co-60,Cs-134,Eu-152 ^
  --workers 0 ^
  --out "C:\MyLab\Results_Cylinder"
```

### 3. Marinelli Beaker Execution
```cmd
CLI.bat marinelli ^
  --detector High-energy ^
  --standard Standard ^
  --sample Sample ^
  --nuclides Co-60,Cs-137,I-131 ^
  --out "C:\MyLab\Results_Marinelli"
```

### 4. Well-Type Detector (WEFFTRAN with Spatial Summing — *Experimental / Untested*)
> **Note:** The WEFFTRAN engine is not yet empirically tested or qualified in the laboratory. Results must be independently verified.
```cmd
CLI.bat well ^
  --detector well ^
  --standard Standard ^
  --sample Sample ^
  --nuclides Eu-152 ^
  --workers 0 ^
  --out "C:\MyLab\Results_Well"
```

### CLI Exit Codes
| Exit Code | Status | Meaning |
| :---: | :--- | :--- |
| **0** | **Success** | All calculations finished cleanly; valid `.CAL` and `.NLB`/`.CTF` generated. |
| **1** | **Diagnostic Success** | Calculations succeeded, but low-energy lines below detector threshold (<40 keV) could not be corrected and are flagged with `*`. |
| **2** | **Runtime Error** | Invalid input parameters, missing geometry files, or engine execution error. |

For detailed inter-process integration guidance, see [CLI_INTEGRATION_GUIDE.md](CLI_INTEGRATION_GUIDE.md).

---

## 🔬 Scientific & Physics Implementation

Detailed technical comparisons against the original codes are documented in [SCIENTIFIC_AUDIT_REPORT.md](SCIENTIFIC_AUDIT_REPORT.md) and [EFFTRAN_MEFFTRAN_WEFFTRAN_CHANGES.md](EFFTRAN_MEFFTRAN_WEFFTRAN_CHANGES.md).

### Summary of Physics & Engineering Enhancements:
| Feature | Original Implementation | EffSuite Modernization |
| :--- | :--- | :--- |
| **Sample Bulk Density (`rho`)** | Added in EFFTRAN 4.9 / MEFFTRAN 1.8 (with `do j=1,ne` loop bug in `mine.f`/`scatter.f` and `log(0)` crash on `Point.txt`) | Full 8-line source density scaling ($\rho / \rho_0$) across Cylindrical, Marinelli, and Well (`WEFFTRAN`) with fixed `do j=1,ns` loop bounds, `Point.txt` guard, and GUI auto-fill |
| **Coincidence Summing** | Serial Fortran loop per nuclide | Parallelized Monte Carlo cascade recursion across all CPU cores in one pass |
| **Numerical Format** | 3-decimal fixed format (`F8.3`) in coincidence dumps | Scientific format (`ES14.6`) to preserve small positive summing factors |
| **Token Sanitization** | Failed on denormalized or empty tokens | Strict token sanitizer replacing noise $<10^{-15}$ with analytical floor |
| **WEFFTRAN Spatial Patch** | Zero-volume integration defect on tall samples | Full spatial integration over cylinder and well volume, eliminating negative/near-singular factors |
| **Ray-Tracing Boundary** | Critical ray boundary condition bugs in well cavity | Fixed Fortran boundary crossing in `path_fixed.f` |
| **Genie 2000 Integration** | Manual text copy-paste / in-place COM overwrite | Non-destructive CAM `.CAL`/`.NLB`/`.CTF` reading and safe writing with round-trip verification |
| **GammaVision Integration** | `gv.f` (`EFFTRAN.Lib` in-place overwrite + `gv.txt`) & Excel macro `.EFT` | Pure-Python non-destructive `.LIB` & `.EFT` reader/writer with round-trip verification and `<name>_gv.txt` report (*implemented as in EFFTRAN, untested — volunteers welcome*) |
| **Materials Engine** | External Excel spreadsheet macros | Native Python parser + NIST XCOM 3.1 with automatic material library cache |

---

## 📁 Repository Structure

```text
EffSuite/
├── native/                         # Fortran source files & boundary patches
│   ├── wefftran_geometry/          # Patched WEFFTRAN ray-tracing routines
│   └── README.md
├── src/effsuite/                   # Core Python application package
│   ├── assets/                     # Pre-compiled engines, XCOM, compositions, & libraries
│   │   ├── common/Composition/     # Pre-configured material composition cards
│   │   ├── Decay_Data/             # Evaluated decay data libraries
│   │   └── xcom/                   # NIST XCOM 3.1 photon attenuation engine
│   ├── licensing/                  # Unrestricted community license verification
│   ├── app_cli.py                  # Headless command-line interface
│   ├── gammavision.py              # ORTEC GammaVision .LIB / .EFT pure-Python adapter
│   ├── genie.py                    # Genie 2000 CAM/CAL/NLB/CTF engine adapter
│   ├── geometry_view.py            # Matplotlib 2D CAD cross-section renderer
│   ├── gui.py                      # Modern Qt6 desktop user interface
│   ├── materials.py                # Material builder & XCOM wrapper
│   ├── parallel_coincidence.py     # Multiprocessing coincidence summing engine
│   ├── software.py                 # Genie 2000 / GammaVision backend dispatcher
│   ├── spatial_summing.py          # Spatial cascade integration engine
│   ├── suite.py                    # Shared calculation coordinator
│   └── well_spatial.py             # WEFFTRAN 3D spatial integration
├── tests/                          # Automated unit and regression test suite
├── tools/                          # Developer build & diagnostic utilities
├── Build_Installer.bat             # Compiles Inno Setup installer
├── Build_Windows.bat               # Compiles standalone PyInstaller executable
├── CLI.bat                         # Windows CLI launcher
├── Run_Tests_Windows.bat           # Executes automated test suite
├── Setup_Windows.bat               # Initializes .venv & installs dependencies
├── Start_GUI.bat                   # Desktop GUI launcher
├── EFFTRAN_MEFFTRAN_WEFFTRAN_CHANGES.md # Complete scientific audit & bugfix log
├── SCIENTIFIC_AUDIT_REPORT.md      # Detailed comparison vs original Tim Vidmar codes
├── USER_GUIDE.md                   # Complete end-user tutorial
└── README.md                       # This file
```

---

## 🛠️ Building & Verification

### Running Unit Tests
```cmd
Run_Tests_Windows.bat
```
or directly in the virtual environment (parallel runner across CPU cores):
```cmd
.venv\Scripts\python.exe tools\run_tests.py
```

### Building the Standalone Executable
```cmd
Build_Windows.bat
```
Produces standalone `dist\EffSuite\` containing `EffSuite.exe` and `EffSuite_CLI.exe`.

### Compiling the Installer
Open `installer\EffSuite.iss` in Inno Setup 7 and compile, or run:
```cmd
Build_Installer.bat
```

---

## 📄 License & Third-Party Notices

* **EffSuite Codebase**: Licensed under the GNU General Public License v3.0 (see [GPL-3.0](third_party/GPL-3.txt)).
* **EFFTRAN, MEFFTRAN, WEFFTRAN Engines**: Copyright (c) 2005–2026 Tim Vidmar. Provided with permission for use, copy, modification, and distribution with attribution (see [third_party](third_party/)).
* **NIST XCOM**: Photon cross-sections database developed by M.J. Berger and J.H. Hubbell, National Institute of Standards and Technology (NIST).

*EffSuite built by ChatGPT & Gemini under the supervision of G. Lutter.*
