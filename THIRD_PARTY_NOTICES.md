# Third-Party Components

## EFFTRAN, MEFFTRAN and WEFFTRAN

The cylinder and Marinelli engines are based on **EFFTRAN 5.1** and
**MEFFTRAN 2.0**, supplied by the official EFFTRAN project
(https://efftran.github.io/). The well engine is based on **WEFFTRAN 0.8**,
whose source and data were supplied in the user's archive. All three are by
Tim Vidmar:

* EFFTRAN 5.1 and MEFFTRAN 2.0: Copyright (c) 2005–2026 Tim Vidmar.
* WEFFTRAN 0.8: Copyright (c) 1995–2016 Tim Vidmar (source file headers);
  the WEFFTRAN 0.8 README is dated 2018.

All three are used under his permission notice:

> Permission to use, copy, modify, distribute and sell this software and its
> documentation for any purpose is hereby granted without fee, provided that
> the above copyright notice appears in all copies and that both that
> copyright notice and this permission notice appear in all supporting
> documentation. Tim Vidmar makes no representations about the suitability of
> this software for any purpose. It is provided 'as is' without express or
> implied warranty.

Where the notice is kept:

* **EFFTRAN 5.1 and MEFFTRAN 2.0**: the `.f` files do not contain the notice
  themselves. It is in each engine's `README.txt` and in a `NOTICE.txt` file
  in each `source/` folder.
* **WEFFTRAN**: in the header of each WEFFTRAN source file, in the engine's
  `README.txt` and in `source/NOTICE.txt`; for `native/`, in
  `native/NOTICE.txt`.
* Python code adapted from the engines (`src/effsuite/spatial_summing.py`)
  carries the notice in its header.
* Copies are in `third_party/`: `cylindrical-original-notice.txt` and
  `marinelli-original-notice.txt` (the EFFTRAN 5.1 and MEFFTRAN 2.0 README
  files, copied verbatim), and `well-original-notice.txt`.

EffSuite's modifications are listed in
[docs/CHANGES_FROM_ORIGINALS.md](docs/CHANGES_FROM_ORIGINALS.md); they do not
remove those notices.

No blanket relicensing claim is made for the legacy source, the reference
programs, the datasets (including the decay data in `Decay_Data/`,
`kordaten.txt` and `zzaa.txt`, and the bundled materials) or third-party
routines; they keep the terms under which they were supplied.

## Numerical Recipes routines

The engine sources (and their compiled programs) contain routines from
*Numerical Recipes in Fortran 77* (W. H. Press, S. A. Teukolsky,
W. T. Vetterling, B. P. Flannery), inherited from the original programs:

| Routine | Files |
|---|---|
| `SUBROUTINE sobseq` | `eta.f`, `scatter.f`, `total.f` of all three engines; `native/wefftran_geometry/eta.f`, `scatter.f`, `total.f`; `native/wefftran_original/total_org.f` |
| `FUNCTION rtbis` | `mine.f` of all three engines |

Notice: **(C) Copr. 1986-92 Numerical Recipes Software.** The notice follows
each routine in the source, except in the well engine's `total.f` and
`native/wefftran_geometry/total.f`, where it is missing; for those files it
is given in the `NOTICE.txt` of their folder.

These routines are proprietary to Numerical Recipes Software. They are
**not** covered by Tim Vidmar's permission notice or by the GNU General Public
License of EffSuite, and EffSuite grants no rights in them.

## NIST XCOM 3.1

The XCOM 3.1 source, data and original NIST README supplied with EFFTRAN are
included under `src/effsuite/assets/xcom`, with programs compiled from that
source. `XCOM.FOR` states:

> Copyright 1999, Martin J. Berger. Permission is given to use the program
> for non-commercial purposes.

**Restriction:** this permission covers **non-commercial use only**. XCOM is
not licensed under the GNU General Public License of EffSuite or under Tim
Vidmar's notice, and EffSuite grants no rights in it. NIST also asserts
copyright in its Standard Reference Data on behalf of the United States
(15 U.S.C. 290e). See `src/effsuite/assets/xcom/NOTICE.txt`. Temporary
compilation copies remove DOS end-of-file characters from include files; the
numerical statements are unchanged.

## Compilers and runtime libraries

The bundled native programs were built with GNU Fortran (GCC 15.2.0 from
w64devkit for Windows, GCC 13 for Linux). Compiler versions, flags and binary
hashes are recorded in `src/effsuite/assets/engines/*/bin/*/build_manifest.json`.
The compiler toolchains themselves are not included.

* **libgfortran and libgcc** are covered by the GPL-3.0 with the GCC Runtime
  Library Exception.
* **libquadmath** is statically linked into the Windows programs (built with
  `-static`). It is licensed under the **GNU Lesser General Public License
  version 2.1 or later** (`third_party/LGPL-2.1.txt`). The complete Fortran
  sources and build scripts (`tools/build_engines.py`,
  `tools/build_raytrace.py`, `tools/build_xcom.py`) are included, so the
  programs can be relinked against a modified libquadmath.
* The GCC runtime and MinGW-w64 copyright and licence notices are copied in
  `third_party/` (`gcc-mingw-w64-base-copyright.txt`,
  `mingw-w64-common-copyright.txt`, `mingw-w64-x86-64-dev-copyright.txt`).

## Python and Python packages

NumPy, Matplotlib, PySide6 (Qt for Python) and xlrd, with their own
dependencies, are installed as dependencies under their own licences. The
frozen Windows build (PyInstaller) bundles them and the Python runtime; their
licence files are copied into its `_internal/licenses/` folder, one subfolder per
package. Any redistribution of that build must keep them.

* **PySide6, Shiboken6 and Qt**: GNU Lesser General Public License version 3
  (`third_party/LGPL-3.txt`, to be read with `third_party/GPL-3.txt`). Qt is
  Copyright (C) The Qt Company Ltd. and other contributors. The Qt and PySide6
  libraries are shipped as separate DLLs and Python modules in the build's
  `_internal` folder and can be replaced by the user. Their source code is
  available from https://download.qt.io/ and
  https://code.qt.io/cgit/pyside/pyside-setup.git/.
* **Python**: Python Software Foundation License (`_internal/licenses/python`).
* **NumPy, Matplotlib, xlrd and the other packages**: BSD-style, PSF-style,
  MIT, Apache-2.0 or HPND licences, as given in `_internal/licenses/`. Matplotlib's
  bundled DejaVu and STIX fonts keep their licence files.
* **Microsoft Visual C++ runtime** (`VCRUNTIME140*.dll`), as shipped with
  Python, under Microsoft's redistribution terms.

## Genie 2000 and GammaVision

Genie CAM components are not included: the adapter uses the vendor
components installed on the user's Windows computer. GammaVision files are
read and written by EffSuite's own code; no ORTEC software is included.

## Trademarks

Genie 2000, Canberra, Mirion, GammaVision, ORTEC, Qt and other product and
company names are trademarks of their respective owners. They are used only
to identify compatible software; EffSuite is not affiliated with or endorsed
by these companies.

## EffSuite

The EffSuite code is licensed under the GNU General Public License, version 3
or (at your option) any later version (SPDX: `GPL-3.0-or-later`)
(`LICENSE`, also in `third_party/GPL-3.txt`). This licence covers EffSuite's
own code only; the components above keep their own terms.

It is supplied for inspection and laboratory evaluation. Neither the presence
of these notices nor passing software tests establishes scientific
suitability or authorises routine laboratory release.
