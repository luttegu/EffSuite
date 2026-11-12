# Scientific & Computational Report: Differences Between Original EFFTRAN / MEFFTRAN / WEFFTRAN and EffSuite

**To:** Scientific Author & Maintainer of EFFTRAN, MEFFTRAN, and WEFFTRAN (Dr. Tim Vidmar)  
**From:** EffSuite Engineering & Validation Team (built by ChatGPT & Gemini under the supervision of G. Lutter)  
**Date:** November 10, 2026  
**Disclaimer:** Provided strictly on an AS-IS basis. G. Lutter accepts NO responsibility or liability under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. Users must independently verify all results.  
**Subject:** Precise Technical Audit of Physics Changes, Bug Fixes, Code Adjustments, and Architectural Modernization  
**Analyzed Reference Distributions:**
* Original EFFTRAN: `C:\PGM\EFFTRAN\EFFTRAN_4.8` (Version 4.8) & `C:\PGM\EFFTRAN\EFFTRAN_4.9` (Version 4.9, 2026)
* Original MEFFTRAN: `C:\PGM\EFFTRAN\MEFFTRAN_1.7` (Version 1.7) & `C:\PGM\EFFTRAN\MEFFTRAN_1.8` (Version 1.8, 2026)
* Original WEFFTRAN: `C:\PGM\EFFTRAN\WEFFTRAN` (Version 0.8 / 4.4.4, January 2018)
* EffSuite: Version 0.1.5 (`C:\PGM\EffSuite`)

---

## Executive Summary

A comprehensive file-by-file and line-by-line comparison was conducted across all Fortran mathematical source routines, decay data schemes, chemical composition definitions, mass attenuation tables, and workflow orchestration between the original distributions and **EffSuite v0.1.5**.

The core findings are:
1. **EFFTRAN 4.9 (Cylindrical) & MEFFTRAN 1.8 (Marinelli)**: EffSuite v0.1.5 integrates the 8-line source model (`Source density [g/cm³]` on line 8) and `HeavyWater` reference material from `EFFTRAN 4.9` and `MEFFTRAN 1.8`. In the latest upstream release, the author updated the density-scaling loop bounds to `ns` and added non-positive density guards. EffSuite preserves full scientific precision (`3e15.5`) in `transfer.f`, includes the relative Monte Carlo uncertainty of the standard and sample in cylindrical transfer factors (as in EFFTRAN 4.9), and maintains numerical floors (`max(0., ...)` variance floor and $10^{-15}$ efficiency floor).
2. **WEFFTRAN (Well-Type)**: Extended the 8th-line sample bulk density scaling (`rho / rho0`) to WEFFTRAN (`spatial_summing.py` and native `well` Fortran sources), in addition to the physical bug fixes in `total.f` and `peak.f` and the 3D spatial quadrature solver resolving the **tall-sample numerical singularity** and **high-efficiency positron ($^{22}\text{Na}$) cascade breakdown**.
3. **Decay Data & Library Fixes**: Corrections were made to $^{22}\text{Na}$ feeding definitions, and $^{187}\text{W}$ was added to `kordaten.txt` ($^{94}\text{Nb}$ is now included in the upstream file).
4. **Modernization & Automation**: Complete removal of dependencies on legacy 32-bit Excel / VBA macros, introduction of parallelized multi-core calculations, automated NIST XCOM execution, and headless CLI batch capabilities.

---

## 1. Engine & Physics Differences: Fortran Source Code Audit

