# Native engine integration

The official EFFTRAN 4.8 and MEFFTRAN 1.7 sources and the supplied WEFFTRAN
archive have now been inspected. The migration runners use those original
programs through private subprocess working directories. They do not yet
replace the scientific algorithms with an independent engine.

`wefftran_geometry` contains source-derived ray/cylinder intersection changes
for `total`, `scatter` and `eta`. Copyright and permission notices are retained.
The supplied archive already contained an earlier tall-sample patch. These
new changes cover additional axial and outside-origin cases, but do not remove
the reproduced negative or near-singular summing factors. See
`../WEFFTRAN_FINDINGS.md` and run `../tools/check_wefftran.py` before evaluating
a proposed geometry change. The v0.3 suite bundles new Windows/Linux numerical executables under
`src/effsuite/assets/engines`. This historical geometry-patch folder is retained
for investigation; the main well summing fix is the spatial backend.

For the historical general JSON bridge proposal, use `../docs/archive/BRIDGE_PROTOCOL.md`. Keep the
reference executable unchanged. A DLL-based variant needs a native host that
matches its calling convention, data types, string layout, array order,
initialization and FPU setup. The host may need to be 32 bit even when Python
is 64 bit; a subprocess avoids matching Python's architecture.

After reference validation, add a narrow Fortran `ISO_C_BINDING` wrapper around existing routines. Use `BIND(C)` and explicit interoperable types. Do not change a legacy `REAL` into `REAL(C_DOUBLE)` unless that legacy type has actually been identified as binary64. Preserve legacy `COMMON` / `SAVE` state semantics and serialize calls until reentrancy has been established. Return an error code and diagnostics rather than executing `STOP` inside Python.

Possible native build layout:

```text
native/
  original/             # controlled, unmodified sources and build metadata
  c_api/                # BIND(C) wrapper and public C header
  host/                 # isolated executable implementing the JSON bridge
  cmake/                # compiler profiles per platform and target architecture
  data/                 # versioned cross sections and decay tables, with hashes
```

A Windows executable does not become portable when launched through Python. A native Linux or macOS engine requires recompilation or a port and its own qualification. A Windows worker reached by an explicit service can be an interim deployment, but is not a standalone native cross-platform engine.
