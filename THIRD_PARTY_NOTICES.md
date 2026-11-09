# Third-party components

EFFTRAN 4.8 and MEFFTRAN 1.7 were supplied by the official EFFTRAN project;
WEFFTRAN source/data were supplied in the user's archive. Original copyright
and permission notices are preserved in each engine's README/source, with
copies under third_party. Modifications do not remove those notices.

The native source contains separately marked Numerical Recipes routines;
those notices are retained. This package makes no blanket relicensing claim
for legacy source, reference programs, datasets or third-party routines.

The bundled new native programs were built with GNU Fortran. GCC runtime and
MinGW-w64 package copyright/license notices, including the GCC Runtime Library
Exception, are copied under third_party. Compiler/build/binary hashes are
recorded in assets/engines/*/bin/*/build_manifest.json. Compiler toolchains
and their downloaded packages are not included in this release.

NumPy, Matplotlib and PySide6 are installed as dependencies, retaining their
own licenses. A future frozen distribution must retain their accompanying
notices as well. Genie CAM components are not included; the adapter uses the
vendor components installed on the user's Windows computer.

New application code is supplied for inspection and laboratory evaluation.
The presence of notices or passing software tests does not establish
scientific suitability or authorize routine laboratory release.

XCOM 3.1 source/data supplied with EFFTRAN are included under assets/xcom.
Its source states copyright 1999 Martin J. Berger and permission for
non-commercial use. That notice and its original NIST README are preserved;
no broader relicensing claim is made. Temporary compilation copies remove
DOS EOF control characters from include files; numerical statements are unchanged.
