> Historical investigation checkpoint. EffSuite 0.3.0 now connects the original-style GUI and CLI to the actual engines and includes a vendor-CAM adapter. Real Windows/Genie verification remains pending. See README.md for current functionality.

# WEFFTRAN investigation, 30 October 2026

This is the historical investigation checkpoint. A source-guided spatial
backend now passes the numerical regression checks for the reproduced
failure. Read [WEFFTRAN_FIX.md](WEFFTRAN_FIX.md) for the current fix,
commands and qualification limits. The original subtraction-based
calculation remains available as a reference backend.

## Reproduced failure

The supplied DET07 model has a 69 mm crystal height and a 43 mm well depth.
Using `Plastic_vial_5mL.txt` with a 50 mm sample height places the sample
between z = 37.5 mm and z = 87.5 mm in the crystal coordinate system.
The upper 18.5 mm extends above the crystal.

The original pipeline, compiled from the supplied sources on Linux, gives
these Eu-152 results. Energies below are the program's integer-keV bins,
not a higher-resolution nuclide-library line identification.

| Bin (keV) | Supplied factor | Observed numerical condition |
|---|---:|---|
| 316 | -89.258 | Negative correction denominator |
| 665 | -262.43 | Negative correction denominator |
| 906 | 6256.5 | Nearly cancelling denominator |

The result formula in `correct.f` is:

```text
C = emissions / (peak - emissions2 + emissions)
```

For the 906 keV bin the printed intermediates are:

```text
emissions  = 1.6267e-5
peak       = 1.0876e-6
emissions2 = 1.7352e-5
denominator = 2.6e-9
```

These produce the printed factor 6256.5. The large value is not introduced
by parallel scheduling. Reverting to the supplied `peak_org.f` reproduces
the same Eu-152 factors, and the ray-intersection patches do not change
these printed height-sweep outputs.

This localizes the failure to the correction result and its denominator.
It does not yet prove which scientific approximation or implementation
choice should be replaced. Replacing negative results with absolute values,
clipping large factors, or substituting one would not establish a valid
physical calculation.

The supplied `Instructions.rtf` says the sample must fit completely into
the well. Samples extending above the crystal therefore require an
extension and qualification beyond that original stated use envelope.

## Confirmed Genie export behavior

The supplied `WEFFTRANCoincidenceSummingGENIE.xls` VBA, in `Sheet8`, starts
each library line with `C = 1` and searches for a nearby correction only
when `x(n) > 0`. Negative corrections are skipped. When none qualifies,
the abundance is left unchanged and a `*` comment is shown in Excel.

That is a concrete mechanism for a failed calculation appearing as
"no correction" in the exported library. Missing decay records also yield
no correction rows. The older workbook does not distinguish these outcomes
from a calculated unit factor in the factor column alone.

The new `plan_nlb_updates` routine rejects failed, missing or ambiguous
matches before preparing any edits. It does not modify the original workbook
or write an NLB itself. Actual CAM integration remains to be implemented.

## Implemented migration components

- EFFTRAN/MEFFTRAN nuclide-group scheduling, including `b` continuations.
- WEFFTRAN per-nuclide scheduling through `initialize`, `emissions`,
  `emissions2`, `peak` and `correct`, with private directories and immutable
  shared efficiency inputs.
- Serial verification against parallel raw output bytes, deterministic
  output order, cancellation, timeouts and process-error propagation.
- Diagnostic states: `candidate`, `invalid`, `missing`, `no_direct_peak`
  and `review_cancellation`. An invalid or missing factor remains null.
- A configurable cancellation-review policy using
  `abs(denominator)/(abs(peak)+abs(emissions2)+abs(emissions))`.
  Its default 0.001 threshold is an implementation review policy, not a
  physical bound or a substitute for uncertainty analysis.
- Source-derived ray intersection patches for axial rays and external
  emission points. Those checks pass, but the patches alone do not repair
  the summing factors.

The native workers still use the original scientific equations and supplied
data. The production GUI and Genie file adapter are separate unfinished work.

## Validation and reproducibility

`examples/wefftran_investigation.json` records:

- 2,000 interior rays unchanged against the legacy routine.
- 4,000 comparisons against an independent geometric construction, plus
  axial and miss cases.
- Height sweeps at 3.25, 31.5, 32.5, 50 and 100 mm.
- Original versus supplied peak comparison for the Eu-152 50 mm case.
- All 227 WEFFTRAN parent groups, including 33 continuation records:
  serial/four-worker byte equality for all four returned spectrum files.
- Agreement for Co-60, Cs-134 and Eu-152 with an independently driven
  sequential `coin2.bat`-equivalent stage sequence.

To regenerate with a local GNU Fortran installation:

```bash
python tools/check_wefftran.py --original /path/to/WEFFTRAN --compiler gfortran --all-nuclides --report investigation.json
```

The report file must be new. Add compiler arguments with
`--compiler-arg=...` when required. Linux checks adapt Windows path separators
only in temporary source copies. The original installation is read-only.
No native Windows binary, Genie CAM round trip or laboratory detector
measurement has been validated here. Equal printed output is not a claim
about equality of hidden floating-point intermediates across platforms.

## Remaining scientific work

Trace the extended-source moment correction against its derivation and
validate an appropriate spatial treatment for samples that extend above
the well/crystal. Qualification needs reference detector measurements or an
independent transport calculation, including strong and weak cascade lines,
summing-in, summing-out, and the height boundary. The spatial backend now
repairs the reproduced numerical failure. Its physical-model accuracy
requires the independent qualification described in WEFFTRAN_FIX.md.
