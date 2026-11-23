# EffSuite — Gamma Spectrometry Efficiency Transfer & Summing Suite

<p align="center">
  <img src="https://img.shields.io/badge/Version-0.3.3-yellow.svg" alt="Version 0.3.3" />
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg" alt="Python Version" />
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20(x64)-0078D6.svg" alt="Windows Platform" />
  <img src="https://img.shields.io/badge/Genie%202000-CAM%20%7C%20CAL%20%7C%20NLB%20%7C%20CTF-8A2BE2.svg" alt="Genie 2000 Integration" />
  <img src="https://img.shields.io/badge/GammaVision-EFT%20%7C%20LIB%20(Untested)-008080.svg" alt="GammaVision Integration (Untested)" />
  <img src="https://img.shields.io/badge/Physics%20Engines-EFFTRAN%205.0%20%7C%20MEFFTRAN%201.9%20%7C%20WEFFTRAN-2ea44f.svg" alt="Physics Engines" />
  <img src="https://img.shields.io/badge/License-GPL--3.0%20%2F%20Vidmar%20Attribution-orange.svg" alt="License" />
</p>

*EffSuite (v0.3.3) built by ChatGPT, Gemini and Claude under the supervision of G. Lutter.*

---

> [!WARNING]
> ### Disclaimer and terms of use
> **Provided strictly on an AS-IS basis. G. Lutter accepts NO responsibility or liability under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. Users must independently verify all results.**

> [!IMPORTANT]
> ### File format and spectrometry software compatibility (Genie 2000 and GammaVision)
> EffSuite tells **Canberra / Mirion Genie 2000** files from **ORTEC GammaVision** files by their extension, and labels the software in the GUI, CLI, and exported reports:
> - **Canberra / Mirion Genie 2000**:
>   - **`.CAL`**: Efficiency Calibration Files (imported & exported as `*_sample.CAL` / `*_corrected.CAL`)
>   - **`.NLB`**: Nuclide Library Files (binary, exported as `*_corrected.NLB`)
>   - **`.CTF`**: Certificate / Source Files (exported as `*_corrected.CTF`)
>   - **`.CNF`**: CAM Spectral Files
> - **ORTEC GammaVision** *(implemented as in EFFTRAN/MEFFTRAN; **untested**, volunteers welcome)*:
>   - **`.EFT`**: Efficiency Calibration Files (EFFTRAN 11-token & MEFFTRAN 5-token layouts; imported & exported as `*_sample.EFT` / `*_corrected.EFT`)
>   - **`.LIB`**: Nuclide Library Files (128-byte direct-access binary records as in `gv.f`; exported as `*_corrected.LIB` alongside a `<name>_gv.txt` audit table)
>
> **Selection**: `.LIB` and `.EFT` automatically select the GammaVision backend; `.CAL`, `.NLB`, and `.CTF` select Genie 2000. You can also force the backend via the GUI **Software** selector, CLI `--software genie|gammavision`, or `EFFSUITE_SOFTWARE`.
>
> *Other vendor formats (such as ORTEC Maestro `.spc` / `.cal` or InterWinner) are **NOT** supported.*

> [!CAUTION]
> ### WEFFTRAN qualification notice (untested, experimental)
> **The WEFFTRAN module (Well-type HPGe detector geometry) is NOT fully laboratory tested or physically qualified yet.**
> The Fortran ray-tracing boundary fix and the 3D spatial summing model are implemented, but this geometry has not yet been validated in the laboratory against reference standards. Users must treat all WEFFTRAN calculation results as experimental and independently verify them before analytical use.

---

## Historical background and attribution

EffSuite combines and extends the efficiency transfer and true coincidence summing codes written by **Dr. Tim Vidmar**:

- **EFFTRAN** (version 5.0 2026): cylindrical geometry
- **MEFFTRAN** (version 1.9): Marinelli beaker geometry
- **WEFFTRAN**: well-type detector geometry

Official EFFTRAN Project Website: **https://efftran.github.io/**

