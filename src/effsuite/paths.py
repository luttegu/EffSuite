r"""Centralized path resolution for EffSuite.

User folder (data and results): C:\GENIE2K\EffSuite when Genie 2000 is
installed or that folder already exists, otherwise Documents\EffSuite, or
%USERPROFILE%\EffSuite when Documents is synchronised by OneDrive (sync
latency, file locking and cloud placeholders disturb the engine runs).
Redirected and localised Documents folders (e.g. 'Dokumenter') are resolved
from the registry.
"""

from __future__ import annotations
from functools import lru_cache
import json
import os
from pathlib import Path
import sys
import tempfile


@lru_cache(maxsize=1)
def get_real_documents_dir() -> Path:
    """Resolve the actual user documents directory, accounting for OneDrive redirection.

    The answer is remembered (lru_cache): the Documents folder does not move
    while the program runs, and reading the registry every time is slow.
    """
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


# Genie 2000 installation folder. C:\GENIE2K is never created by EffSuite: its
# presence is how a Genie 2000 workstation is recognised.
GENIE2K_DIR = Path("C:/GENIE2K")


def is_onedrive_path(path: Path) -> bool:
    """True when ``path`` lies in a OneDrive-synchronised folder."""
    roots = [os.environ.get(name) for name in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")]
    folder = Path(str(path).lower())
    for root in filter(None, roots):
        root = Path(root.lower())
        if folder == root or root in folder.parents:
            return True
    return any(part.lower().startswith("onedrive") for part in path.parts)


def root_candidates() -> list[tuple[Path, bool]]:
    r"""User folder candidates in order, each with "may create its parent folder".

    1. C:\GENIE2K\EffSuite if it already exists (kept, even without Genie 2000,
       so data written there by earlier versions stays in use)
    2. C:\GENIE2K\EffSuite if C:\GENIE2K exists (Genie 2000 installed)
    3. Documents\EffSuite, unless Documents is synchronised by OneDrive and
       the folder does not exist yet
    4. %USERPROFILE%\EffSuite
    5. %LOCALAPPDATA%\EffSuite, then the temp folder
    """
    out: list[tuple[Path, bool]] = []
    genie_root = GENIE2K_DIR / "EffSuite"
    if genie_root.is_dir() or GENIE2K_DIR.is_dir():
        out.append((genie_root, False))
    documents = get_real_documents_dir()
    if documents != Path.home() and ((documents / "EffSuite").is_dir() or not is_onedrive_path(documents)):
        out.append((documents / "EffSuite", True))
    out.append((Path.home() / "EffSuite", True))
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        out.append((Path(local_app_data) / "EffSuite", True))
    out.append((Path(tempfile.gettempdir()) / "EffSuite", True))
    return out


def get_effsuite_root() -> Path:
    r"""Return the user folder for EffSuite data and results.

    EFFSUITE_ROOT wins when set; otherwise the first writable folder of
    root_candidates().
    """
    return _find_effsuite_root(os.environ.get("EFFSUITE_ROOT"))


@lru_cache(maxsize=4)
def _find_effsuite_root(env_root: str | None) -> Path:
    """Search for the root folder once per value of EFFSUITE_ROOT (remembered).

    Without this, every call created folders and wrote a test file on disk.
    """
    if env_root:
        return Path(env_root)

    for cand, parents in root_candidates():
        try:
            cand.mkdir(parents=parents, exist_ok=True)
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


# Older location of the laboratory data, still searched (read only) so existing files keep working.
LEGACY_DATA_DIR = Path.home() / "Documents/EffSuite/Data"


def legacy_data_dirs() -> list[Path]:
    """Legacy Documents/EffSuite/Data folders: the real (OneDrive / redirected) Documents and ~/Documents."""
    folders = [LEGACY_DATA_DIR]
    real = get_real_documents_dir() / "EffSuite/Data"
    if real not in folders:
        folders.insert(0, real)
    return folders


def settings_file() -> Path:
    """Per-user settings file (JSON), independent of the data folder it points to.

    Windows: %APPDATA%\\EffSuite\\settings.json; elsewhere ~/.config/effsuite/settings.json.
    """
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "EffSuite" / "settings.json"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "effsuite" / "settings.json"


def load_settings() -> dict:
    """The saved user settings ({} when there are none or the file is unreadable)."""
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict) -> None:
    """Write the user settings (atomic replace)."""
    target = settings_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def builtin_data_dir() -> Path:
    """Default laboratory data folder when nothing else is set: <EffSuite root>\\Data."""
    return get_effsuite_root() / "Data"


def data_dir_source() -> str:
    """Where the default data folder comes from: "environment", "settings" or "built-in"."""
    if os.environ.get("EFFSUITE_DATA"):
        return "environment"
    if load_settings().get("data_directory"):
        return "settings"
    return "built-in"


def get_data_dir() -> Path:
    """The user's laboratory data folder (own Material, Composition, Detector, Sample, Standard).

    Priority: EFFSUITE_DATA environment variable, then the folder saved with
    set_data_dir() (GUI: Tools → Default Data Folder…; CLI: ``config --data-dir``),
    then <EffSuite root>\\Data. The folder may not exist yet: it is created
    (with ensure_data_dir) the first time something is saved in it. Only the
    original EFFTRAN / MEFFTRAN materials are bundled with the program.
    """
    env = os.environ.get("EFFSUITE_DATA")
    if env:
        return Path(env).expanduser()
    saved = load_settings().get("data_directory")
    if saved:
        return Path(saved).expanduser()
    return builtin_data_dir()


def ensure_data_dir(folder: Path | str | None = None) -> Path:
    """Create the data folder (default: get_data_dir()) with its Composition and Material subfolders."""
    folder = Path(folder).expanduser() if folder else get_data_dir()
    for sub in ("Composition", "Material"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    return folder


def set_data_dir(folder: Path | str | None) -> Path:
    """Save ``folder`` as the default data folder (None: back to the built-in default).

    The folder and its Composition / Material subfolders are created. Returns
    the data folder now in effect (EFFSUITE_DATA still wins when set).
    """
    settings = load_settings()
    if folder:
        folder = ensure_data_dir(Path(folder).expanduser().resolve())
        settings["data_directory"] = str(folder)
    else:
        settings.pop("data_directory", None)
    save_settings(settings)
    return get_data_dir()


def user_data_dirs(data_directory: Path | str | None = None) -> list[Path]:
    """Laboratory data folders to search, most specific first.

    The project's own folder (if any), the default data folder, then the
    legacy Documents\\EffSuite\\Data. The bundled original data come after these.
    """
    folders = [Path(data_directory).expanduser()] if data_directory else []
    for folder in (get_data_dir(), *legacy_data_dirs()):
        if folder not in folders:
            folders.append(folder)
    return folders


def get_results_dir() -> Path:
    results_base = get_effsuite_root() / "Results"
    try:
        results_base.mkdir(parents=True, exist_ok=True)
        return results_base
    except OSError:
        return Path(tempfile.gettempdir()) / "EffSuite/Results"
