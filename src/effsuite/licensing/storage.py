"""Atomic per-user activation storage for EffSuite."""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import tempfile
from typing import Callable
import uuid

from .config import PUBLIC_KEYS, PRODUCT_ID
from .verification import (
    License,
    LicenseError,
    read_bytes,
    uuid_text,
    verify_license,
    utc_time,
    utc_text,
)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".effsuite-lic-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass


class LicenseStore:
    """Per-user license storage, installation ID management, and offline verification."""

    def __init__(
        self,
        directory: Path,
        public_keys: dict[str, str],
        version: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.public_keys = public_keys
        self.version = version
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def path(self) -> Path:
        return self.directory / "activation.efflic"

    def installation_id(self) -> str:
        path = self.directory / "installation-id.txt"
        if path.exists():
            try:
                return uuid_text(read_bytes(path).decode("ascii").strip())
            except (UnicodeError, ValueError) as exc:
                raise LicenseError(
                    "Installation identity is damaged. Restore it or request a replacement licence."
                ) from exc
        self.directory.mkdir(parents=True, exist_ok=True)
        value = str(uuid.uuid4())
        try:
            with path.open("x", encoding="ascii") as stream:
                stream.write(value + "\n")
        except FileExistsError:
            return self.installation_id()
        return value

    def verify(self, data: bytes) -> License:
        now = self.clock()
        result = verify_license(
            data, self.public_keys, version=self.version, installation_id=self.installation_id(), now=now
        )
        seen_path = self.directory / "last-seen-utc.txt"
        seen = utc_time(read_bytes(seen_path).decode("ascii").strip()) if seen_path.exists() else None
        if seen is not None and now < seen - timedelta(minutes=5):
            raise LicenseError(
                "The computer clock moved backwards. Correct your system date and time."
            )
        if seen is None or now > seen:
            try:
                atomic_write(seen_path, (utc_text(now) + "\n").encode("ascii"))
            except OSError:
                pass
        return result

    def current(self) -> License:
        if not self.path.exists():
            # Check system-wide default installation location C:\GENIE2K\EffSuite\Licensing
            alt = Path("C:/GENIE2K/EffSuite/Licensing/activation.efflic")
            if alt.exists() and alt != self.path:
                try:
                    return self.verify(read_bytes(alt))
                except Exception:
                    pass
            # Check bundled default lab license
            bundled = Path(__file__).resolve().parents[3] / "publisher/official_keys/default_lab_license.efflic"
            if bundled.exists():
                try:
                    return self.verify(read_bytes(bundled))
                except Exception:
                    pass
            raise LicenseError("No licence is installed. Please activate EffSuite.")
        try:
            return self.verify(read_bytes(self.path))
        except OSError as exc:
            raise LicenseError(f"Could not read licence file: {exc}") from exc

    def import_license(self, data: bytes) -> License:
        licence = self.verify(data)
        atomic_write(self.path, data)
        return licence

    def request_document(self) -> dict:
        return {
            "schema_version": 1,
            "product": PRODUCT_ID,
            "installation_id": self.installation_id(),
            "application_version": self.version,
            "created_at": utc_text(self.clock()),
        }


from ..paths import get_licensing_dir


def default_store(version: str = "0.1.0") -> LicenseStore:
    return LicenseStore(get_licensing_dir(), PUBLIC_KEYS, version)
