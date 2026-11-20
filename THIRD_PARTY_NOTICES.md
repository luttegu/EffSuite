# Third-Party Components

## EFFTRAN, MEFFTRAN and WEFFTRAN

The cylinder and Marinelli engines are based on **EFFTRAN 5.0** and
**MEFFTRAN 1.9**, supplied by the official EFFTRAN project
(https://efftran.github.io/). The well engine is based on **WEFFTRAN 0.8**,
whose source and data were supplied in the user's archive. EFFTRAN and
MEFFTRAN are Copyright (c) 2005–2026 and WEFFTRAN is Copyright (c) 2018,
Tim Vidmar. All three are used under his permission notice:

> Permission to use, copy, modify, distribute and sell this software and its
> documentation for any purpose is hereby granted without fee, provided that
> the above copyright notice appears in all copies and that both that
> copyright notice and this permission notice appear in all supporting
> documentation. Tim Vidmar makes no representations about the suitability of
> this software for any purpose. It is provided 'as is' without express or
> implied warranty.

The original notices are kept in the engines' source files and README files.
Copies are in `third_party/`: `cylindrical-original-notice.txt` and
`marinelli-original-notice.txt` (the EFFTRAN 5.0 and MEFFTRAN 1.9 README
files, copied verbatim; the MEFFTRAN 1.9 README header still reads
"version 1.8"), and `well-original-notice.txt`. EffSuite's modifications are listed in
[docs/CHANGES_FROM_ORIGINALS.md](docs/CHANGES_FROM_ORIGINALS.md); they do not
remove those notices.

The native source contains separately marked Numerical Recipes routines;
their notices are retained. No blanket relicensing claim is made for the
legacy source, the reference programs, the datasets or third-party routines.

## NIST XCOM 3.1

The XCOM 3.1 source and data supplied with EFFTRAN are included under
`src/effsuite/assets/xcom`. The source states copyright 1999 Martin J. Berger
and permission for non-commercial use. That notice and the original NIST
README are preserved; no broader relicensing claim is made. Temporary
compilation copies remove DOS end-of-file characters from include files;
the numerical statements are unchanged.

## Compilers and runtime libraries

The bundled native programs were built with GNU Fortran (GCC 15.2.0 from
w64devkit for Windows, GCC 13 for Linux). The GCC runtime and MinGW-w64
copyright and licence notices, including the GCC Runtime Library Exception,
are copied in `third_party/`. Compiler versions, flags and binary hashes are
recorded in `src/effsuite/assets/engines/*/bin/*/build_manifest.json`. The
compiler toolchains themselves are not included.

## Python packages

NumPy, Matplotlib, PySide6 (Qt) and xlrd are installed as dependencies under
their own licences. The frozen Windows build (PyInstaller) bundles them; any
redistribution of that build must keep their licence notices.

## Genie 2000 and GammaVision

Genie CAM components are not included: the adapter uses the vendor
components installed on the user's Windows computer. GammaVision files are
read and written by EffSuite's own code; no ORTEC software is included.

## EffSuite

The EffSuite code is licensed under the GNU General Public License v3.0
(`third_party/GPL-3.txt`). It is supplied for inspection and laboratory
evaluation. Neither the presence of these notices nor passing software tests
establishes scientific suitability or authorises routine laboratory release.