```text
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
C                                                                       C
C  EFFTRAN (version 5.0 2026)                                           C
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

## Overview

**EffSuite** runs EFFTRAN, MEFFTRAN, and WEFFTRAN from one program, for high-resolution gamma-ray spectrometry (HPGe) laboratories:

1. **Original Fortran physics**: the EFFTRAN 5.0 and MEFFTRAN 1.9 engines run unchanged apart from small numerical safeguards and a higher-precision output format. Wells use a new spatial summing model that fixes the original's tall-sample failure.
2. **Desktop GUI (Qt)**: the original workbook tabs as forms, with automatic 1080p/4K scaling, a dimensioned cross-section, efficiency charts and a calculation log.
3. **Parallel coincidence summing**: summing correction factors *C* for every nuclide of a library in one run, on all CPU cores (`workers = 0`: number of CPUs minus 2).
4. **Summing-factor uncertainty**: a relative standard uncertainty u(C) for every factor, which the original programs do not provide ([details](docs/TCS_UNCERTAINTY.md)).
5. **Genie 2000 and GammaVision**: reads `.CAL` efficiency calibrations, `.NLB` nuclide libraries and `.CTF` certificates, and writes verified corrected copies (file dialogs open in `C:\GENIE2K\CAMFILES`). GammaVision `.LIB` and `.EFT` files are handled in pure Python.
6. **NIST XCOM materials**: composition editor and automatic XCOM 3.1 attenuation tables; the 20 original EFFTRAN / MEFFTRAN materials are bundled; your own materials live in your data folder (changeable with **Tools → Default data folder…** or `CLI.bat config --data-dir`).
7. **Command line**: `EffSuite_CLI.exe` (or `python -m effsuite.app_cli`) for scripts, LIMS integration and batch runs.

> [!IMPORTANT]
> **GammaVision has been implemented as EFFTRAN is doing it, but I cannot test it because I do not have the software. Volunteers are welcome to test it and provide feedback.**

---

## Quick start on Windows

### Option 1: Standalone Windows installation (recommended for labs)
1. Download or compile the installer (`installer/EffSuite.iss`).
2. Run the installer. It installs per-user without requiring Administrator rights to:
   ```text
   C:\GENIE2K\EffSuite\          (Genie 2000 installed: program, Data and Results together)
   %LOCALAPPDATA%\Programs\EffSuite\   (otherwise; Data and Results go to Documents\EffSuite\)
   ```
3. Launch **EffSuite GUI** from the Start Menu or desktop shortcut.

### Option 2: Running from source (Python virtual environment)
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

## Graphical user interface (GUI)

The GUI tabs follow the order of a gamma spectrometry analysis:

```
[ Start ] ➔ [ Detector ] ➔ [ Standard & Sample ] ➔ [ Efficiency ] ➔ [ Library / Certificate ]      (+ Material Editor window)
```

* **Start**: choose Complete analysis, Efficiency transfer only or True coincidence summing only; load an example or a saved project.
* **Detector**: crystal dimensions, dead layers, core hole, end cap and materials, with a dimensioned cross-section that updates as you type.
* **Standard & Sample**: the sample and the standard side by side (filling height, container, density, matrix). With True coincidence summing only, the tab is renamed **Sample**, only the sample is needed and the Standard column is hidden.
* **Efficiency**: import the standard calibration (Genie `.CAL`, GammaVision `.EFT`, CSV/text), transfer it to the sample, see the efficiency curves, and export the sample `.CAL` / `.EFT`.
* **Library / Certificate**: open a Genie `.NLB` / `.CTF` or a GammaVision `.LIB`, or type nuclides (`Co-60, Cs-134, Eu-152`). Calculates the summing factors *C* and their uncertainty u(C), and exports corrected Genie or GammaVision (`.LIB` + `_gv.txt`) files.
* **Material Editor** (separate window, opened with **Materials…** or **Edit** on the Detector and Standard & Sample pages): create materials from chemical formulas and a density; **Apply** generates the XCOM attenuation table and updates the material lists, while the other pages stay usable.
* **Log**: engine stages, warnings and convergence diagnostics as the calculation runs.

Step-by-step instructions: [User Guide](docs/USER_GUIDE.md).

---

## Command-line interface (CLI) and automation

EffSuite has a headless CLI (`EffSuite_CLI.exe` or `CLI.bat`) for batch automation and scripting:

### 1. Re-running a saved GUI project
```cmd
CLI.bat run "C:\MyLab\Soil_Sample_01.effsuite.json" --out "C:\MyLab\Results_01"
```

### 2. Complete analysis (cylindrical geometry)
```cmd
CLI.bat cylinder ^
  --detector High-energy ^
  --standard Solution ^
  --calibration "C:\GENIE2K\CAMFILES\Standard.CAL" ^
  --sample Soil ^
  --sample-height 45.0 ^
  --library "C:\GENIE2K\CAMFILES\LIBRARY.NLB" ^
  --out "C:\MyLab\Results_Cylinder"
