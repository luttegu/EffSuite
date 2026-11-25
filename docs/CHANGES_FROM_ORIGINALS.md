# EffSuite Compared with the Original EFFTRAN, MEFFTRAN and WEFFTRAN

*EffSuite v0.5.2 (November 2026). For the original author (Dr. Tim Vidmar), maintainers and scientific reviewers.*

> **Disclaimer:** Provided strictly on an AS-IS basis. G. Lutter accepts NO responsibility or liability under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. Users must independently verify all results.

This document lists every difference between EffSuite and the original
programs: physics and source changes, defects found in the originals, and
features that have no original equivalent. It merges the former
`EFFTRAN_MEFFTRAN_WEFFTRAN_CHANGES.md` and `SCIENTIFIC_AUDIT_REPORT.md`. The
release-by-release history is in [RELEASE_NOTES.md](../RELEASE_NOTES.md), and
the test evidence in [VALIDATION.md](VALIDATION.md).

**Reference distributions compared** (`C:\PGM\EFFTRAN`):

| Program | Version compared | EffSuite engine folder |
|---|---|---|
| EFFTRAN (cylindrical samples) | 5.1 (November 2026); earlier 4.8, 4.9 and 5.0 | `src/effsuite/assets/engines/cylindrical` |
| MEFFTRAN (Marinelli beakers) | 2.0 (November 2026); earlier 1.7, 1.8 and 1.9 | `src/effsuite/assets/engines/marinelli` |
| WEFFTRAN (well detectors) | 0.8 (2018; Fortran stages "4.4.4 2016") | `src/effsuite/assets/engines/well` |

---

## Summary

* **Cylinder and Marinelli.** The Fortran engines are the original EFFTRAN 5.1
  and MEFFTRAN 2.0 routines, with small numerical safeguards (sections 1.3 and
  1.4) and a higher-precision output format (section 1.9 for the update). The physics model is unchanged.
  A Python layer runs the stages in private folders and runs nuclides in
  parallel.
* **Well detectors.** The original subtraction formula for the summing factor
  can give negative or near-singular factors for tall samples (section 2.2).
  EffSuite replaces it with a spatial integration of predicted counts and a
  ray-traced well response (sections 2.3 and 2.4). The legacy calculation
  remains available for comparison.
* **New in EffSuite** (section 3): an uncertainty for every summing factor,
  direct Genie 2000 and GammaVision file handling, XCOM material generation, a
  desktop GUI and a CLI replacing the Excel workbooks, and parallel,
  reproducible, hashed calculations.

---

## 1. Cylinder (EFFTRAN 5.1) and Marinelli (MEFFTRAN 2.0) engines

### 1.1 Sample bulk density (8th source line)

Added upstream in EFFTRAN 4.9 and MEFFTRAN 1.8. Source models gained an 8th
line with the bulk density ρ in g/cm³ (for example `1.40` in `Soil.txt` and
`0.00` in `Point.txt`). `mine.f`, `total.f`, `scatter.f` and `eta.f` read ρ,
read the nominal density ρ₀ from line 1 of `Composition/<material>.txt`, and
shift the logarithmic attenuation coefficients:

  ln μ(E, ρ) = ln μ(E, ρ₀) + ln(ρ/ρ₀), that is μ(E, ρ) = μ(E, ρ₀) · ρ/ρ₀.

EffSuite has the same model, with these differences:

| Item | Upstream | EffSuite |
|---|---|---|
| Missing or non-positive ρ (7-line file, `Point.txt` with `vacuum`) | replaced by 10⁻¹² (a 7-line file behaves like a vacuum) | replaced by the nominal ρ₀ (`if (rho.le.0.) rho=rho0`); ρ₀ floored at 10⁻¹⁵ |
| Loop bound in `total.f` | EFFTRAN 5.0 line 152 (5.1 line 154, MEFFTRAN 2.0 line 152) scales `mus(j)` for `j=1,ns` (rows of the attenuation table) although `mus` holds the `ne` interpolated energies | `do j=1,ne`, the array actually used |
| Loop bound in `mine.f`, `scatter.f` | first 4.9/1.8 sources used `do j=1,ne` (`ne` = 0 in `mine.f`, 25 in `scatter.f`, so ρ was partly ignored); **corrected upstream** to `ns` | `do j=1,ns` |
| Well geometry | not available in WEFFTRAN | same scaling added to the well engine and to the spatial model |

