# native/ — historical WEFFTRAN geometry work

This folder is **not** used by the calculations. The engines EffSuite runs,
EFFTRAN 5.1, MEFFTRAN 2.0 and WEFFTRAN with their sources, Windows/Linux
programs and build manifests, are in `src/effsuite/assets/engines/`. They run
as separate processes in private working folders.

| Folder | Contents |
|---|---|
| `wefftran_geometry/` | Source-derived ray/cylinder intersection changes for `total`, `scatter` and `eta`, covering additional axial and outside-origin cases. Copyright and permission notices are retained. |
| `wefftran_original/` | The supplied original `peak_org.f` and `total_org.f`, used only as references by `tools/check_wefftran.py`. |

The supplied WEFFTRAN archive already contained an earlier tall-sample patch.
The geometry changes here improve the ray intersections, but they do **not**
remove the negative or near-singular summing factors of the original
subtraction formula. The actual fix is the spatial summing model described in
[docs/WELL_SPATIAL_MODEL.md](../docs/WELL_SPATIAL_MODEL.md). Run
`tools/check_wefftran.py` before evaluating any proposed geometry change.

## Notes for a future in-process engine

A DLL-based engine would need a native host matching its calling convention,
data types, string layout, array order, initialisation and FPU set-up. The
host may need to be 32-bit even when Python is 64-bit; a subprocess avoids
matching Python's architecture.

After reference validation, a narrow Fortran `ISO_C_BINDING` wrapper could be
added around the existing routines:

* use `BIND(C)` and explicit interoperable types;
* do not change a legacy `REAL` into `REAL(C_DOUBLE)` unless that legacy type
  has been identified as binary64;
* preserve the legacy `COMMON` / `SAVE` state semantics, and serialise calls
  until reentrancy is established;
* return an error code and diagnostics instead of executing `STOP` inside
  Python.

A Windows program does not become portable by being launched from Python. A
native Linux or macOS engine needs recompilation or a port, and its own
qualification.