```

### 3. Summing only (Marinelli beaker)
```cmd
CLI.bat marinelli ^
  --detector High-energy ^
  --sample Sample ^
  --nuclides Co-60,Cs-137,I-131 ^
  --tcs-u-peak 4 --tcs-u-total 8 ^
  --out "C:\MyLab\Results_Marinelli"
```

### 4. Well-type detector (WEFFTRAN with spatial summing, *experimental, untested*)
> **Note:** The WEFFTRAN engine is not yet empirically tested or qualified in the laboratory. Results must be independently verified.
```cmd
CLI.bat well ^
  --detector well ^
  --sample Sample ^
  --nuclides Eu-152 ^
  --out "C:\MyLab\Results_Well"
```

### CLI Exit Codes
| Exit Code | Status | Meaning |
| :---: | :--- | :--- |
| **0** | **Success** | The calculation finished and every reported summing line has a valid factor. |
| **1** | **Success with uncorrected lines** | Results were published, but some lines have no usable factor and are marked `*` (no decay data, line not calculated, or a failed well convergence check). |
| **2** | **Error** | Invalid input, missing file or engine, or engine failure; nothing is published. |

All commands and options, and how to call EffSuite from other software: [CLI Integration Guide](docs/CLI_INTEGRATION_GUIDE.md).

---

## Scientific and physics implementation

Every difference from the original programs is documented in [CHANGES_FROM_ORIGINALS.md](docs/CHANGES_FROM_ORIGINALS.md); the test evidence is in [VALIDATION.md](docs/VALIDATION.md).

### Summary of physics and engineering changes
| Feature | Original Implementation | EffSuite Modernization |
| :--- | :--- | :--- |
| **Sample bulk density (`rho`)** | Added in EFFTRAN 4.9–5.0 / MEFFTRAN 1.8–1.9 (absent in WEFFTRAN) | 8-line source density scaling ($\rho / \rho_0$) across Cylindrical, Marinelli, and Well (`WEFFTRAN`) with validated loop bounds, `Point.txt` guard, and GUI auto-fill |
| **Transfer uncertainty** | Fixed 0.5% standard/sample placeholders in older versions | Monte Carlo propagation ($u = \sqrt{u_{\mathrm{ref}}^2 + (100 s_{\mathrm{std}})^2 + (100 s_{\mathrm{sample}})^2}$) for Cylindrical (EFFTRAN 5.0) and Marinelli (MEFFTRAN 1.9); wells keep the original 0.5% terms |
| **Summing factor uncertainty** | None: factors are given without uncertainty | Relative standard uncertainty u(C) for every factor, propagated from the peak and total efficiency uncertainties through engine-computed sensitivity coefficients, plus the engine's numerical uncertainty (see [TCS_UNCERTAINTY.md](docs/TCS_UNCERTAINTY.md)) |
| **Coincidence summing** | One nuclide at a time, run from Excel | All library nuclides in one run, in parallel native processes (unchanged Fortran cascade calculation) |
| **Numerical format** | 3-decimal fixed format (`f15.3`) in `coin.txt` | Scientific format (`e23.15`) to preserve small positive summing factors |
| **Token handling** | Failed on denormalized or empty tokens | Strict token parser (Fortran `D` exponents accepted); since v0.3.0 a NaN or infinite engine value stops the calculation instead of being replaced by $10^{-15}$ |
| **WEFFTRAN spatial patch** | Zero-volume integration defect on tall samples | Full spatial integration over cylinder and well volume, eliminating negative/near-singular factors |
| **Ray-tracing boundary** | Critical ray boundary condition bugs in well cavity | Fixed Fortran boundary crossing in `path_fixed.f` |
| **Well calculation speed** | — (spatial integration is new in EffSuite) | Compiled Fortran ray tracing (`raytrace`, v0.3.0): DET007 complete analysis 12.5 s instead of 108 s, peak memory below 1 GB |
| **Genie 2000 integration** | Manual text copy-paste / in-place COM overwrite | Non-destructive CAM `.CAL`/`.NLB`/`.CTF` reading and safe writing with round-trip verification |
| **GammaVision integration** | `gv.f` (`EFFTRAN.Lib` in-place overwrite + `gv.txt`) & Excel macro `.EFT` | Pure-Python non-destructive `.LIB` & `.EFT` reader/writer with round-trip verification and `<name>_gv.txt` report (*implemented as in EFFTRAN, untested — volunteers welcome*) |
| **Materials** | External Excel spreadsheet macros | Native Python parser + NIST XCOM 3.1 with automatic material library cache |

---

## Documentation

| Document | For |
| :--- | :--- |
| [User Guide](docs/USER_GUIDE.md) | Using the desktop program: transfer, summing, export, results |
| [Materials and XCOM](docs/MATERIALS.md) | Creating materials, changing sample density |
| [Summing-Factor Uncertainty](docs/TCS_UNCERTAINTY.md) | Method, inputs and limits of u(C) |
| [CLI Integration Guide](docs/CLI_INTEGRATION_GUIDE.md) | Command line, exit codes, calling EffSuite from other software |
| [Changes from the Originals](docs/CHANGES_FROM_ORIGINALS.md) | Every physics, source and data difference from EFFTRAN, MEFFTRAN and WEFFTRAN |
| [Well Spatial Model](docs/WELL_SPATIAL_MODEL.md) | The well-detector summing model and its evidence |
| [Validation](docs/VALIDATION.md) | What is tested, and what remains before routine use |
| [Architecture](docs/ARCHITECTURE.md) | Code structure, modules, repository layout, builds |
| [Release Notes](RELEASE_NOTES.md) | Changes per version |
| [Third-Party Notices](THIRD_PARTY_NOTICES.md) | Licences and original notices |

---

## Repository Structure

```text
EffSuite/
├── docs/            # documentation (index: docs/README.md) and project web page
├── src/effsuite/    # Python package; assets/ holds the Fortran engines, data and XCOM
├── native/          # historical WEFFTRAN geometry patches and original references
├── tests/           # automated tests
├── tools/           # build, validation and release utilities
├── examples/        # validation evidence and example inputs
├── installer/       # Inno Setup script
├── third_party/     # original notices and licences
└── *.bat            # Setup_Windows, Start_GUI, CLI, Run_Tests_Windows, Build_Windows, Build_Installer
```

Module-level details: [Architecture](docs/ARCHITECTURE.md).

---

## Building and verification

### Running unit tests
```cmd
Run_Tests_Windows.bat
```
or directly in the virtual environment (parallel runner across CPU cores):
```cmd
.venv\Scripts\python.exe tools\run_tests.py
```

### Building the standalone executable
```cmd
Build_Windows.bat
```
Produces standalone `dist\EffSuite\` containing `EffSuite_GUI.exe` and `EffSuite_CLI.exe`.

### Compiling the installer
Open `installer\EffSuite.iss` in Inno Setup 7 and compile, or run:
```cmd
Build_Installer.bat
```

---

## License and third-party notices

* **EffSuite Codebase**: Licensed under the GNU General Public License, version 3 or (at your option) any later version (SPDX: `GPL-3.0-or-later`; see [LICENSE](LICENSE)). This covers EffSuite's own code only.
* **EFFTRAN, MEFFTRAN, WEFFTRAN Engines**: EFFTRAN and MEFFTRAN Copyright (c) 2005–2026 Tim Vidmar; WEFFTRAN Copyright (c) 1995–2016 Tim Vidmar. Provided with permission for use, copy, modification, and distribution with attribution (see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [third_party](third_party/)).
* **Numerical Recipes routines** (`sobseq`, `rtbis`) in the engine sources: (C) Copr. 1986-92 Numerical Recipes Software. Proprietary; not covered by the licences above.
* **NIST XCOM**: Photon cross-sections database developed by M.J. Berger and J.H. Hubbell, National Institute of Standards and Technology (NIST). Its program notice grants permission for **non-commercial use only**.
* **Qt / PySide6** (LGPL-3.0), **libquadmath** (LGPL-2.1) and the Python packages: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

*EffSuite (v0.3.3) built by ChatGPT, Gemini and Claude under the supervision of G. Lutter.*