Check: `Water` at ρ = 2.0 g/cm³ gives the same results as `heavy`
(H₂O, ρ₀ = 2.0 g/cm³, a MEFFTRAN 1.9 material kept as a test fixture) to 6
decimal places in all three geometries. 7-line source
files and older projects still load, with ρ = ρ₀.

### 1.2 Efficiency-transfer uncertainty

From EFFTRAN 4.9 and MEFFTRAN 1.9 on, `total.f` writes a fourth column: the
relative Monte Carlo statistical uncertainty *s* of the total efficiency.
`transfer.f` combines it with the reference calibration uncertainty
*u*<sub>ref</sub> (percent):

  *u* = √(*u*<sub>ref</sub>² + (100 *s*<sub>std</sub>)² + (100 *s*<sub>sample</sub>)²)

EffSuite uses this formula for cylinder and Marinelli. MEFFTRAN 1.8 and
WEFFTRAN used fixed 0.5 % + 0.5 % terms; these remain only for wells. None of
these values is a complete uncertainty budget: detector dimensions,
positioning and decay data are not included.

### 1.3 Numerical safeguards in `total.f` and `efficiency.f`

* **Variance cancellation.** The convergence estimator evaluates
  √((σ − t²)/N)/t. Analytically σ ≥ t², but over 10⁶ histories σ − t² can
  round to a tiny negative value. Its square root was `NaN`, which travelled
  through `total.txt` and `efficiency.txt` into the coincidence step.
  EffSuite uses `sqrt(max(0., (sig(j)-t(j)*t(j))/n))`.
* **Logarithm of zero.** At very low energy, or for strongly attenuated
  lines, efficiencies approach zero, and the logarithmic interpolation fails.
  EffSuite clamps output efficiencies at 10⁻¹⁵. Upstream later added a 10⁻¹²
  guard.
* **No silent replacement.** Since v0.3.0, a `NaN` or infinite number in any
  engine output stops the calculation with an error. It is no longer replaced
  by 10⁻¹⁵ in Python (`parallel_coincidence._number`).
* **Uninitialised arrays.** `s(3000)` and `s1(3000)` are zeroed explicitly
  before the nuclide loop in `coincidence.f`.

### 1.4 Output precision

* **`coincidence.f`.** The factor format `f15.3` is changed to `e23.15` at
  compile time (`tools/build_engines.py`), so that small factors keep their
  digits. Example: the Co-60 2506 keV sum peak, C ≈ 8·10⁻⁷, which `f15.3`
  prints as `0.000`. The arithmetic is unchanged.
* **`transfer.f`.** EffSuite keeps `format(3e15.5)`. Upstream EFFTRAN 4.9/5.0
  uses `format(f12.1,e15.5,f12.1)`, which rounds energies to 0.1 keV
  (46.539 keV becomes 46.5 keV). It computes in single precision and in the
  same order of operations as EFFTRAN 5.1 and MEFFTRAN 2.0, so its
  efficiencies equal the upstream ones digit for digit.

### 1.5 Program organisation

* **Renamed programs.** In EFFTRAN 5.0 and MEFFTRAN 1.9 the batch runner
  became `summing.f`, and the coincidence routine became `coin.f` (earlier
  `coin.f` and `coincidence.f`). EffSuite runs the stages itself and calls the
  coincidence routine (built as `coincidence.exe`) directly; no batch runner
  or shell script is used.
* **Stage-isolated transfer.** Upstream EFFTRAN 4.9/5.0 `transfer.f` launches
  `total.exe` itself. In EffSuite, the Python layer runs `total` for the
  standard and for the sample, then runs `transfer`.
* **`gv.f`.** Upstream 4.9 loads `coin.txt` once into memory. EffSuite keeps
  that change with array bounds protection, but does not use `gv.f` for
  GammaVision export (section 3.2).

### 1.6 Defect in the MEFFTRAN 1.9 detector format

**Fixed upstream in MEFFTRAN 2.0**: its `Efficiency Transfer.xlsm`, the
bundled models and all stages (`mine.f`, `total.f`, `ptt.f`, `eta.f`) use
16 lines again, without absorber. EffSuite still accepts 19-line files written
by MEFFTRAN 1.9. The description below applies to MEFFTRAN 1.9.

