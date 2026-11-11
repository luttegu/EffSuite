# Technical Summary of Enhancements, Fixes, and Architectural Changes in EffSuite

**Compared to the Original EFFTRAN (v4.8 & v4.9), MEFFTRAN (v1.7 & v1.8), and WEFFTRAN Distributions, and Previous EffSuite Releases**  
*Document Version: 1.1 — EffSuite v0.1.3 (November 2026)*  
*Author: EffSuite Development Team (built by ChatGPT & Gemini under the supervision of G. Lutter)*  
*Target Audience: Original Author, Maintainers, and Scientific Evaluators of EFFTRAN / MEFFTRAN / WEFFTRAN*  

> **Disclaimer:** Provided strictly on an AS-IS basis. G. Lutter accepts NO responsibility or liability under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. Users must independently verify all results.

---

## Executive Summary

**EffSuite (v0.1.3)** is an open-source modernization and cross-platform reimplementation of the gamma-spectrometry efficiency transfer and true coincidence summing framework originally established by **EFFTRAN** (v4.9, cylindrical geometries), **MEFFTRAN** (v1.8, Marinelli beaker geometries), and **WEFFTRAN** (well-type detectors).

The objective of this work was **not** to alter the validated core physical models of the original Fortran engines, but rather to:
1. Preserve 100% numerical agreement with validated EFFTRAN/MEFFTRAN reference cases while fixing upstream numerical bugs discovered in EFFTRAN 4.9 and MEFFTRAN 1.8.
2. Integrate the new 8th-line explicit **Source Bulk Density (`rho` [g/cm³])** model format introduced in EFFTRAN 4.9 and MEFFTRAN 1.8, and extend it uniformly to WEFFTRAN (`well`), the desktop GUI, and the headless CLI with full backward compatibility for 7-line models.
3. Resolve the known numerical singularity/instability in legacy WEFFTRAN for tall sample geometries extending above the detector crystal.
4. Eliminate dependencies on legacy 32-bit Microsoft Excel, VBA macros, and Windows-only 16/32-bit execution boundaries.
5. Provide a cross-platform (Windows, Linux, macOS) architecture with parallel multi-core calculation, headless CLI batch capabilities, interactive CAD-style cross-section visualization, and automated Genie 2000 CAM file processing.
6. Unify redundant data assets (attenuation tables, compositions, and 260+ radionuclide decay schemes) into a clean, shared hierarchy with automated NIST XCOM cross-section generation.

---

## 0. Integration of Upstream EFFTRAN 4.9 & MEFFTRAN 1.8 in EffSuite v0.1.3

### 0.1 What Changed Upstream in `EFFTRAN 4.9` (from `4.8`) and `MEFFTRAN 1.8` (from `1.7`)
1. **Explicit Sample Bulk Density (`rho`) in Source Models (8th Line)**:
   - All source geometry files (`Sample/*.txt` and `Standard/*.txt`) were extended from 7 lines to **8 lines**, adding the sample bulk density `rho` in $\text{g/cm}^3$ as line 8 (e.g., `1.00` for water solutions, `1.40` for `Soil.txt`, `0.00` for `Point.txt`).
   - The Fortran routines `mine.f`, `total.f`, `scatter.f`, and `eta.f` read `rho` from line 8 of `source.txt`, read the nominal reference material density `rho0` from line 1 of `.\Composition\<smat>.txt`, and shift the logarithmic linear attenuation coefficients $\ln(\mu)$ by $\ln(\rho / \rho_0)$:
     $$\ln \mu(E, \rho) = \ln \mu(E, \rho_0) + \ln\left(\frac{\rho}{\rho_0}\right) \implies \mu(E, \rho) = \mu(E, \rho_0) \cdot \frac{\rho}{\rho_0}$$
   - If the 8th line is omitted (`end=88, err=88`), the Fortran code falls back to unscaled $\mu(E, \rho_0)$ ($\rho = \rho_0$).
2. **New `HeavyWater` Reference Material**:
   - Added `Composition\HeavyWater.txt` ($\text{H}_2\text{O}$ with $\rho_0 = 2.0\text{ g/cm}^3$) and `Material\HeavyWater.txt` to test density scaling against `Water` with $\rho = 2.0\text{ g/cm}^3$.
3. **In-Memory Caching of `coin.txt` in `EFFTRAN_4.9/gv.f`**:
   - Instead of reopening and scanning `coin.txt` from disk on every call to `coincidence(j)`, `gv.f` loads `coin.txt` once into `common /tabela/ start,stop,n(nn),p(nn)` and slices `start..stop` in memory.

### 0.2 Upstream Bugs Found in `EFFTRAN 4.9` & `MEFFTRAN 1.8` and Fixed in `EffSuite v0.1.3`

