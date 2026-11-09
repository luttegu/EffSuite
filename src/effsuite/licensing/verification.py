"""Strict Ed25519 verification for EffSuite.

The signature covers the canonical UTF-8 payload bytes and a product-specific
protocol prefix. No remote service or executable code is loaded from a licence.
Offline expiry uses the local UTC clock.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_FILE_BYTES = 65_536
DOMAIN = b"EffSuite-License-v1\x00"
PRODUCT_ID = "effsuite"
VERSION_PATTERN = r"(?:0|[1-9]\d{0,3})\.(?:0|[1-9]\d{0,3})\.(?:0|[1-9]\d{0,3})"


class LicenseError(ValueError):
    """Invalid, inapplicable, expired or unsupported licence data."""


def encode64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def decode64(value: Any, length: int | None = None) -> bytes:
    if not isinstance(value, str) or not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise LicenseError("Invalid base64url encoding")
    try:
        data = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise LicenseError("Invalid base64url data") from exc
    if encode64(data) != value or (length is not None and len(data) != length):
        raise LicenseError("Invalid encoded length or non-canonical encoding")
    return data


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LicenseError("Duplicate JSON fields are not allowed")
        result[key] = value
    return result


def strict_json(data: bytes) -> dict[str, Any]:
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_FILE_BYTES:
        raise LicenseError("Licence data must contain 1–65536 bytes")
    try:
        result = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(LicenseError("Non-finite JSON value")),
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise LicenseError(f"Invalid licence JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise LicenseError("A JSON object is required")
    return result


def read_bytes(path: Path) -> bytes:
    """Bound reads rather than trusting a file's reported size."""
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise LicenseError("File exceeds the 64 KiB limit")
    return data


def key_id(public_bytes: bytes) -> str:
    if len(public_bytes) != 32:
        raise LicenseError("An Ed25519 public key must have 32 bytes")
    return hashlib.sha256(public_bytes).hexdigest()[:32]


def load_public_key_file(path: Path) -> tuple[str, str]:
    obj = strict_json(read_bytes(path))
    if (
        set(obj) != {"schema_version", "key_id", "public_key"}
        or type(obj["schema_version"]) is not int
        or obj["schema_version"] != 1
    ):
        raise LicenseError("Choose a publisher public-key JSON file (schema 1), not a private key")
    raw = decode64(obj["public_key"], 32)
    if obj["key_id"] != key_id(raw):
        raise LicenseError("Public-key identifier does not match its key")
    return obj["key_id"], obj["public_key"]


def version_tuple(value: str) -> tuple[int, int, int]:
    clean = value.split("-")[0].split("+")[0].strip() if isinstance(value, str) else value
    if not isinstance(clean, str) or not re.fullmatch(VERSION_PATTERN, clean):
        raise LicenseError("Version must be three nonnegative integers, such as 1.0.0")
    return tuple(map(int, clean.split(".")))


def utc_time(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise LicenseError("Dates must use UTC: YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise LicenseError("Invalid UTC date") from exc


def utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise LicenseError("A timezone-aware date is required")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def uuid_text(value: Any) -> str:
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError, TypeError) as exc:
        raise LicenseError("Invalid canonical identifier") from exc
    return value


@dataclass(frozen=True)
class License:
    """Authentic licence claims, independent of current applicability."""

    license_id: str
    licensee: str
    issued_at: datetime
    expires_at: datetime
    max_version: str | None
    installation_id: str | None
    edition: str = "laboratory"

    def check(self, *, version: str, installation_id: str | None = None, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise LicenseError("Current time must be timezone-aware")
        if self.issued_at > now + timedelta(minutes=5):
            raise LicenseError("Licence issue time is in the future. Check the computer's date and time.")
        if self.expires_at is not None and now >= self.expires_at:
            raise LicenseError("This licence has expired. Your calculation models and report files are unchanged.")
        if self.max_version is not None and version_tuple(version) > version_tuple(self.max_version):
            raise LicenseError(
                f"This licence covers versions through {self.max_version}; this application is {version}."
            )
        version_tuple(version)
        if self.installation_id is not None and self.installation_id != installation_id:
            raise LicenseError("This licence belongs to another workstation. Request a replacement licence.")


def parse_claims(obj: dict[str, Any]) -> License:
    """Validate the complete signed schema; reject unsupported claims."""
    fields = {
        "schema_version",
        "product",
        "license_id",
        "licensee",
        "issued_at",
        "expires_at",
        "max_version",
        "installation_id",
        "edition",
    }
    if set(obj) != fields or type(obj["schema_version"]) is not int or obj["schema_version"] != 1:
        raise LicenseError("Unsupported licence schema or fields")
    if obj["product"] != PRODUCT_ID or obj["edition"] not in {"laboratory", "enterprise", "standard"}:
        raise LicenseError("This licence is not for the supported EffSuite product or edition")
    name = obj["licensee"]
    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 200
        or name != name.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
    ):
        raise LicenseError("Enter a laboratory/customer name of 1–200 printable characters")
    issued = utc_time(obj["issued_at"])
    expires = utc_time(obj["expires_at"])
    if expires is not None and expires <= issued:
        raise LicenseError("Expiry must be later than the issue time")
    if obj["max_version"] is not None:
        version_tuple(obj["max_version"])
    if obj["installation_id"] is not None:
        uuid_text(obj["installation_id"])
    return License(
        uuid_text(obj["license_id"]), name, issued, expires, obj["max_version"], obj["installation_id"], obj["edition"]
    )


def verify_license(
    data: bytes,
    public_keys: Mapping[str, str],
    *,
    version: str,
    installation_id: str | None = None,
    now: datetime | None = None,
) -> License:
    """Authenticate with digital signature before trusting any claims, then check applicability."""
    envelope = strict_json(data)
    if set(envelope) != {"key_id", "payload", "signature"}:
        raise LicenseError("Unsupported signed licence envelope")
    kid = envelope["key_id"]
    if not isinstance(kid, str) or kid not in public_keys:
        raise LicenseError("Licence issuer is not trusted by this EffSuite build")
    public = decode64(public_keys[kid], 32)
    if key_id(public) != kid:
        raise LicenseError("Application public-key configuration is invalid")
    payload, signature = decode64(envelope["payload"]), decode64(envelope["signature"], 64)
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, DOMAIN + payload)
    except InvalidSignature as exc:
        raise LicenseError("Licence signature is invalid; the file has been modified or corrupted") from exc
    licence = parse_claims(strict_json(payload))
    licence.check(version=version, installation_id=installation_id, now=now)
    return licence