The MEFFTRAN 1.9 `Efficiency Transfer.xlsm` writes a 19-line
`detector.txt`, with absorber diameter, thickness and material, as for
cylinders. `ptt.f` and `eta.f` were updated to read 19 lines, but `mine.f` and
`total.f` and the bundled `Detector/*.txt` models still use 16 lines:

```
At line 212 of file mine.f (unit = 7)
Fortran runtime error: Cannot open file '.\Composition\100.00.txt': No such file or directory
```

Conversely, `ptt.exe` stops at end of file on a 16-line model. EffSuite
accepts either format and writes each engine exactly the lines it reads
(`model_io.py`; test
`test_detector_geometry_cross_compatibility_efftran_and_mefftran`).

### 1.7 Decay data (`kordaten.txt`)

The cylinder and Marinelli engines read the same `kordaten.txt` (9,870
lines). It contains Nb-94, which upstream added in 5.0/1.9, and also W-187,
which upstream still lacks. Pa-234 keeps the upstream transition `41 43`.
Apart from W-187 and the position of the Nb-94 record, the nuclide records
are identical to those of the EFFTRAN 5.1 / MEFFTRAN 2.0 `kordaten.txt`.
The bundled materials are the 19 of the EFFTRAN 5.1 and MEFFTRAN 2.0
distributions, unchanged from 5.0/1.9. MEFFTRAN 1.9's `heavy.txt` (H₂O,
ρ₀ = 2.0 g/cm³) is not in MEFFTRAN 2.0 and was removed in 0.5.0, as was the
earlier `HeavyWater.txt` (identical composition) in 0.3.2.

The cylinder and Marinelli Detector, Sample and Standard models are the
original EFFTRAN 5.0 / MEFFTRAN 1.9 ones, unchanged in EFFTRAN 5.1 /
MEFFTRAN 2.0. The original WEFFTRAN distribution
has no usable well-format models (only EFFTRAN-format leftovers), so EffSuite
bundles its own well models, which are always kept: `Detector/well.txt`
(Ge crystal, aluminium end cap), `Sample/Sample.txt` and
`Standard/Standard.txt` (water in a `polystyrene` vial; `Plastic_vial` until
0.3.1, which is not an original material).

### 1.8 Compilation

All 35 native Windows programs (10 cylinder, 10 Marinelli and 15 well
programs, including the EffSuite `raytrace`) are built with GNU Fortran 15.2.0 (w64devkit). The Linux cylinder and Marinelli programs (rebuilt for
EFFTRAN 5.1 and MEFFTRAN 2.0) are built with GNU Fortran 14.4, as are the Linux
well programs `mine`, `total`, `scatter` and `efficiency`; the other Linux
well programs with GNU Fortran 13.3. This replaced MinGW GCC 7.3 builds that failed on Windows
with `WinError 623` (DLL relocation). The flags `-finit-local-zero` and
`-fno-strict-aliasing` make the legacy Fortran 77 deterministic; the 13.3
Linux builds were made without them. Source, binary hashes and commands are
in `assets/engines/*/bin/*/build_manifest.json`.

Until this update, the Linux cylinder and Marinelli programs were still the
v0.1.1 builds, older than the EFFTRAN 4.9 / MEFFTRAN 1.8 sources (no bulk
density, three-column `total.txt`). The Linux well programs `mine`, `total`,
`scatter` and `efficiency` were also v0.1.1 builds, older than their sources
(density scaling, path-length fix of section 2.1, 10⁻¹⁵ floor); they are
rebuilt with GNU Fortran 14.4 from the unchanged sources. For a 60 mm water
sample at 1.5 g/cm³ in the bundled well detector, their output files now
equal the Windows ones.

`tools/build_engines.py` puts the compiler's own folder first on `PATH`.
Without this, another MinGW on `PATH` (for example `C:\EGSnrc\mingw64\bin`)
supplies an older `ld.exe` (binutils 2.30), whose executables Windows refuses
to start (`WinError 193`).

### 1.9 Update to EFFTRAN 5.1 and MEFFTRAN 2.0