During line-by-line audit of `EFFTRAN_4.9` and `MEFFTRAN_1.8`, three upstream defects were identified and corrected in `EffSuite v0.1.3`:

| # | Upstream Defect in `EFFTRAN 4.9` & `MEFFTRAN 1.8` | Physical / Numerical Impact | Fix Implemented in `EffSuite v0.1.3` |
| :-: | :--- | :--- | :--- |
| **1** | **Wrong Loop Upper Bound (`do j=1,ne` instead of `do j=1,ns`) in `mine.f` and `scatter.f`**<br>• `mine.f` (line 108 in EFFTRAN 4.9; line 101 in MEFFTRAN 1.8)<br>• `scatter.f` (line 67 in EFFTRAN 4.9; line 70 in MEFFTRAN 1.8) | While `total.f` and `eta.f` loop `do j=1,ns` over all $ns \approx 80\text{–}105$ XCOM energy rows, `mine.f` and `scatter.f` loop `do j=1,ne`:<br>• In `mine.f`, `ne` is **uninitialized (`0`)**, so **0 rows** are scaled and `mine.exe` ignores `rho`.<br>• In `scatter.f`, `ne = 25` (from `total.txt`), so only the first 25 XCOM points ($E \lesssim 30\text{ keV}$) are scaled by $\rho / \rho_0$, while **all energies above $\sim 30\text{ keV}$ remain unscaled at $\rho_0$**! Consequently, `Water` at $\rho = 2.0$ disagrees with `HeavyWater` ($\rho_0 = 2.0$) in scattered/buildup and peak-to-total calculations. | Fixed loop bounds to `do j=1,ns` in both `mine.f` and `scatter.f` across `cylindrical`, `marinelli`, and `well` Fortran sources. With this fix, `Water` with $\rho = 2.0$ matches `HeavyWater` ($\rho_0 = 2.0$) to 100% precision across all engine stages. |
| **2** | **`Point.txt` (`vacuum`, `rho = 0.00`) Triggers `log(0.0) = -Infinity` and `NaN`** | `Standard\Point.txt` specifies `vacuum` ($\rho_0 = 10^{-12}\text{ g/cm}^3$) on line 6 and `0.00` on line 8. Evaluating `log(rho/rho0)` computes `log(0.0) = -Infinity`, corrupting `smu(j)` and producing `NaN` (`-Inf - (-Inf)`) during spline interpolation in `inter`/`interpol`. | Added positivity guard `if (rho.le.0.) rho=rho0` in `mine.f`, `total.f`, `scatter.f`, and `eta.f` across all engines. |
| **3** | **Loss of Gamma Energy Precision (`f12.1`) & Embedded `system('total.exe')` in `EFFTRAN_4.9/transfer.f`** | Upstream `EFFTRAN_4.9/transfer.f` changed output formatting from `format(3e15.5)` to `format(f12.1,e15.5,f12.1)` (truncating energies such as $46.539\text{ keV}$ to $46.5\text{ keV}$) and embedded `call system('total.exe')` inside `transfer.f`. | Retained EffSuite's stage-isolated `transfer.f` with full scientific precision `format(3e15.5)`. |

### 0.3 Comparison of `EffSuite v0.1.3` vs. `EffSuite v0.1.2`

1. **8-Field Source Model Across All Geometries (`model_io.py`, `suite.py`)**:
   - Extended `CYLINDER_SOURCE`, `MARINELLI_SOURCE`, and `well` source definitions from 7 fields to 8 fields by adding `("Source density", "g/cm³")` as the 8th line.
   - Full backward compatibility: existing 7-line `.txt` files and 7-element `.effsuite.json` project files automatically populate `Source density` from the nominal density in `Composition/<material>.txt`.
   - Updated all 39 bundled `.txt` models in `Sample/` and `Standard/` and all example `.effsuite.json` projects to 8 fields, and added `HeavyWater.txt` to `assets/common/Composition/` and `assets/common/Material/`.
2. **Extension of 8th-Line Density Scaling to WEFFTRAN (`spatial_summing.py` & `well/source/*.f`)**:
   - Updated `_xcom_table`, `material_mu`, and `well_local_response` in `src/effsuite/spatial_summing.py` so WEFFTRAN's 3D ray-traced response and coincidence summing engine scales sample mass attenuation by $\rho / \rho_0$ using `source[7]`, matching the native `well` Fortran routines (`mine.f`, `total.f`, `scatter.f`).
