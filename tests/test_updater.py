"""Update check: version comparison, release selection and verified download (no network)."""
import hashlib
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from effsuite import updater


def release_item(tag, prerelease=True, draft=False, payload=b"setup", name=None, url=None, digest=True):
    version = tag.removeprefix("v")
    name = name or f"EffSuite_{version}_Setup.exe"
    asset = {"name": name, "size": len(payload),
             "browser_download_url": url or f"{updater.DOWNLOAD_PREFIX}{tag}/{name}"}
    if digest:
        asset["digest"] = "sha256:" + hashlib.sha256(payload).hexdigest()
    return {"tag_name": tag, "name": f"EffSuite {tag}", "body": "Notes", "draft": draft,
            "prerelease": prerelease, "html_url": f"{updater.RELEASES_PAGE}/tag/{tag}", "assets": [asset]}


class FakeResponse(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}


class VersionTests(unittest.TestCase):
    def test_numeric_comparison(self):
        self.assertTrue(updater.is_newer("0.3.10", "0.3.9"))
        self.assertTrue(updater.is_newer("v0.4.0", "0.3.3"))
        self.assertFalse(updater.is_newer("0.3.3", "0.3.3"))
        self.assertFalse(updater.is_newer("0.4", "0.4.0"))
        self.assertFalse(updater.is_newer("0.3.2", "0.3.3"))

    def test_unparseable_is_never_newer(self):
        self.assertIsNone(updater.parse_version("v1.0-rc1"))
        self.assertFalse(updater.is_newer("v9.0-beta", "0.3.3"))
        self.assertFalse(updater.is_newer("1.0", "dev"))