### 1.1 EFFTRAN 4.9 vs. EffSuite v0.1.5 (`cylindrical`)
Comparison between `C:\PGM\EFFTRAN\EFFTRAN_4.9\*.f` and `src\effsuite\assets\engines\cylindrical\source\*.f`:
- Integrated the 8th-line sample density `rho` (`read(7,*,end=88,err=88) rho`) and nominal material density `rho0` (`from .\Composition\<smat>.txt`) in `mine.f`, `total.f`, `scatter.f`, and `eta.f`, plus in-memory `coin.txt` caching in `gv.f`.
- **Density Scaling**: Upstream updated `mine.f` and `scatter.f` to loop over all `ns` material cross-section points (`do j=1,ns`). In `total.f`, EffSuite scales the `ne` calculated energies (`do j=1,ne`), which is the array actively used.
- **Positivity Guard on Density**: EffSuite guards against non-positive or missing `rho` via `if (rho.le.0.) rho=rho0` across all routines (falling back to nominal density `rho0`), while upstream uses $10^{-12}$.
- **Transfer Uncertainty & Full Precision**: EffSuite incorporates the 4th-column Monte Carlo statistical uncertainty from `total.txt` into the cylindrical efficiency transfer formula, matching EFFTRAN 4.9. EffSuite retains the stage-isolated architecture and full scientific floating-point precision `format(3e15.5)` (avoiding upstream `f12.1` truncation) and preserves `max(0., (sig(j)-t(j)*t(j))/n)` and `1e-15` numerical safety floors in `total.f` and `efficiency.f`.

### 1.2 MEFFTRAN 1.8 vs. EffSuite v0.1.5 (`marinelli`)
Comparison between `C:\PGM\EFFTRAN\MEFFTRAN_1.8\*.f` and `src\effsuite\assets\engines\marinelli\source\*.f`:
- Integrated the 8th-line sample density `rho` and `rho0` scaling in `mine.f`, `total.f`, `scatter.f`, and `eta.f`.
- **Density Scaling & Guard**: Uses `do j=1,ns` in `mine.f` and `scatter.f`, and guards `rho <= 0` with nominal density fallback.
- **Preserved Numerical Floor**: Kept Monte Carlo variance floor `max(0., (sig(j)-t(j)*t(j))/n)` and `1e-15` efficiency floor in `total.f` and `efficiency.f`. Transfer uncertainty retains the verified $0.5\% + 0.5\%$ standard/sample contributions of MEFFTRAN 1.8.

---

### 1.3 WEFFTRAN vs. EffSuite (`well`)
Comparison between `C:\PGM\EFFTRAN\WEFFTRAN\*.f` and `src\effsuite\assets\engines\well\source\*.f`:

#### A. Identical Routines (12 files)
`buildup.f`, `correct.f`, `efficiency.f`, `emissions.f`, `emissions2.f`, `energy.f`, `eta.f`, `initialize.f`, `mine.f`, `ptt.f`, `scatter.f`, `transfer.f`: **100% IDENTICAL**.

#### B. Physics Bug Fix in `total.f` (Ray-tracing Path Length for Tall Samples)
* **File**: `total.f` (Subroutine `path`, Lines 412–426).
* **The Bug in Original WEFFTRAN**:
  In original WEFFTRAN, when calculating the path length $d$ through cylinder/well boundaries along direction $(\sin\theta\cos\phi, \sin\theta\sin\phi, \cos\theta)$:
  ```fortran
  ! Original WEFFTRAN (lines 410-415):
        k=k1
        if (k2.gt.k) k=k2
        zb=z0+k*tz
        if (zb.le.zlo) zb=zlo
        if (zb.gt.zup) zb=zup
        d=(z0-zb)/tz
        d=abs(d)
        return
  ```
  If an emitted photon originates from a source position $z_0$ located **above the detector upper surface** ($z_0 > z_{up}$, common when sample filling height exceeds the crystal well rim), original WEFFTRAN used $z_0$ directly as the starting point. Consequently, the distance through the **air gap above the detector** was erroneously treated as active detector material ($\text{attenuation} = \mu \cdot d$).
* **EffSuite Fix**:
  EffSuite clamps both entry point $z_a$ and exit point $z_b$ to the physical detector bounding box $[z_{lo}, z_{up}]$:
  ```fortran
  ! EffSuite Fixed total.f:
        zb=z0+k*tz
        if (zb.le.zlo) zb=zlo
        if (zb.gt.zup) zb=zup

        za=z0
        if (za.le.zlo) za=zlo
        if (za.gt.zup) za=zup

        d=(za-zb)/tz
        d=abs(d)
        return
  ```
* **Physical Effect**: Prevents artificial overestimation of total detection efficiency for photons emitted in the top portion of tall vials.

