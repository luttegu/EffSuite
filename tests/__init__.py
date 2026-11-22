"""EffSuite tests.

Every test process uses its own empty data folder and settings file, so the
tests never read or write the user's real materials (Documents, C:\\GENIE2K…)
and only see the bundled original materials plus what a test creates itself.
"""
import atexit
import os
import shutil
import tempfile

_sandbox = tempfile.mkdtemp(prefix="effsuite-tests-")
atexit.register(shutil.rmtree, _sandbox, True)
os.environ["EFFSUITE_DATA"] = os.path.join(_sandbox, "Data")
os.environ["APPDATA"] = os.path.join(_sandbox, "AppData")          # settings file (Windows)
os.environ["XDG_CONFIG_HOME"] = os.path.join(_sandbox, "config")   # settings file (Linux)

from pathlib import Path  # noqa: E402
import effsuite.paths  # noqa: E402

effsuite.paths.LEGACY_DATA_DIR = Path(_sandbox) / "legacy"         # never the real Documents\EffSuite\Data
effsuite.paths.legacy_data_dirs = lambda: [effsuite.paths.LEGACY_DATA_DIR]
