"""Choice of the user folder (data and results) with and without Genie 2000."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from effsuite import paths


class UserFolderChoice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.genie = self.base / "GENIE2K"
        self.home = self.base / "home"
        self.documents = self.home / "Documents"
        self.documents.mkdir(parents=True)
        self.temp = self.base / "temp"
        env = {k: v for k, v in os.environ.items()
               if k not in ("EFFSUITE_ROOT", "OneDrive", "OneDriveCommercial", "OneDriveConsumer")}
        env["LOCALAPPDATA"] = str(self.base / "LocalAppData")
        self.patches = [patch.object(paths, "GENIE2K_DIR", self.genie),
                        patch.object(paths, "get_real_documents_dir", lambda: self.documents),
                        patch.object(Path, "home", classmethod(lambda cls: self.home)),
                        patch.object(tempfile, "gettempdir", lambda: str(self.temp)),
                        patch.dict(os.environ, env, clear=True)]
        for p in self.patches:
            p.start()
        paths._find_effsuite_root.cache_clear()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        paths._find_effsuite_root.cache_clear()
        self.tmp.cleanup()

    def test_genie_workstation_uses_genie_folder(self):
        self.genie.mkdir()
        self.assertEqual(paths.get_effsuite_root(), self.genie / "EffSuite")

    def test_without_genie_uses_documents_and_never_creates_genie_folder(self):
        self.assertEqual(paths.get_effsuite_root(), self.documents / "EffSuite")
        self.assertFalse(self.genie.exists())

    def test_existing_genie_effsuite_folder_is_kept(self):
        (self.genie / "EffSuite").mkdir(parents=True)
        (self.documents / "EffSuite").mkdir()
        self.assertEqual(paths.get_effsuite_root(), self.genie / "EffSuite")

    def test_onedrive_documents_falls_back_to_profile_folder(self):
        self.documents = self.home / "OneDrive" / "Documents"
        self.documents.mkdir(parents=True)
        with patch.dict(os.environ, {"OneDrive": str(self.home / "OneDrive")}):
            self.assertEqual(paths.get_effsuite_root(), self.home / "EffSuite")

    def test_existing_onedrive_documents_folder_is_kept(self):
        self.documents = self.home / "OneDrive" / "Documents"
        (self.documents / "EffSuite").mkdir(parents=True)
        with patch.dict(os.environ, {"OneDrive": str(self.home / "OneDrive")}):
            self.assertEqual(paths.get_effsuite_root(), self.documents / "EffSuite")

    def test_environment_variable_wins(self):
        self.genie.mkdir()
        with patch.dict(os.environ, {"EFFSUITE_ROOT": str(self.base / "lab")}):
            self.assertEqual(paths.get_effsuite_root(), self.base / "lab")

    def test_onedrive_detection(self):
        with patch.dict(os.environ, {"OneDriveCommercial": r"C:\Users\x\OneDrive - Lab"}):
            self.assertTrue(paths.is_onedrive_path(Path(r"C:\Users\x\OneDrive - Lab\Documents")))
            self.assertFalse(paths.is_onedrive_path(Path(r"C:\Users\x\Documents")))
        self.assertTrue(paths.is_onedrive_path(Path(r"D:\OneDrive\Dokumenter")))


if __name__ == "__main__":
    unittest.main()
