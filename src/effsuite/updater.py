"""Check GitHub for a newer EffSuite release, download and start its installer.

Only the standard library is used, so the check also works in the CLI build.
Releases are read from the public GitHub API; pre-releases are included because
EffSuite is published as beta releases.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable
import urllib.error
import urllib.request

from . import __version__ as VERSION

REPOSITORY = "luttegu/EffSuite"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
DOWNLOAD_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
CHECK_INTERVAL_S = 24 * 3600

# Keys in settings.json (see paths.load_settings).
SETTING_AUTO = "update_check_at_startup"
SETTING_LAST = "update_last_check"
SETTING_SKIPPED = "update_skipped_version"

_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)*)$")


class UpdateError(Exception):
    """Update check or download failed; the message is shown to the user."""


@dataclass(frozen=True)
class Release:
    version: str
    tag: str
    title: str
    notes: str
    page_url: str
    prerelease: bool
    asset_name: str
    asset_url: str
    asset_size: int
    sha256: str | None


def parse_version(text: str) -> tuple[int, ...] | None:
    """Return '0.3.4' or 'v0.3.4' as (0, 3, 4); None for anything else (e.g. 'v1.0-rc1')."""
    match = _VERSION_RE.match((text or "").strip())
    if not match:
        return None
    parts = [int(p) for p in match.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:   # 0.4 == 0.4.0
        parts.pop()
    return tuple(parts)


def is_newer(candidate: str, current: str = VERSION) -> bool:
    """True when candidate is a strictly higher version; unparseable versions are never newer."""
    new, old = parse_version(candidate), parse_version(current)
    return new is not None and old is not None and new > old


def release_from_json(item: dict) -> Release | None:
    """Build a Release from one GitHub API entry, or None if it has no usable installer.

    The installer must be named EffSuite_<version>_Setup.exe and be served from
    this repository's release downloads, so a renamed or foreign asset is never run.
    """
    if item.get("draft"):
        return None
    tag = str(item.get("tag_name") or "")
    if parse_version(tag) is None:
        return None
    version = tag.removeprefix("v")
    expected = f"EffSuite_{version}_Setup.exe"
    for asset in item.get("assets") or []:
        url = str(asset.get("browser_download_url") or "")
        if asset.get("name") != expected or not url.startswith(DOWNLOAD_PREFIX):
            continue
        digest = str(asset.get("digest") or "")
        return Release(
            version=version,
            tag=tag,
            title=str(item.get("name") or tag),
            notes=str(item.get("body") or ""),
            page_url=str(item.get("html_url") or RELEASES_PAGE),
            prerelease=bool(item.get("prerelease")),
            asset_name=expected,
            asset_url=url,
            asset_size=int(asset.get("size") or 0),
            sha256=digest.removeprefix("sha256:").lower() if digest.startswith("sha256:") else None,
        )
    return None


def newest_release(items: list[dict]) -> Release | None:
    """The highest-versioned release that has an installer."""
    releases = [r for r in (release_from_json(i) for i in items if isinstance(i, dict)) if r]
    return max(releases, key=lambda r: parse_version(r.version), default=None)


def _request(url: str, timeout: float):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"EffSuite/{VERSION}",   # GitHub rejects requests without one
    })
    return urllib.request.urlopen(request, timeout=timeout)


def fetch_releases(timeout: float = 10.0) -> list[dict]:
    """The latest releases from the GitHub API."""
    try:
        with _request(f"{RELEASES_API}?per_page=20", timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise UpdateError("GitHub refused the request (rate limit). Try again in an hour.") from exc
        raise UpdateError(f"GitHub returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise UpdateError(f"Could not reach GitHub: {getattr(exc, 'reason', exc)}") from exc
    except ValueError as exc:
        raise UpdateError("GitHub returned an unreadable answer.") from exc
    if not isinstance(data, list):
        raise UpdateError("GitHub returned an unexpected answer.")
    return data


def check_for_update(current: str = VERSION,
                     fetch: Callable[[], list[dict]] = fetch_releases) -> Release | None:
    """The newest release if it is newer than current, else None."""
    release = newest_release(fetch())
    return release if release and is_newer(release.version, current) else None


def should_check_automatically(settings: dict, now: float | None = None) -> bool:
    """True when startup checks are on and the last check is more than a day old."""
    if not settings.get(SETTING_AUTO, True):
        return False
    try:
        last = float(settings.get(SETTING_LAST, 0))
    except (TypeError, ValueError):
        last = 0.0
    now = time.time() if now is None else now
    return not (0 <= now - last < CHECK_INTERVAL_S)


def download_installer(release: Release, folder: Path | str | None = None,
                       progress: Callable[[int, int], None] | None = None,
                       cancel: threading.Event | None = None,
                       timeout: float = 30.0) -> Path:
    """Download the installer and check its size and SHA-256; return its path.

    A partial or corrupt file is deleted, so it can never be started.
    """
    folder = Path(folder or Path(tempfile.gettempdir()) / "EffSuite_update")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / release.asset_name
    partial = target.with_suffix(".part")
    digest = hashlib.sha256()
    received = 0
    try:
        with _request(release.asset_url, timeout) as response, open(partial, "wb") as out:
            total = int(response.headers.get("Content-Length") or release.asset_size or 0)
            while chunk := response.read(256 * 1024):
                if cancel is not None and cancel.is_set():
                    raise UpdateError("Download cancelled.")
                out.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress:
                    progress(received, total)
        if release.asset_size and received != release.asset_size:
            raise UpdateError(f"Download incomplete: {received} of {release.asset_size} bytes.")
        if release.sha256 and digest.hexdigest() != release.sha256:
            raise UpdateError("Downloaded installer does not match the SHA-256 published on GitHub.")
        os.replace(partial, target)
    except UpdateError:
        partial.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"Download failed: {getattr(exc, 'reason', exc)}") from exc
    return target


def can_install() -> bool:
    """True for the installed Windows build; a source checkout is updated with git instead."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def install_folder_writable(folder: Path | str | None = None) -> bool:
    """True when the current user can write to the installation folder (no UAC prompt needed)."""
    folder = Path(folder or Path(sys.executable).parent)
    try:
        with tempfile.TemporaryFile(dir=folder):
            return True
    except OSError:
        return False


def installer_arguments(writable: bool) -> list[str]:
    """Inno Setup command line for an in-place upgrade.

    Writable folder: silent upgrade, then the installer restarts EffSuite
    (/RELAUNCH=1, see installer/EffSuite.iss). Otherwise the folder belongs to an
    all-users installation: run the normal wizard in administrative mode.
    """
    if writable:
        return ["/SILENT", "/NORESTART", "/RELAUNCH=1"]
    return ["/ALLUSERS"]


def launch_installer(installer: Path | str, writable: bool) -> None:
    """Start the installer detached, so it keeps running after EffSuite exits."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(installer), *installer_arguments(writable)],
                     close_fds=True, creationflags=flags)