Both distributions replace ActiveX controls with Form controls in the Excel
workbooks (README). The 5.0 and 1.9 sources were not kept, so the 5.1 and
2.0 sources were compared with the previous EffSuite sources, leaving out the
EffSuite changes of sections 1.1 to 1.4:

| Program | Difference from the previous EffSuite sources | EffSuite |
|---|---|---|
| EFFTRAN 5.1 | None in the stages EffSuite runs (declaration order and `if` formatting only). | Sources taken from 5.1 with the changes of sections 1.1, 1.3 and 1.4; `buildup.f`, `energy.f` and `ptt.f` are byte-identical to 5.1. The Windows programs give byte-identical output to the previous build; `transfer.f` changed (section 1.4). |
| MEFFTRAN 2.0 | `buildup.f`, `efficiency.f`, `eta.f` and `scatter.f` use single precision (`real`), as EFFTRAN does; the previous sources used `double precision`, as MEFFTRAN 1.6.1 did. `total.f` keeps `double precision` for the geometry and attenuation data, but its Monte Carlo tallies (`t`, `t2`, `sig`, `s`, `u1`, `u2`, `smax`, `unc`) are `real` and hold 1000 energies instead of 100. `mine.f` has no unused absorber variables. 16-line detector (section 1.6). | Sources taken from 2.0 with the changes of sections 1.1, 1.3 and 1.4. `buildup.f`, `energy.f` and `ptt.f` are byte-identical to 2.0. |

Check on the example of the MEFFTRAN 2.0 distribution (`detector.txt`,
`source.txt`): the EffSuite Windows programs reproduce `total.txt`,
`scatter.txt`, `buildup.txt`, `eta.txt`, `efficiency.txt` and `ptt.txt` of the
upstream 2.0 programs exactly, and `coin.txt` to the upstream `f15.3` rounding.
For the transfer examples of both distributions
(`Standard_Efficiency/standard.txt`, `standard.txt`, `sample.txt`), all 16
transferred efficiencies equal those of the upstream `transfer.exe`; energies and uncertainties agree after its `f12.1` rounding.
Compared with the earlier EffSuite double-precision build, total efficiency
changes by 2·10⁻⁵ (relative), peak efficiency by up to 0.35 %, P/T by up to
0.43 % and *C* by up to 6·10⁻⁴ (0.2 %). The Linux build
gives the same files, except 5 of 5,665 summing factors that differ by
1·10⁻⁷ (relative). The DET952 Marinelli validation case still agrees with the
laboratory MEFFTRAN results within 0.002.

---

## 2. Well detectors (WEFFTRAN)

### 2.1 Fortran stages

Comparison of `C:\PGM\EFFTRAN\WEFFTRAN\*.f` with `assets/engines/well/source`:

| Files | Status |
|---|---|
| `buildup.f`, `correct.f`, `emissions.f`, `emissions2.f`, `energy.f`, `eta.f`, `initialize.f`, `ptt.f`, `transfer.f` | identical (apart from line endings) |
| `mine.f`, `scatter.f` | bulk-density scaling added (section 1.1) |
| `efficiency.f` | peak efficiencies floored at 10⁻¹⁵ |
| `total.f` | density scaling, and path-length fix for tall samples (below) |
| `peak.f` | annihilation-photon term for β⁺ emitters (below) |

**`total.f`, subroutine `path`.** The original takes the source position
*z*₀ directly as the entry point. For a source point above the detector
(*z*₀ > *z*<sub>up</sub>, common when the filling height exceeds the well
rim), the air path above the detector was counted as detector material.
EffSuite clamps the entry point as well as the exit point to
[*z*<sub>lo</sub>, *z*<sub>up</sub>]:

```fortran
      zb=z0+k*tz
      if (zb.le.zlo) zb=zlo
      if (zb.gt.zup) zb=zup
      za=z0
      if (za.le.zlo) za=zlo
      if (za.gt.zup) za=zup
      d=(za-zb)/tz
```

**`peak.f`, positron emitters.** The original treats the PL column as
L-capture X-rays. For a β⁺ emitter such as Na-22 in a near-4π well, the
relevant probability is that *at least one* of the two 511 keV photons is
detected, 2ε₅₁₁ − ε₅₁₁². When PL > 0.40 (the PL column is then the β⁺
branch), `peak.f` uses that term:

```fortran
      if (pl(i).gt.0.40) then
          totx = totx + pl(i) * (2.0 * tot511 - tot511 * tot511)
      else
          totx = totx + pl(i) * omegal * totxl
      endif
```

These native stages are used by the legacy well calculation
(`effsuite-well-coincidence`, `well_parallel.py`). The default well
calculation uses the spatial model below.

### 2.2 The tall-sample defect

The original computes the summing factor in `correct.f` by subtraction:

  *C* = emissions / (peak − emissions2 + emissions)

This combines mean-efficiency and second-moment estimates. When the sample
extends above the well rim, local efficiencies differ strongly between the
top and the bottom of the sample, and for multi-photon cascades the
denominator approaches zero or becomes negative. Detector DET07, with a 5 mL
vial filled to 50 mm in a 43 mm well, gives for Eu-152:

| Line / keV | Original *C* | EffSuite *C* |
|---|---:|---:|
| 316 | −89.26 | 12.02 |
| 665 | −262.43 | 11.43 |
| 906 | +6256.5 (denominator ≈ 2.6·10⁻⁹) | 11.10 |

The workbook `WEFFTRANCoincidenceSummingGENIE.xls` (sheet 8, line 42)
discards negative factors with `if x(n) > 0`. The affected lines are then left
uncorrected without warning.

### 2.3 Spatial integration of predicted counts

EffSuite (`spatial_summing.py`, `well_spatial.py`) evaluates the cascade at
quadrature points throughout the sample. It integrates the predicted counts,
and only then forms the ratio:

  *C*(E) = Σ *w*·*N*<sub>direct</sub>(E, **r**) / Σ *w*·*N*<sub>coincident</sub>(E, **r**)

* All transition probabilities and weights are non-negative, so neither sum
  can cancel. Factors are not averaged, clipped or replaced.
* The whole sample is included: the part inside the well and the part above
  the crystal. The axial integration is split at the crystal rim.
* Numerical convergence is checked twice, with twice the directions and with
  twice the sample points. Both checks must change every factor by less than
  1 %, otherwise export is blocked. This is a numerical test, not an
  uncertainty.
* The 511 keV annihilation pair uses exact zero- and single-detection
  probabilities for antiparallel photons. This replaces the legacy
  first-order 1 − 2*T*, which fails at high efficiency.
* Since v0.3.0, the ray tracing runs in the compiled `raytrace` program,
  which agrees with the Python version to about 10⁻¹⁴. DET007 complete
  analysis: 12.5 s instead of 108 s, peak memory under 1 GB.

Details, commands and the regression evidence are in
[WELL_SPATIAL_MODEL.md](WELL_SPATIAL_MODEL.md).

### 2.4 Well response model (DET007 Monte Carlo benchmark)

A well detector (DET007) was compared with a GenTran/EGSnrc Monte Carlo report
(17 nuclides, 41 gamma lines). Four defects were found and fixed:

| # | Problem | Fix |
|---|---|---|
| 1 | Containers wider than the well were accepted; `total` then returned values such as −9.19·10¹⁵ with exit code 0. | Container diameter > well diameter is refused, for sample and standard. |
| 2 | Sample build-up was one uniform multiplier, giving local probabilities > 1 (1.061 for a 24 mm vial) and blocking export. | Total efficiency is the sum of exclusive photon fates (uncollided, Rayleigh, Compton, absorbed), traced through sample, container, bore liner and top housing, so 0 ≤ peak ≤ total ≤ 1 by construction. |
| 3 | The two 511 keV photons were treated as independent directions. | Exact antiparallel pair probabilities from the same ray set. |
| 4 | The minimum-energy threshold used the axial instead of the radial sample thickness, on a coarse 26-point energy grid. | XCOM cross sections are evaluated at every gamma, X-ray and scattered energy. The legacy `mine` to `ptt` stages are not needed for well summing. |

The model has no fitted constants:
* peak-to-total comes from the real hollow crystal, with local containment of
  the first-scattered photon at the actual interaction depth;
* Compton and Rayleigh scattering in sample, container, liner and housing are
  recovered (the old code treated Compton in container and liner as
  absorption);
* the efficiency transfer for wells uses the same ray-traced response for the
  standard and the sample.

Residuals versus the Monte Carlo (sample: 58.46 mm water vial; standard:
20.75 mm):

