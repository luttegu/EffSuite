r"""Centralized path resolution for EffSuite.

Default installation & workspace: C:\GENIE2K\EffSuite
Avoids OneDrive synchronization latency, file locking, cloud placeholders,
and foreign language / redirected user profile folder naming (e.g. 'Dokumenter').
"""

from __future__ import annotations
import os
from pathlib import Path
import sys
import tempfile


def get_real_documents_dir() -> Path:
    """Resolve the actual user documents directory, accounting for OneDrive redirection."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                val, _ = winreg.QueryValueEx(key, "Personal")
                expanded = Path(os.path.expandvars(val))
                if expanded.is_dir():
                    return expanded
        except Exception:
            pass
    for cand in [Path.home() / "Documents", Path.home() / "Dokumenter"]:
        if cand.is_dir():
            return cand
    return Path.home()


def get_effsuite_root() -> Path:
    r"""Return the primary root directory for EffSuite data and results.

    Priority:
    1. EFFSUITE_ROOT environment variable (if explicitly set)
    2. C:\GENIE2K\EffSuite (standard production location)
    3. Real Documents/EffSuite (taking into account OneDrive/Dokumenter)
    4. LocalAppData/EffSuite
    5. Temp fallback
    """
    env_root = os.environ.get("EFFSUITE_ROOT")
    if env_root:
        return Path(env_root)

    candidates: list[Path] = [
        Path("C:/GENIE2K/EffSuite"),
        get_real_documents_dir() / "EffSuite",
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "EffSuite")
    candidates.append(Path(tempfile.gettempdir()) / "EffSuite")

    for cand in candidates:
        try:
            cand.mkdir(parents=True, exist_ok=True)
            test = cand / ".write_test"
            test.touch()
            test.unlink()
            return cand
        except OSError:
            continue

    return Path(tempfile.gettempdir()) / "EffSuite"


def is_readable_dir(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        if not path.is_dir():
            return False
        with os.scandir(path) as it:
            next(it, None)
        return True
    except (OSError, PermissionError):
        return False


def get_data_dir() -> Path | None:
    for cand in [
        get_effsuite_root() / "Data",
        Path("C:/GENIE2K/EffSuite/Data"),
        get_real_documents_dir() / "EffSuite/Data",
    ]:
        if is_readable_dir(cand / "Composition") or is_readable_dir(cand / "Material"):
            return cand
    return None


def get_results_dir() -> Path:
    results_base = get_effsuite_root() / "Results"
    try:
        results_base.mkdir(parents=True, exist_ok=True)
        return results_base
    except OSError:
        return Path(tempfile.gettempdir()) / "EffSuite/Results"