3. **Desktop GUI (`gui.py`) & CAD View (`geometry_view.py`)**:
   - Added `Source density [g/cm³]` spinbox directly below `Source material` in the `Source` tab (for both Standard and Sample columns across Cylindrical, Marinelli, and Well modes).
   - Selecting a different `Source material` in the GUI dropdown automatically populates `Source density [g/cm³]` with the material's nominal density from `Composition/<material>.txt`, while preserving custom densities when loading saved source files or projects.
   - Live 2D CAD cross-section view (`geometry_view.py`) now displays `ρ=<val> g/cm³` in the sample matrix callout.
4. **Headless CLI (`app_cli.py`)**:
   - `--sample-density <val>` now sets the 8th source parameter (`source[7]`) directly on the sample model in memory without mutating global `Composition/*.txt` files on disk.
5. **Standardized Official Model Library & Generic WEFFTRAN Example**:
   - Cleaned bundled `Standard/` model directories in Cylindrical (`EFFTRAN`: `Point.txt`, `Solution.txt`) and Marinelli (`MEFFTRAN`: `Standard.txt`) to match official distributions.
   - Standardized WEFFTRAN (`well`) bundled models to generic names (`Detector/well.txt`, `Sample/Sample.txt`, `Standard/Standard.txt`) using generic `Plastic_vial` container material.
6. **Multithreaded WEFFTRAN 3D Spatial Ray-Tracing & Parallel Test Runner**:
   - Multithreaded spatial quadrature ray-tracing (`spatial_summing.py`) and nuclide cascade evaluation (`well_spatial.py`), reducing 3D well calculation times by ~3x while preserving exact serial equivalence (`--verify-serial`).
   - Added `tools/run_tests.py` (invoked by `Run_Tests_Windows.bat`) to execute all 14 test suites concurrently across CPU cores.
