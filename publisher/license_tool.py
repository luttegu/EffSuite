"""Generate encrypted signing keys and issue signed offline licences for EffSuite.

CLI: python -m publisher.license_tool --help
"""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from effsuite.licensing.verification import (
    DOMAIN,
    PRODUCT_ID,
    LicenseError,
    encode64,
    key_id,
    parse_claims,
    strict_json,
    read_bytes,
    utc_text,
    uuid_text,
)


def write_new(path: Path, data: bytes, mode: int = 0o600) -> None:
    """Never overwrite a signing key or an already-issued licence accidentally."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def public_document(key: Ed25519PrivateKey) -> dict:
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {"schema_version": 1, "key_id": key_id(raw), "public_key": encode64(raw)}


def load_public_key_file(path: Path) -> tuple[str, str]:
    doc = strict_json(read_bytes(path))
    return doc["key_id"], doc["public_key"]


def generate_keys(private_path: Path, public_path: Path, password: str) -> None:
    """Create a fresh encrypted PKCS#8 Ed25519 key and a public-only JSON file."""
    if len(password) < 8:
        raise LicenseError("Use a signing-key passphrase of at least 8 characters")
    if private_path.resolve() == public_path.resolve() or private_path.exists() or public_path.exists():
        raise LicenseError("Choose two different, new key filenames. Existing keys are never overwritten.")
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    write_new(private_path, private)
    write_new(public_path, (json.dumps(public_document(key), indent=2) + "\n").encode(), 0o644)


def load_private(path: Path, password: str) -> Ed25519PrivateKey:
    try:
        key = serialization.load_pem_private_key(read_bytes(path), password=password.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise LicenseError("Could not unlock the private key. Check the file and passphrase.") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise LicenseError("The key must be an Ed25519 private signing key")
    return key


def issue(
    key: Ed25519PrivateKey,
    *,
    licensee: str,
    expires_at: str,
    edition: str = "laboratory",
    max_version: str | None = None,
    installation_id: str | None = None,
    now: datetime | None = None,
) -> bytes:
    """Issue a signed licence file; its required expiry is a signed claim."""
    payload = {
        "schema_version": 1,
        "product": PRODUCT_ID,
        "license_id": str(uuid.uuid4()),
        "licensee": licensee.strip(),
        "edition": edition,
        "issued_at": utc_text(now or datetime.now(timezone.utc)),
        "expires_at": expires_at,
        "max_version": max_version,
        "installation_id": installation_id,
    }
    parse_claims(payload)
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    envelope = {
        "key_id": public_document(key)["key_id"],
        "payload": encode64(data),
        "signature": encode64(key.sign(DOMAIN + data)),
    }
    return (json.dumps(envelope, indent=2) + "\n").encode("utf-8")


def read_request(path: Path) -> dict:
    data = strict_json(read_bytes(path))
    if data.get("schema_version") != 1 or data.get("product") != PRODUCT_ID:
        raise LicenseError("Invalid customer activation request file")
    uuid_text(data.get("installation_id"))
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="EffSuite publisher licence management tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate-keys", help="Generate a new Ed25519 signing keypair")
    gen.add_argument("--private", type=Path, required=True, help="Output path for encrypted private key (.pem)")
    gen.add_argument("--public", type=Path, required=True, help="Output path for public key (.json)")

    iss = subparsers.add_parser("issue", help="Issue a signed customer licence")
    iss.add_argument("--private", type=Path, required=True, help="Publisher encrypted private key (.pem)")
    iss.add_argument("--out", type=Path, required=True, help="Output path for customer licence (.efflic)")
    iss.add_argument("--licensee", type=str, required=True, help="Customer or laboratory name")
    iss.add_argument("--expires", type=str, required=True, help="UTC expiry ISO date (e.g. 2027-12-31T00:00:00Z)")
    iss.add_argument("--edition", type=str, default="laboratory", choices=["laboratory", "standard", "enterprise"])
    iss.add_argument("--max-version", type=str, default=None, help="Optional max version ceiling (e.g. 1.99.99)")
    iss.add_argument("--installation-id", type=str, default=None, help="Optional customer installation UUID")
    iss.add_argument("--request", type=Path, default=None, help="Optional customer activation request (.req) to read installation ID from")

    insp = subparsers.add_parser("inspect", help="Inspect a signed licence file")
    insp.add_argument("license_file", type=Path, help="Licence file to inspect (.efflic)")

    args = parser.parse_args()

    if args.command == "generate-keys":
        pw1 = getpass.getpass("Enter passphrase for new private key: ")
        pw2 = getpass.getpass("Confirm passphrase: ")
        if pw1 != pw2:
            print("Error: Passphrases do not match.")
            return 1
        generate_keys(args.private, args.public, pw1)
        print(f"Keypair successfully generated:\n  Private: {args.private}\n  Public:  {args.public}")
        return 0

    if args.command == "issue":
        pw = getpass.getpass("Enter passphrase to unlock private key: ")
        key = load_private(args.private, pw)
        inst_id = args.installation_id
        if args.request:
            req_data = read_request(args.request)
            inst_id = req_data.get("installation_id")
        lic_bytes = issue(
            key,
            licensee=args.licensee,
            expires_at=args.expires,
            edition=args.edition,
            max_version=args.max_version,
            installation_id=inst_id,
        )
        write_new(args.out, lic_bytes, 0o644)
        print(f"Licence successfully issued to {args.licensee}:\n  File: {args.out}")
        return 0

    if args.command == "inspect":
        envelope = strict_json(read_bytes(args.license_file))
        raw_payload = strict_json(decode64(envelope["payload"]))
        print("Licence file contents:")
        print(json.dumps(raw_payload, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