class ReleaseSelectionTests(unittest.TestCase):
    def test_newest_by_version_not_by_list_order(self):
        items = [release_item("v0.3.4"), release_item("v0.3.10"), release_item("v0.3.9")]
        self.assertEqual(updater.newest_release(items).version, "0.3.10")

    def test_prereleases_included_drafts_skipped(self):
        items = [release_item("v0.5.0", draft=True), release_item("v0.4.0", prerelease=True)]
        self.assertEqual(updater.newest_release(items).version, "0.4.0")

    def test_rejects_foreign_or_misnamed_installer(self):
        self.assertIsNone(updater.release_from_json(release_item("v0.4.0", url="https://example.com/EffSuite_0.4.0_Setup.exe")))
        self.assertIsNone(updater.release_from_json(release_item("v0.4.0", name="EffSuite_0.3.0_Setup.exe")))
        self.assertIsNone(updater.release_from_json({"tag_name": "v0.4.0", "assets": []}))

    def test_digest_parsed(self):
        release = updater.release_from_json(release_item("v0.4.0", payload=b"abc"))
        self.assertEqual(release.sha256, hashlib.sha256(b"abc").hexdigest())
        self.assertIsNone(updater.release_from_json(release_item("v0.4.0", digest=False)).sha256)

    def test_check_for_update(self):
        items = [release_item("v0.3.3"), release_item("v0.4.0")]
        self.assertEqual(updater.check_for_update("0.3.3", fetch=lambda: items).version, "0.4.0")
        self.assertIsNone(updater.check_for_update("0.4.0", fetch=lambda: items))
        self.assertIsNone(updater.check_for_update("0.4.0", fetch=lambda: []))

    def test_network_error_becomes_update_error(self):
        import urllib.error
        with patch.object(updater, "_request", side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(updater.UpdateError, "Could not reach GitHub"):
                updater.fetch_releases()


class ScheduleTests(unittest.TestCase):
    def test_daily_check(self):
        now = 1_000_000.0
        self.assertTrue(updater.should_check_automatically({}, now))
        self.assertFalse(updater.should_check_automatically({updater.SETTING_LAST: now - 3600}, now))
        self.assertTrue(updater.should_check_automatically({updater.SETTING_LAST: now - 2 * 86400}, now))
        self.assertTrue(updater.should_check_automatically({updater.SETTING_LAST: now + 3600}, now))   # clock moved back
        self.assertTrue(updater.should_check_automatically({updater.SETTING_LAST: "bad"}, now))

    def test_disabled(self):
        self.assertFalse(updater.should_check_automatically({updater.SETTING_AUTO: False}, 0))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def download(self, release, data, **kwargs):
        with patch.object(updater, "_request", return_value=FakeResponse(data)):
            return updater.download_installer(release, self.folder, **kwargs)

    def test_verified_download(self):
        payload = b"x" * 600_000
        release = updater.release_from_json(release_item("v0.4.0", payload=payload))
        seen = []
        path = self.download(release, payload, progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(path.read_bytes(), payload)
        self.assertEqual(seen[-1], (len(payload), len(payload)))

    def test_hash_mismatch_deletes_file(self):
        release = updater.release_from_json(release_item("v0.4.0", payload=b"good"))
        with self.assertRaisesRegex(updater.UpdateError, "SHA-256"):
            self.download(release, b"evil")
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_incomplete_download_deletes_file(self):
        release = updater.release_from_json(release_item("v0.4.0", payload=b"complete"))
        with self.assertRaisesRegex(updater.UpdateError, "incomplete"):
            self.download(release, b"comp")
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_cancel(self):
        release = updater.release_from_json(release_item("v0.4.0", payload=b"data"))
        cancel = threading.Event()
        cancel.set()
        with self.assertRaisesRegex(updater.UpdateError, "cancelled"):
            self.download(release, b"data", cancel=cancel)
        self.assertEqual(list(self.folder.iterdir()), [])


class InstallTests(unittest.TestCase):
    def test_arguments(self):
        self.assertIn("/SILENT", updater.installer_arguments(True))
        self.assertIn("/RELAUNCH=1", updater.installer_arguments(True))
        self.assertEqual(updater.installer_arguments(False), ["/ALLUSERS"])

    def test_source_checkout_does_not_install(self):
        with patch.object(updater.sys, "frozen", False, create=True):
            self.assertFalse(updater.can_install())

    def test_writable_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(updater.install_folder_writable(folder))
        self.assertFalse(updater.install_folder_writable(Path(folder) / "missing"))


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from effsuite.gui import MainWindow
except ImportError:
    MainWindow = None


@unittest.skipIf(MainWindow is None, "Install .[desktop] for GUI tests")
class GuiUpdateTests(unittest.TestCase):
    """Startup offer, skipped versions and settings, with a temporary settings.json."""
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from effsuite import paths
        self.tmp = tempfile.TemporaryDirectory()
        settings = Path(self.tmp.name) / "settings.json"
        self.patches = [patch.object(paths, "settings_file", lambda: settings),
                        patch.object(MainWindow, "check_first_run_disclaimer", lambda window: None)]
        for p in self.patches:
            p.start()
        self.window = MainWindow()
        self.offered = []
        self.window.show_update_dialog = self.offered.append

    def tearDown(self):
        self.window.dirty = False
        self.window.close()
        self.window.material_editor.deleteLater()
        self.window.deleteLater()   # otherwise destroyed after QApplication at exit: segfault
        self.app.processEvents()
        del self.window
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_startup_offer_and_last_check_saved(self):
        from effsuite.paths import load_settings
        release = updater.release_from_json(release_item("v99.0.0"))
        self.window._update_checked(release, False)
        self.assertEqual(self.offered, [release])
        self.assertFalse(updater.should_check_automatically(load_settings()))

    def test_skipped_version_not_offered_at_startup_but_on_manual_check(self):
        from effsuite.paths import save_settings
        save_settings({updater.SETTING_SKIPPED: "99.0.0"})
        release = updater.release_from_json(release_item("v99.0.0"))
        self.window._update_checked(release, False)
        self.assertEqual(self.offered, [])
        self.window._update_checked(release, True)
        self.assertEqual(self.offered, [release])

    def test_no_offer_while_calculating(self):
        release = updater.release_from_json(release_item("v99.0.0"))
        self.window.thread = object()
        try:
            self.window._update_checked(release, False)
            self.assertEqual(self.offered, [])
            self.assertIs(self.window._pending_release, release)
        finally:
            self.window.thread = None
            self.window._pending_release = None

    def test_up_to_date_message_only_on_manual_check(self):
        with patch.object(QMessageBox, "information") as info:
            self.window._update_checked(None, False)
            info.assert_not_called()
            self.window._update_checked(None, True)
            info.assert_called_once()

    def test_startup_toggle_saved(self):
        from effsuite.paths import load_settings
        self.window._set_auto_update_check(False)
        self.assertFalse(updater.should_check_automatically(load_settings()))


if __name__ == "__main__":
    unittest.main()