| Quantity | Original WEFFTRAN | EffSuite |
|---|---|---|
| Transfer factor | +2.2 % to +5.3 % on all 41 lines | mean +1.3 %, RMS 1.9 %, maximum ≈ 4 % |
| Summing factor, 2-photon cascades (Co-60, Bi-214, Cs-134) | −6 % to −14 % | ≈ −5 % to −14 % |
| Summing factor, 3–4-photon cascades (Ba-133, Eu-152) | −15 % to −26 % | ≈ −15 % to −26 % |

The remaining summing deficit comes mainly from detector details that the
7-field WEFFTRAN input cannot describe. The optional inputs in section 2.5
address them.

### 2.5 Optional extended well-detector inputs

A 7-field detector file works unchanged. Up to five optional fields can follow,
positionally (12 lines) or as `key = value` lines, and `#` comments are
allowed:

| Key | Meaning | Default |
|---|---|---|
| `mantle_dead_layer` | outer-side dead layer, mm (DET007: 1.9 mm vs 0.7 mm in the bore) | the 7-field dead layer `dd` |
| `bottom_dead_layer` | crystal base dead layer, mm (DET007: 1.5 mm) | `dd` |
| `holder_thickness` | mount cup around mantle and base, mm (DET007: 2.45 mm Cu) | 0 |
| `sample_offset` | gap between well bottom and container, mm (added to the source offset) | 0 |
| `holder_material` | mount cup material | `copper` |

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

Rays distinguish active germanium from dead layers, which only absorb. Photons
leaving the crystal can Compton-backscatter from the holder: a fraction
≈ 0.40 returns with *E*′ = *E* / (1 + 1.4 *E* / 511 keV), that is 150 to
290 keV, where germanium absorbs strongly. This raises the total efficiency
without changing the primary peaks, and brings the DET007 summing factors to
90–100 % of the Monte Carlo values. The GUI shows the optional groups and
draws the mount cup in the cross-section view.

### 2.6 Well decay data

The well model reads `assets/common/Decay_Data` (261 files; a laboratory data
folder can replace it):

* **Na-22.** The original contained an experimental multi-line entry that
  forced the 511 keV lines into the cascade. EffSuite uses the canonical
  1274.537 keV line with β⁺ feeding P<sub>β⁺</sub> = 0.9030 and
  P<sub>K</sub> = 0.0960, and models the annihilation photons as described
  above.
* **Inconsistent records.** A structural audit (`examples/decay_library_audit.json`)
  rejects three of 227 parent records:
  * Pa-234: invalid or duplicate transition indices;
  * Th-227: a transition with total conversion coefficient 0 but L coefficient 13.6;
  * W-187: a transition with total conversion coefficient 0.0153 but K coefficient 118.

  They are not guessed or edited. Since v0.3.0, such a nuclide is reported as
  not corrected and the other nuclides are still calculated.

---

## 3. New in EffSuite (no original equivalent)

### 3.1 Uncertainty of the summing factors, u(C)

The original `coin.f` writes `nuclide, energy, factor`, and `correct.f` writes
`energy, factor`. The *Coincidence Summing* workbooks show only "Correction
Factor"; no uncertainty of *C* is computed anywhere. EffSuite adds a relative
standard uncertainty (k = 1) for every factor, in all three geometries,
without changing the engines:

* **Sensitivity coefficients.** *S*<sub>P</sub> = ∂ln *C*/∂ln ε<sub>P</sub>
  and *S*<sub>T</sub> = ∂ln *C*/∂ln ε<sub>T</sub> come from central
  differences over four extra engine runs. Each run scales the peak
  (`efficiency.txt`) or total (`buildup.txt`) efficiency curve by e<sup>±h</sup>;
  for wells, the ray-traced local efficiencies are scaled instead.
* **Combination.** u<sub>r</sub>(*C*)² = (*S*<sub>P</sub> *u*<sub>P</sub>)² +
  (*S*<sub>T</sub> *u*<sub>T</sub>)² + 2ρ *S*<sub>P</sub> *S*<sub>T</sub>
  *u*<sub>P</sub> *u*<sub>T</sub> + *u*<sub>num</sub>².
  * *u*<sub>P</sub>, *u*<sub>T</sub> and ρ are user settings (defaults 5 %,
    10 % and 0).
  * *u*<sub>num</sub> is the Monte Carlo uncertainty from column 4 of
    `total.txt` (cylinder and Marinelli) or the quadrature refinement change
    (wells).
