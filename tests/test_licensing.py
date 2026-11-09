"""Automated tests for EffSuite Ed25519 offline licensing and workstation activation."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from publisher.license_tool import (
    generate_keys,
    issue,
    load_private,
    load_public_key_file,
    public_document,
    read_request,
)
from effsuite.licensing.config import PUBLIC_KEYS, PRODUCT_ID
from effsuite.licensing.dates import readable_day, readable_utc, whole_last_day
from effsuite.licensing.storage import LicenseStore, default_store
from effsuite.licensing.verification import (
    DOMAIN,
    LicenseError,
    decode64,
    encode64,
    verify_license,
)
from effsuite.paths import get_effsuite_root, get_licensing_dir, get_results_dir


NOW = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
EXPIRY = "2027-11-07T00:00:00Z"


class LicensingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.td = Path(self.temp_dir.name)
        self.key = Ed25519PrivateKey.generate()
        self.doc = public_document(self.key)
        self.public_keys = {self.doc["key_id"]: self.doc["public_key"]}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_keypair_generation_encryption_and_loading(self):
        priv_path = self.td / "test_private.pem"
        pub_path = self.td / "test_public.json"
        passphrase = "Secure-Test-Passphrase-2026"

        generate_keys(priv_path, pub_path, passphrase)
        self.assertTrue(priv_path.is_file())
        self.assertTrue(pub_path.is_file())
        self.assertTrue(priv_path.read_bytes().startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"))

        # Cannot overwrite existing key
        with self.assertRaises(LicenseError):
            generate_keys(priv_path, pub_path, passphrase)

        # Load with right passphrase
        loaded_key = load_private(priv_path, passphrase)
        self.assertIsNotNone(loaded_key)

        # Fail with wrong passphrase
        with self.assertRaises(LicenseError):
            load_private(priv_path, "Wrong-Passphrase")

        # Load public key
        kid, pub_b64 = load_public_key_file(pub_path)
        expected_doc = public_document(loaded_key)
        self.assertEqual(kid, expected_doc["key_id"])
        self.assertEqual(len(decode64(pub_b64)), 32)

    def test_valid_issuance_and_verification(self):
        data = issue(
            self.key,
            licensee="Laboratoire National Henri Becquerel",
            edition="laboratory",
            expires_at=EXPIRY,
            now=NOW,
        )
        lic = verify_license(data, self.public_keys, version="1.0.0", now=NOW)
        self.assertEqual(lic.licensee, "Laboratoire National Henri Becquerel")
        self.assertEqual(lic.edition, "laboratory")
        self.assertIsNone(lic.installation_id)  # Lab license: unlocked

    def test_expiry_boundary(self):
        data = issue(
            self.key,
            licensee="Test Lab",
            expires_at=EXPIRY,
            now=NOW,
        )
        lic = verify_license(data, self.public_keys, version="1.0.0", now=NOW)
        self.assertIsNotNone(lic.expires_at)

        # 1 microsecond before cut-off is valid
        lic.check(version="1.0.0", now=lic.expires_at - timedelta(microseconds=1))

        # At cut-off and after is rejected
        with self.assertRaises(LicenseError):
            lic.check(version="1.0.0", now=lic.expires_at)
        with self.assertRaises(LicenseError):
            lic.check(version="1.0.0", now=lic.expires_at + timedelta(days=1))

    def test_tampering_rejected(self):
        raw = issue(
            self.key,
            licensee="Authentic Laboratory",
            expires_at=EXPIRY,
            now=NOW,
        )
        envelope = json.loads(raw)

        # Modify claims payload
        claims = json.loads(decode64(envelope["payload"]))
        claims["licensee"] = "Pirated Laboratory"
        envelope["payload"] = encode64(json.dumps(claims).encode("utf-8"))

        with self.assertRaises(LicenseError):
            verify_license(json.dumps(envelope).encode("utf-8"), self.public_keys, version="1.0.0", now=NOW)

    def test_installation_id_workstation_binding(self):
        workstation_a = str(uuid.uuid4())
        workstation_b = str(uuid.uuid4())

        data = issue(
            self.key,
            licensee="Specific Workstation Lab",
            installation_id=workstation_a,
            expires_at=EXPIRY,
            now=NOW,
        )

        # Valid on workstation A
        lic_a = verify_license(data, self.public_keys, version="1.0.0", installation_id=workstation_a, now=NOW)
        self.assertEqual(lic_a.installation_id, workstation_a)

        # Rejected on workstation B
        with self.assertRaises(LicenseError):
            verify_license(data, self.public_keys, version="1.0.0", installation_id=workstation_b, now=NOW)

    def test_version_ceiling(self):
        data = issue(
            self.key,
            licensee="Standard Licensee",
            expires_at=EXPIRY,
            max_version="1.0.0",
            now=NOW,
        )

        # v1.0.0 works
        verify_license(data, self.public_keys, version="1.0.0", now=NOW)
        # v0.9.0 works
        verify_license(data, self.public_keys, version="0.9.0", now=NOW)
        # v1.1.0 rejected
        with self.assertRaises(LicenseError):
            verify_license(data, self.public_keys, version="1.1.0", now=NOW)

    def test_store_atomic_import_and_rollback_detection(self):
        clock = [NOW]
        store_dir = self.td / "store"
        store = LicenseStore(store_dir, self.public_keys, version="1.0.0", clock=lambda: clock[0])

        # Initially unlicensed
        with self.assertRaises(LicenseError):
            store.current()

        # Import valid license
        lic_data = issue(
            self.key,
            licensee="Initial Lab",
            expires_at=EXPIRY,
            now=NOW,
        )
        imported = store.import_license(lic_data)
        self.assertEqual(imported.licensee, "Initial Lab")
        self.assertEqual(store.current().licensee, "Initial Lab")

        # Attempt to import corrupted data does not damage existing license
        with self.assertRaises(LicenseError):
            store.import_license(b"corrupted invalid license")
        self.assertEqual(store.current().licensee, "Initial Lab")

        # Time moves forward 3 days: works
        clock[0] = NOW + timedelta(days=3)
        self.assertEqual(store.current().licensee, "Initial Lab")

        # Time rolls backwards: rejected
        clock[0] = NOW + timedelta(days=1)
        with self.assertRaises(LicenseError):
            store.current()

    def test_activation_request_roundtrip(self):
        store_dir = self.td / "store_req"
        store = LicenseStore(store_dir, self.public_keys, version="1.0.0", clock=lambda: NOW)

        req_doc = store.request_document()
        self.assertEqual(req_doc["product"], PRODUCT_ID)
        self.assertEqual(req_doc["application_version"], "1.0.0")
        self.assertEqual(req_doc["installation_id"], store.installation_id())

        req_file = self.td / "customer.req"
        req_file.write_text(json.dumps(req_doc), encoding="utf-8")
        parsed = read_request(req_file)
        self.assertEqual(parsed["installation_id"], store.installation_id())

    def test_official_lab_license_verification(self):
        lab_lic_file = Path("publisher/official_keys/default_lab_license.efflic")
        self.assertTrue(lab_lic_file.is_file())
        store = LicenseStore(self.td / "official_store", PUBLIC_KEYS, version="1.0.0")
        lic = store.verify(lab_lic_file.read_bytes())
        self.assertEqual(lic.licensee, "Gamma Spectrometry Laboratory")
        self.assertEqual(lic.edition, "laboratory")
        self.assertIsNone(lic.installation_id)

    def test_paths_default_resolution(self):
        root = get_effsuite_root()
        self.assertIsNotNone(root)
        lic_dir = get_licensing_dir()
        self.assertIsNotNone(lic_dir)
        res_dir = get_results_dir()
        self.assertIsNotNone(res_dir)

    def test_cli_license_flow(self):
        from effsuite.app_cli import main as cli_main
        from io import StringIO
        import unittest.mock as mock

        cli_lic_dir = self.td / "cli_licensing"
        env = {"EFFSUITE_LICENSE_DIR": str(cli_lic_dir)}

        with mock.patch.dict(os.environ, env):
            # 1. Default lab license is active out of the box
            buf1 = StringIO()
            with mock.patch("sys.stdout", new=buf1):
                ret = cli_main(["license", "--status"])
                self.assertEqual(ret, 0)
            self.assertIn("ACTIVE & QUALIFIED", buf1.getvalue())
            self.assertIn("Gamma Spectrometry Laboratory", buf1.getvalue())

            # 2. Export activation request
            req_path = self.td / "cli_req.req"
            with mock.patch("sys.stdout", new=StringIO()):
                ret = cli_main(["license", "--request", str(req_path)])
                self.assertEqual(ret, 0)
            self.assertTrue(req_path.is_file())
            req_data = json.loads(req_path.read_text(encoding="utf-8"))
            self.assertEqual(req_data["product"], "effsuite")

            # 3. Import official lab license explicitly
            official_lic = Path("publisher/official_keys/default_lab_license.efflic")
            with mock.patch("sys.stdout", new=StringIO()):
                ret = cli_main(["license", "--import", str(official_lic)])
                self.assertEqual(ret, 0)

            # 4. Active status after import
            buf = StringIO()
            with mock.patch("sys.stdout", new=buf):
                ret = cli_main(["license", "--status"])
                self.assertEqual(ret, 0)
            output = buf.getvalue()
            self.assertIn("ACTIVE & QUALIFIED", output)
            self.assertIn("Gamma Spectrometry Laboratory", output)


if __name__ == "__main__":
    unittest.main()