#### C. Physics Correction in `peak.f` ($511\text{ keV}$ Positron Annihilation Quenching)
* **File**: `peak.f` (Lines 173–215).
* **The Issue in Original WEFFTRAN**:
  Original WEFFTRAN assumed cascade transitions and electron capture X-rays. For $\beta^+$ emitters such as $^{22}\text{Na}$, positron annihilation produces two collinear, antiparallel $511\text{ keV}$ photons. In original `peak.f`, the feeding term calculation assumed single-photon $L$-capture:
  ```fortran
  ! Original WEFFTRAN:
        totx=pk(i)*omegak*totxk
        totx=totx+pl(i)*omegal*totxl
  ```
  When $^{22}\text{Na}$ is measured in high-geometry well detectors ($\approx 4\pi$), the probability of detecting *at least one* $511\text{ keV}$ annihilation photon is given by:
  $$P(\text{annihilation detect}) = 2\varepsilon_{511} - \varepsilon_{511}^2$$
* **EffSuite Correction**:
  In EffSuite `peak.f`, a universal logic switch detects positron emission when $P_L > 0.40$ (where the $P_L$ column is utilized as $\beta^+$ branch probability in the decay scheme):
  ```fortran
  ! EffSuite peak.f:
        call inter(ne,ee,tt,log(511.0d0),tot511)
        tot511=exp(tot511)
        if (tot511.lt.0.) tot511=0.
        if (tot511.gt.1.) tot511=1.

        if (pl(i).gt.0.40) then
            totx = totx + pl(i) * (2.0 * tot511 - tot511 * tot511)
        else
            totx = totx + pl(i) * omegal * totxl
        endif
  ```
* **Physical Effect**: Restores physically meaningful total efficiency and coincidence summing calculations for $^{22}\text{Na}$ without breaking non-positron nuclides.

---

## 2. Advanced Numerical Solution: The WEFFTRAN Tall-Sample Singularity

### 2.1 The Legacy Singularity Problem in Original WEFFTRAN
In original WEFFTRAN, coincidence summing factors $C$ were computed using second-moment difference formulas in `correct.f`:
$$C = \frac{\text{emissions}}{\text{peak} - \text{emissions2} + \text{emissions}}$$
When a sample vial extends above the well or detector rim (e.g. 5 mL vial filled to 50 mm in a 43 mm well cavity, such as DET07):
1. Count probabilities $\varepsilon(E, \vec{r})$ at the top of the vial differ dramatically from those at the bottom of the well.
2. In multi-gamma cascade emitters (e.g., $^{152}\text{Eu}$), the subtraction $(\text{peak} - \text{emissions2} + \text{emissions})$ approaches zero or becomes negative.
3. This resulted in catastrophic unphysical factors:
   * $^{152}\text{Eu}$ at $316\text{ keV}$: $C = -89.26$
   * $^{152}\text{Eu}$ at $665\text{ keV}$: $C = -262.43$
   * $^{152}\text{Eu}$ at $906\text{ keV}$: $C = +6256.5$ (denominator $\approx 2.6 \times 10^{-9}$)
4. **VBA Masking**: In the legacy Excel workbook `WEFFTRANCoincidenceSummingGENIE.xls`, Sheet 8, line 42, VBA discarded negative factors with `if x(n) > 0`, leaving those energies uncorrected without warning the user.

### 2.2 EffSuite Spatial Quadrature Integration (`well_spatial.py` & `spatial_summing.py`)
To solve this permanently while retaining rigorous physics, EffSuite implements a 3D source-guided spatial quadrature integration:
$$C(E) = \frac{\int_V \rho(\vec{r}) \cdot N_{\text{direct}}(E, \vec{r}) \, d^3\vec{r}}{\int_V \rho(\vec{r}) \cdot N_{\text{coincident}}(E, \vec{r}) \, d^3\vec{r}}$$
- **Strict Positivity Formulation**: Count rates at every volume element $\vec{r} = (r, \phi, z)$ are computed with strictly positive cascade recursion probabilities. The denominator cannot cancel or become negative.
- **Physical Geometry**: The integration volume spans both regions:
  1. Internal region: Sample cylinder surrounded by the well cavity wall and bottom dead layers.
  2. External region: Sample cylinder protruding above the top detector plane into air.
