"""EffSuite — Gamma spectrometry efficiency transfer and coincidence summing suite."""

__version__ = "0.5.3"

import os

# numpy's OpenBLAS reserves a buffer per CPU thread at import: about 750 MB of committed
# memory on a 24-thread PC. EffSuite does almost no linear algebra, so one thread costs
# nothing. Set before any submodule imports numpy; a value set by the user is kept.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