* **Not included.** Decay-data uncertainties are left out, because the decay
  libraries contain none.

Full description: [TCS_UNCERTAINTY.md](TCS_UNCERTAINTY.md).

### 3.2 Genie 2000 and GammaVision files

| | Original | EffSuite |
|---|---|---|
| Genie `.CAL`, `.NLB`, `.CTF` | VBA overwrites the user's files in place through 32-bit COM | `genie.py` uses the installed CAM components (32- or 64-bit host). It writes a private copy, saves it, reopens it, checks every value, and publishes it under a new name (`*_sample.CAL`, `*_corrected.NLB`, `*_corrected.CTF`). The source file is never changed. |
| GammaVision `.LIB`, `.EFT` | `gv.f` overwrites `EFFTRAN.Lib` and writes `gv.txt`; macros write `.EFT` | `gammavision.py` (pure Python): same layouts, new output file, round-trip check, and a `<name>_gv.txt` report. One difference from `gv.f`: an ambiguous line match leaves the yield unchanged instead of taking the nearest line. **Untested with the real software.** |

### 3.3 Materials and XCOM

The original requires `Material.xls` and a separate XCOM run.
EffSuite has a Material Editor window, a `material` CLI command and a macro-free
workbook, all of which run the bundled XCOM 3.1. A material that has a
composition but no attenuation table is generated automatically during a
calculation. Density changes need only line 8 of the source model, or
`--sample-density`. Two compositions were renormalised:
`Copper_Ferrocyanide.txt` and `Spinach_ashed.txt`, whose original totals were
not normalised. See [MATERIALS.md](MATERIALS.md).

### 3.4 Calculation framework

| | Original | EffSuite |
|---|---|---|
| User interface | Excel workbooks with VBA (32-bit Excel) | Qt desktop GUI and a CLI sharing one service (`suite.run_project`) |
| Execution | VBA `Shell()` and `.bat` scripts in the program folder | Each job runs in a private temporary folder; bundled and laboratory data are copied, never written. The result folder appears only when the job succeeds. |
| Summing scope | one nuclide at a time, or a macro loop | all nuclides of a library in one run, in parallel native processes (`workers = 0`: CPU count − 2). A parent and its `b` continuation records stay together. |
| Reproducibility | none recorded | `results.json` records SHA-256 hashes of programs, data and inputs. `--verify-serial` checks that parallel equals serial output byte for byte. |
| Errors | silent zeros, or negative factors hidden | explicit errors; invalid or unconverged factors are marked `*` and are never exported as corrections |
| Platforms | Windows | Windows x64 and Linux (native programs for both) |
| Automation | none | `run` (saved project), geometry commands, `batch` (CSV/JSON), `plot-geometry`, `material` |
| Laboratory comparison | none | `lab_comparison.py` / `Compare_Lab.bat`: compares with archived reference outputs using pre-declared tolerances and hashed evidence files |

---

## 4. Suggestions for the original programs

1. **WEFFTRAN `total.f`.** Clamp the entry point *z*<sub>a</sub> in `path()`
   (section 2.1).
2. **WEFFTRAN summing.** Replace the subtraction in `correct.f`, or at least
   flag a non-positive denominator instead of discarding the factor in VBA
   (section 2.2).
3. **WEFFTRAN positron emitters.** Use 2ε₅₁₁ − ε₅₁₁² for β⁺ feeding in near-4π
   geometry (section 2.1).
4. **MEFFTRAN 1.9.** Make `mine.f` and `total.f` read the same 19-line
   detector file as `ptt.f` and `eta.f` (section 1.6). Done in MEFFTRAN 2.0,
   which uses 16 lines throughout.
5. **EFFTRAN 5.1 and MEFFTRAN 2.0 `total.f`.** Use `ne` rather than `ns` as
   the density loop bound (section 1.1).
6. **`transfer.f`.** Write energies with `e15.5` instead of `f12.1`
   (section 1.4).
7. **Decay data.** Correct Pa-234, Th-227 and W-187 (section 2.6), and add
   W-187 to `kordaten.txt`.

We welcome review and feedback from the original author and the
gamma-spectrometry community.