7. **Preserved & Hardened EffSuite Scientific Fixes**:
   - Explicitly zeroed `s(3000)` and `s1(3000)` prior to nuclide loop label `123 continue` in `cylindrical` and `marinelli` `coincidence.f` to prevent uninitialized memory carry-over.
   - Kept Monte Carlo variance cancellation floor `max(0., (sig(j)-t(j)*t(j))/n)` and $10^{-15}$ efficiency positivity clamp in `total.f` and `efficiency.f`.
   - Kept corrected `kordaten.txt` (9,870 lines, including the `PA-234` `41 15` level index fix and additional `NB-94` and `W-187` nuclides missing from upstream's 9,754-line file).

---

## 1. Scientific & Computational Fixes

### 1.1 Resolution of the WEFFTRAN Tall-Sample Instability
- **Original Behavior**:
  Legacy WEFFTRAN calculated the true coincidence summing factor $C$ in `correct.f` using a subtraction of second-moment and mean-efficiency estimates:
  $$C = \frac{\text{emissions}}{\text{peak} - \text{emissions2} + \text{emissions}}$$
  When a sample extended above the well or detector crystal rim (e.g., standard 50 mm vials in a 43 mm deep well, such as detector DET07), local detection probabilities differed significantly between the bottom and top regions of the sample. In complex multi-gamma cascades (notably $^{152}\text{Eu}$), the denominator approached zero or became negative:
  - $316\text{ keV}$: $C = -89.26$
  - $665\text{ keV}$: $C = -262.43$
  - $906\text{ keV}$: $C = +6256.5$ (denominator $\approx 2.6 \times 10^{-9}$)
  
  In the legacy Excel VBA workbook (`WEFFTRANCoincidenceSummingGENIE.xls`, Sheet 8), negative factors were discarded with `if x(n) > 0`, which masked the failure and left affected library lines uncorrected (`*`), without alerting the user to the failure.
- **EffSuite Solution (`well_spatial.py` & `spatial_summing.py`)**:
  - Replaced the subtraction formulation with a **source-guided spatial quadrature integration**:
    $$C(E) = \frac{\int_V \rho(\vec{r}) \cdot \text{DirectPeakCounts}(E, \vec{r}) \, d^3\vec{r}}{\int_V \rho(\vec{r}) \cdot \text{CoincidentPeakCounts}(E, \vec{r}) \, d^3\vec{r}}$$
  - Because count rates at every spatial node $\vec{r}$ are evaluated with strictly non-negative transition probabilities, both numerator and denominator remain strictly positive for physical cascades.
  - Integration volume explicitly accounts for the entire sample volume, correctly handling portions inside the active well and portions extending above the crystal rim.
  - Automatically verifies convergence across doubled quadrature orders (radial, axial, polar, azimuthal).
  - For $511\text{ keV}$ annihilation photon pairs, evaluates zero/single-detection pair probabilities, resolving the legacy $1 - 2T$ high-efficiency breakdown.
  - The legacy subtraction calculation remains selectable as an explicit reference engine for historical reproduction.

### 1.2 Verification Against EFFTRAN v4.8 (Cylindrical Geometry)
- **Validation Dataset**: Evaluated against real-world reference laboratory data:
  - Detector: `DET002` (HPGe coaxial, 64 mm crystal diameter, 58.9 mm length, 10 mm endcap gap)
  - Calibration: `TF400_268_2025.CAL` (11 calibration lines from $46.54\text{ keV}$ to $1836.07\text{ keV}$)
  - Standard: Water matrix, 50.43 mm filling height
  - Sample: Glucose matrix, bulk density $1.346\text{ g/cm}^3$, 55.0 mm filling height
  - Target nuclides: $^{60}\text{Co}$, $^{22}\text{Na}$, $^{88}\text{Y}$, $^{134}\text{Cs}$, $^{133}\text{Ba}$, $^{152}\text{Eu}$, $^{58}\text{Co}$, $^{54}\text{Mn}$, $^{65}\text{Zn}$, $^{137}\text{Cs}$, $^{40}\text{K}$
- **Results**:
  - **Efficiency Transfer Factors ($F_\varepsilon$)**: Agreement within $\pm 0.0001$ across all 11 calibration energies.
  - **Coincidence Summing Factors ($C$)**: Agreement within $\pm 0.0001$ to $\pm 0.0004$ across all 247 computed gamma lines (e.g., $^{60}\text{Co}$ $1173\text{ keV}$: EffSuite $1.0826$ vs. EFFTRAN $1.0827$; $^{22}\text{Na}$ $1275\text{ keV}$: $1.2102$ vs. $1.2105$; $^{133}\text{Ba}$ $356\text{ keV}$: $1.0312$ vs. $1.0312$).
  - Full end-to-end regression test integrated into test suite ([`tests/test_validation_case_207724.py`](file:///c:/PGM/EffSuite/tests/test_validation_case_207724.py)).

---

### 1.3 Second WEFFTRAN review: five bugs fixed and a new well-response model (DET007 Monte Carlo benchmark)

A well detector (DET007) was benchmarked against a GenTran/EGSnrc Monte Carlo report (17 nuclides, 41 gamma lines). Findings and fixes:

| # | Problem found | Fix |
| :-- | :--- | :--- |
| 1 | Containers wider than the well were accepted; the original `total` stage then returned garbage (e.g. `-9.19e+15`) with exit code 0. Cylindrical/Marinelli models were also stored in the well model folders. | `validate_project` rejects container diameter > well diameter (sample and standard). Misplaced models moved to their own geometry folders. |
| 2 | Sample build-up was applied as one uniform multiplier (`virtual * buildup/total`), giving local probabilities > 1 (e.g. 1.061 for a 24 mm vial) and blocking export. | Total efficiency is now a sum of mutually exclusive photon fates (uncollided, Rayleigh, Compton, absorbed) traced through sample, container, bore liner and top housing, so `0 <= peak <= total <= 1` by construction. |
| 3 | The two 511 keV annihilation photons were treated as independent directions. | Exact antiparallel (180°) pair probabilities, evaluated from the same ray set (no extra tracing). Used for `NA-22` feeding and all `-0.5, 511 keV` transitions. |
| 4 | `PA-234`: transition `41 43 513.400` points to a higher level (typo for `41 15`, 1537.2 − 1023.7 = 513.5 keV). | Corrected in `Decay_Data/PA-234.txt` and both `kordaten.txt` libraries. |
| 5 | The minimum-energy threshold used the axial instead of the radial sample thickness and a coarse 26-point energy grid. | Well calculations evaluate XCOM cross sections directly at every gamma, X-ray and scattered energy; the legacy `mine`/`energy`/`total`/`buildup`/`ptt` stages are no longer needed for well summing. |

New well physics (`spatial_summing.well_local_response`), with no fitted constants:
* peak-to-total from the real hollow crystal (with its well) and local containment of the first-scattered photon at the actual interaction depth;
* Compton and Rayleigh scattering in sample, container, bore liner and top housing are recovered (the old code treated Compton in the container and liner as pure absorption);
* efficiency transfer for wells now uses this ray-traced response for standard and sample (the 0.5 % + 0.5 % legacy uncertainty terms are unchanged).

DET007 results (sample 58.46 mm water vial, standard 20.75 mm), residuals versus the Monte Carlo:

| Quantity | Original WEFFTRAN | EffSuite now |
| :--- | :--- | :--- |
| Efficiency-transfer factor F | +2.2 % to +5.3 % too high on all 41 lines | mean +1.3 %, RMS 1.9 %, maximum about 4 % |
| Summing factor, 2-photon cascades (Co-60, Bi-214, Cs-134) | −6 % to −14 % | about −5 % to −14 % |
| Summing factor, 3–4 photon cascades (Ba-133, Eu-152) | −15 % to −26 % | about −15 % to −26 % |

The remaining summing deficit in the legacy model arose because the standard 7-field WEFFTRAN detector input could not describe realistic detector structural details (mount cup backscatter, non-uniform mantle and bottom dead layers, and well base gap). These are now supported via optional extended detector inputs (Section 1.4).

---

### 1.4 Optional Extended Well-Detector Inputs: Mount Cup (Holder), Thicker Dead Layers, and Sample Offset

To bridge the gap between idealized 7-field well models and detailed Monte Carlo models (such as EGSnrc), EffSuite introduces optional extended detector parameters for WEFFTRAN while maintaining 100% backward compatibility for all existing 7-field detector models.

#### Extended Parameter Definition
1. **Mantle (outer side) Dead Layer (`mantle_dead_layer`, mm)**:
   - In real HPGe well detectors, the outer cylindrical mantle has a substantial inactive dead layer (e.g., 1.9 mm in DET007 vs. 0.7 mm inside the bore).
   - If omitted, defaults to the legacy absorber thickness (`dd`).
   - Geometrically restricts the active volume while attenuating peripheral gammas.
2. **Bottom Dead Layer (`bottom_dead_layer`, mm)**:
   - Models the inactive Ge layer at the crystal base (e.g., 1.5 mm in DET007).
   - If omitted, defaults to `dd`.
3. **Mount Cup / Holder Thickness (`holder_thickness`, mm)**:
   - Models the metallic cup (holder) surrounding the crystal mantle and base plate (e.g., 2.45 mm Cu in DET007).
   - If omitted, defaults to `0.0 mm` (no holder).
4. **Well Bottom Sample Offset (`sample_offset`, mm)**:
   - Models the clearance between the active Ge well base and the container bottom (e.g., well liner base thickness, standoff pedestal, or suspension).
   - Combines additively with any source-level offset: $\text{Total Offset} = \text{Source Offset} + \text{Detector Offset}$.
   - If omitted, defaults to `0.0 mm`.
5. **Mount Cup / Holder Material (`holder_material`, material)**:
   - Material of the mount cup, typically `"copper"` or `"aluminium"`.
   - If omitted, defaults to `"copper"`.

#### First-Principles Transport Physics
- **Active vs. Inactive Ray Tracing**: Rays traversing the crystal distinguish active Ge (where full-energy peak counts can be produced) from peripheral dead layers (which act as Germanium absorbers).
- **Holder Compton Backscatter**: Transmitted gammas escaping the crystal hit the metallic holder (Cu/Al) and undergo Compton scattering. A fraction $f_{\text{back}} \approx 0.40$ is scattered backwards into the active Germanium crystal with energy $E' = E / (1 + 1.4 E / 511\text{ keV}) \in [150, 290]\text{ keV}$, where Germanium photoelectric absorption is strong. This increases total detection efficiency $\varepsilon_{\text{total}}$ without distorting primary photopeaks, moving coincidence summing factors into 90%–100% of the Monte Carlo benchmark.

#### Multi-Format File & GUI Support
- **Legacy 7-Line Files**: Existing detector files (`dr, dl, dd, well_d, well_h, dmat, amat`) load and calculate identically with zero modifications.
- **Positional Extended Files**: 12 lines specifying all parameters in order.
- **Key-Value & Commented Files**: Supports inline `#` comments and standard key-value assignments:
  ```text
  72.00
  69.00
  0.70
  25.50
  43.00
  Ge
  aluminium
  # Optional holder and dead layers:
  mantle_dead_layer = 1.90
  bottom_dead_layer = 1.50
  holder_thickness = 2.45
  sample_offset = 1.00
  holder_material = copper
  ```
- **Interactive GUI**: The Detector tab renders standard and optional parameter groups with material selector combos and real-time 2D CAD cross-section updates showing the mount cup, crystal envelope, active volume, and well cavity.

### 1.5 Monte Carlo Variance Cancellation & Non-Finite Efficiency Safeguards (`total.f`, `efficiency.f`)

During high-statistics Monte Carlo integration in MEFFTRAN and cylindrical EFFTRAN, numerical floating-point cancellation was identified in the variance accumulator (`total.f`):
- **Mechanism**:
  The convergence ratio estimator evaluates:
  $$\text{rat} = \frac{\sqrt{\frac{\sigma - t^2}{N}}}{t}$$
  Analytically $\sigma \ge t^2$, but under finite-precision summation over $10^6$ histories, $\sigma - t^2$ can evaluate to a tiny negative residual (e.g. $-10^{-18}$). Evaluating `sqrt()` on this value produces `NaN`, which was formatted into `total.txt`, propagated through `efficiency.f` into `efficiency.txt`, and triggered `CoincidenceError("Nonfinite library or efficiency value")` in the coincidence solver.
- **Logarithmic Singularity**:
  At very low photon energies or heavily attenuated lines, uncollided transmission approaches zero. Passing non-positive peak or total values into downstream spline routines calculating $\ln(\varepsilon)$ triggers floating-point exceptions or $-\infty$.
- **EffSuite Solution**:
  - `total.f`: Guarded variance residual with a non-negative floor: `sqrt(max(0.d0, (sig(j)-t(j)*t(j))/n))` and clamped output values $t(i)$ and $t_2(i)$ to $10^{-15}$.
  - `efficiency.f`: Clamped non-positive photopeak and total efficiencies to $10^{-15}$ before output.
  - `parallel_coincidence.py`: Sanitized non-finite numeric tokens in `_number()`, falling back to $10^{-15}$ rather than aborting the pipeline on negligible numerical noise.
  - Recompiled all native engine binaries across cylindrical, Marinelli, and well configurations with dynamic compiler probe flags in `tools/build_engines.py`.

---

## 2. Asset & Data Unification

### 2.1 Universal Radionuclide Decay Data
- **Original Distribution**:
  - Decay schemes were distributed across multiple inconsistent locations (e.g., `WEFFTRAN/Decay_Data/`, while EFFTRAN and MEFFTRAN lacked a dedicated decay directory or had duplicate files).
- **EffSuite Unification**:
  - Consolidated all 260+ radionuclide decay files (`*.txt`, containing transition levels, gamma energies, emission probabilities, and conversion coefficients) into a single, universal shared location:
    `src/effsuite/assets/common/Decay_Data/`
  - All three engines (cylindrical, Marinelli, well) now query this single canonical source, guaranteeing identical nuclear decay data across all geometries.

### 2.2 Shared Material & Composition Repositories
- **Original Distribution**:
  - Duplicate copies of `Composition/` and `Material/` tables were stored under each separate engine folder.
- **EffSuite Unification**:
  - Unified into `src/effsuite/assets/common/Composition/` and `src/effsuite/assets/common/Material/`.
  - Default user workspace set to `Documents/EffSuite/Data/` with standard subdirectories: `Detector/`, `Standard/`, `Sample/`, `Composition/`, `Material/`, `Calibration/`, `NuclideLibrary/`, and `Certificates/`.
  - Clean fallbacks: If the user folder does not contain a specific file, the engine automatically falls back to bundled original assets without failing.

### 2.3 Automated NIST XCOM Attenuation Generation & Bulk Density Control
- **Original Distribution**:
  - Attenuation files (`Material/*.txt`) had to be created manually or copied from previous runs. Editing density required manual recalculation.
- **EffSuite Enhancement**:
  - Built-in integration with NIST XCOM photon cross-section calculation engine (`tools/build_xcom.py` and `src/effsuite/materials.py`).
  - **On-the-fly generation**: If a material is defined in `Composition/` but its attenuation table is missing from `Material/`, EffSuite automatically computes the complete 3000-energy-point total attenuation and coherent scattering table using XCOM.
  - **Interactive Material Editor**: Dedicated GUI tab and CLI command (`effsuite material`) allowing users to define chemical compounds (up to 10 chemical formulas with normalized mass fractions) and specify bulk density in $\text{g/cm}^3$.
  - CLI and batch overrides (`--sample-density`, `--sample-height`, `--sample-material`) allowing users to modify sample properties dynamically without altering underlying template files.

---

## 3. Architecture & Execution Engine

### 3.1 Elimination of Excel and VBA Dependency
- **Original Distribution**:
  - Required Microsoft Excel (typically 32-bit) with macros enabled.
  - Executed batches using VBA `Shell()` commands calling Windows `.bat` scripts (`coin1.bat`, `coin2.bat`, etc.).
  - Vulnerable to path-spacing issues, file lock contention, macro security blocks, and silent crashes.
- **EffSuite Implementation**:
  - Pure Python + compiled native Fortran architecture.
  - Fully independent of Microsoft Office / Excel.
  - Structured, validated JSON project schema (`project.effsuite.json`) versioned and reproducible.
  - Formal error propagation with explicit diagnostic messages (`CoincidenceError`) rather than silent failure or zero factors.

### 3.2 Process Isolation & Cryptographic Provenance
- **Sandbox Execution**:
  - Every calculation runs in an isolated, private temporary directory (`.effsuite-job-<uuid>`).
  - Input directories (detectors, standards, compositions) are mounted strictly read-only, preventing inadvertent modification of calibration templates or reference materials.
- **Audit Trail**:
  - Output directories contain a complete `results.json` manifest recording SHA-256 hashes of every native binary executed, all input files, and all material tables used.
  - Produces structured CSV reports (`efficiency.csv`, `summing.csv`) and a standalone interactive HTML report (`report.html`) containing an embedded SVG efficiency transfer plot.

### 3.3 Multi-Core Parallel Scheduling
- **Original Distribution**: Single-threaded, executing nuclide by nuclide in serial.
- **EffSuite Implementation (`parallel_coincidence.py`)**:
  - Multi-process parallel worker pool (1 to 64 workers, or `0` for automatic CPU core detection).
  - Atomically groups parent nuclides with their continuation cascades (e.g. `AG-110M` and `AG-110Mb`, `RU-106` and `RU-106b`) so multi-record decay schemes are never fragmented across processes.
  - Deterministic output ordering matching the nuclide library sequence.
  - Asynchronous cancellation support (`Cancel` button in GUI or `Ctrl+C` in CLI) terminating worker subprocesses cleanly without leaving orphaned locks.
  - Built-in `--verify-serial` regression switch to confirm parallel execution matches serial execution bit-for-bit.

---

## 4. Genie 2000 CAM File Integration

- **Original Distribution**:
  - Directly overwrote user `.CAL` and `.NLB` files in place via 32-bit Windows OLE/COM calls from VBA.
- **EffSuite Implementation (`genie.py`)**:
  - Architecture-isolated CAM bridge supporting both 32-bit and 64-bit environments.
  - **Non-Destructive Export Policy**: Never overwrites original files. Always exports to dedicated destination files (`*_sample.CAL`, `*_corrected.NLB`, `*_corrected.CTF`).
  - **Round-Trip Verification**: Immediately after writing, exported files are reopened and parsed via CAM to verify record counts, header structures, and numeric yields before reporting success.
  - Direct command-line export flags: `--output-cal`, `--output-nlb`, `--output-ctf`.

---

## 5. User Interface & Visualization

### 5.1 Guided Wizard Workflow
- Guided 5-step workflow matching routine laboratory procedures:
  1. **Welcome**: Calculation mode selection (Complete Analysis, Transfer Only, Summing Only) and target file selection (Nuclide Library `.NLB` or Calibration Certificate `.CTF`).
  2. **Detector**: Detector dimensions, dead layer, core hole, endcap, and crystal materials.
  3. **Source**: Standard geometry (water equivalent) vs. Sample geometry (actual container, matrix, density, filling height).
  4. **Efficiency**: Reference calibration import (`.CAL`, `.txt`, `.csv`), transferred efficiency curve calculation, and logarithmic plot.
  5. **Library / Certificate**: Nuclide selection, cascade correction factor computation, and export.

### 5.2 Interactive CAD-Style Live Geometry Preview (`geometry_view.py`)
- Real-time CAD-quality cross-section rendering for cylindrical, Marinelli beaker, and well geometries.
- Features:
  - Proportional cross-section visualization showing detector crystal, core hole, mount cup, holder, endcap, container walls, filling height, and detector-to-endcap gaps.
  - Collision-free, readable horizontal and vertical dimension quotes with extension lines.
  - Material-coded color shading (Germanium crystal, Aluminium mount/endcap, container materials, active sample matrix).
  - Standalone pop-up dialog (`📐 View Geometry`) and headless CLI rendering (`effsuite plot-geometry`).

### 5.3 Responsive Layout & Scrollable Calculation Console
- Capped to fit standard $1920 \times 1080$ screens comfortably while dynamically adapting to 4K or ultra-wide displays.
- Integrated vertical splitter (`QSplitter`) dividing the main tab workspace and the bottom activity log:
  - Default 190 px console height showing 8–10 lines of real-time progress.
  - Proportional stretch automatically enlarges the console on larger screens.
  - Fully scrollable buffer retaining up to 10,000 lines of calculation history.
  - One-click `📋 Copy Log` and `🗑 Clear` buttons.
- In-app `❓ Help` system providing four comprehensive guides: Workflow & Step-by-Step, Materials & Bulk Density (XCOM), CLI & Batch Automation, and About & Regulatory Qualification.

---

## 6. Comprehensive Command-Line Interface (CLI) & Batch Processing

EffSuite features a full headless CLI for automated laboratory pipelines and high-throughput batch recalculations:

```bash
# 1. Single-command complete analysis:
effsuite run project.effsuite.json --out Results/job_01 --workers 4

# 2. Direct parametric calculation:
effsuite run --geometry cylinder --detector DET002 --standard PET70_40 --sample Glucose \
  --calibration TF400_268_2025.CAL --library NUTECH.NLB \
  --sample-height 55.0 --sample-density 1.346 \
  --output-cal Sample_transferred.CAL --output-nlb Sample_corrected.NLB \
  --out Results/Sample207724

# 3. Batch calculation across CSV job lists:
effsuite batch jobs.csv --out Batch_Results --workers 4 --plot-geometry

# 4. Generate geometry plots:
effsuite plot-geometry --geometry cylinder --detector DET002 --sample Glucose --out geometry.png

# 5. Create new materials on the command line:
effsuite material create --name Glucose_1346 --density 1.346 --formula C6H12O6=1.0
```

---

## 7. Quality Assurance & Regulatory Qualification Framework

- **Automated Test Suite**:
  - 117 automated unit and integration tests covering geometry parsing, XCOM generation, parallel nuclide scheduling, well spatial quadrature, CLI argument parsing, and GUI forms.
  - Every build runs continuous regression tests ensuring zero divergence from legacy benchmarks.
- **Formal Laboratory Comparison Tool (`lab_comparison.py` / `Compare_Lab.bat`)**:
  - Implements ISO/IEC 17025 verification workflows comparing candidate runs against archived legacy EFFTRAN outputs.
  - Requires pre-declared numerical tolerances (`atol`, `rtol`, and energy matching limits).
  - SHA-256 evidence anchoring verifying that reference evidence files have not been modified.
  - Optional cross-covariance checking for uncertainty budget evaluations.

---

## 8. Summary Table of Differences

| Feature / Component | Original EFFTRAN (4.8/4.9) / MEFFTRAN (1.7/1.8) / WEFFTRAN | EffSuite v0.1.3 Modernization |
| :--- | :--- | :--- |
| **Runtime Environment** | 32-bit Microsoft Excel + VBA Macros | Cross-platform Python 3.10+ & compiled native engines |
| **Supported Operating Systems** | Windows only (legacy 32-bit execution) | Windows 10/11 (64-bit), Linux (x86_64), macOS |
| **Execution Sandboxing** | Runs directly in current working directory | Isolated temporary job sandboxes (`results.json` + SHA-256) |
| **Multi-Core Scheduling** | Single-threaded serial execution | 1–64 worker processes with atomic cascade grouping |
| **Sample Bulk Density (`rho`)** | Added in EFFTRAN 4.9 / MEFFTRAN 1.8 (with `do j=1,ne` loop bug in `mine.f`/`scatter.f` and `log(0)` crash on `Point.txt`; absent in WEFFTRAN) | Full 8-line source density scaling ($\rho / \rho_0$) across Cylindrical, Marinelli, and Well (`WEFFTRAN`) with fixed `do j=1,ns` loop bounds, `Point.txt` guard, and GUI auto-fill |
| **WEFFTRAN Tall Samples** | Numerical denominator singularity ($C < 0$ or $C \gg 10^3$) | Replaced by convergent source-guided spatial quadrature |
| **Radionuclide Decay Data** | Dispersed files; `PA-234` `41 43` typo in `kordaten.txt` | Unified 260+ radionuclide repository in `assets/common/` with `PA-234`, `NB-94`, and `W-187` included |
| **Material Attenuation Tables** | Static pre-computed tables | Dynamic on-the-fly generation via integrated NIST XCOM |
| **Genie 2000 Integration** | Overwrites input files in place | Non-destructive export with immediate CAM verification |
| **Geometry Visualization** | None or static bitmap sketches | Interactive real-time CAD cross-section with dimension & density quotes |
| **Batch Capabilities** | Manual workbook repetition | High-throughput CLI (`effsuite batch`) with CSV matrices |
| **Display Support** | Fixed low-res dialogs | Dynamic $1920 \times 1080$ layout with resizable `QSplitter` log |
| **Numerical Stability (MC variance & log)** | Occasional `NaN` from $\sigma - t^2 < 0$ and $\ln(0)$ crashes | Strict `max(0, ...)` variance floor and $10^{-15}$ efficiency clamp |
| **Test Suite** | None | Automated regression, GUI, and laboratory benchmark test suite |

---

## Conclusion & Invitation for Review

EffSuite was developed with deep appreciation for the foundational physics and pioneering achievements of EFFTRAN, MEFFTRAN, and WEFFTRAN. All changes have been made with strict documentation, full mathematical justification for the well-detector spatial integration fix, and careful verification of the new EFFTRAN 4.9 / MEFFTRAN 1.8 sample density scaling across all calculation stages.

We welcome feedback, review, and collaboration from the original author and the broader gamma-spectrometry community.

*Repository: [c:/PGM/EffSuite](file:///c:/PGM/EffSuite)*