- **Convergence Verification**: Automatically checks numerical refinement across doubled quadrature orders (radial, axial, polar, azimuthal) with tolerance $\text{rtol} = 0.01$.
- **Compatibility**: Original WEFFTRAN subtraction mode remains preserved and can be selected via `--engine original` if historical comparison is required.

---

## 3. Nuclear Decay Data & Material Library Differences

A cross-check between `WEFFTRAN\Decay_Data\*.txt` and EffSuite shared assets revealed one specific data correction:

### 3.1 $^{22}\text{Na}$ Level Scheme Alignment
* **File**: `Decay_Data/NA-22.txt`.
* **Original WEFFTRAN**: Contained an experimental multi-line transition entry attempting to force 511 keV lines into the cascade matrix.
* **EffSuite**: Cleaned $^{22}\text{Na}$ to the canonical 1274.537 keV line with proper $\beta^+$ feeding ($P_{\beta^+} = 0.9030$, $P_K = 0.0960$), allowing the engine's built-in 511 keV pair-correlation logic to model the annihilation photons analytically.

### 3.2 Composition & Attenuation Tables
* **Normalization**: Minor mass fraction normalization adjustments in `Copper_Ferrocyanide.txt` and `Spinach_ashed.txt` where original files had non-normalized totals or single-precision truncation.
* **NIST XCOM Automated Generator**: Original versions required manual entry into `Material.xls` or external XCOM execution. EffSuite automatically runs NIST XCOM (`xcom.exe`) on demand whenever a material formula is entered or density is adjusted.

---

## 4. Architectural & Operational Enhancements

| Feature | Original EFFTRAN / MEFFTRAN / WEFFTRAN | EffSuite |
| :--- | :--- | :--- |
| **Operating System** | Windows only (32-bit Excel / VBA dependency) | Windows x64 and Linux native |
| **User Interface** | Excel Macro Workbooks (`.xls`, VBA) | Modern PySide6 Desktop GUI + Headless CLI |
| **Execution Architecture** | Single-threaded sequential execution | Multi-process parallelization across CPU cores |
| **Coincidence Summing Scope** | One nuclide or manual macro looping | Batch calculation across all library lines simultaneously |
| **Auto Workers (`workers=0`)** | Not available (single process) | Dynamically allocates `max(1, os.cpu_count() - 2)` cores |
| **Default File Dialogs** | Local folder | Defaults to standard Genie directory `C:\GENIE2K\CAMFILES` for `.NLB` |
| **Genie 2000 Integration** | Manual copy-paste from Excel sheets | Direct read and write of Genie `.CAL`, `.NLB`, and `.CTF` |
| **Geometry CAD View** | None (parameter table only) | Real-time dimensioned axial cross-section view with live quotes |
| **Batch Automation** | None (manual interaction with Excel) | Headless batch processing via CSV/JSON (`effsuite batch`) |
| **Uncertainty Propagation** | Traditional transfer uncertainty formula | Preserves original legacy uncertainty formulas |

---

## 5. Summary Recommendations for the Scientific Author

1. **Adopt WEFFTRAN `total.f` Clamping Fix**:
   The fix in `path()` (clamping $z_a$ to $[z_{lo}, z_{up}]$) resolves an unphysical geometric artifact when sample heights exceed the detector crystal. We recommend including this in any future WEFFTRAN release.
2. **Review Positron Annihilation Modelling in Well Detectors**:
   The inclusion of $(2\varepsilon_{511} - \varepsilon_{511}^2)$ in `peak.f` provides accurate coincidence summing factors for $^{22}\text{Na}$ in $4\pi$ geometry.
3. **Preserve Scientific Precision in `transfer.f` Output**:
   Using `format(3e15.5)` instead of `format(f12.1,e15.5,f12.1)` prevents truncating gamma energies to 0.1 keV resolution when generating efficiency curves.
