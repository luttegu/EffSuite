"""The bundled materials are only the originals; each user keeps their own in a (changeable) data folder."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from effsuite import paths
from effsuite.model_io import COMMON_DATA, default_material_density, find_material_file, material_names

# Union of the EFFTRAN 5.0 and MEFFTRAN 1.9 distributions.
ORIGINAL_MATERIALS = {"CLYC", "CZT", "CsI", "Ge", "LaBr3", "NaI", "air", "aluminium", "beryllium", "cellulose",
                      "copper", "heavy", "iron", "lead", "plexiglass", "polystyrene", "silica", "soil", "vacuum", "water"}


class BundledMaterials(unittest.TestCase):
    def test_only_original_materials_are_bundled(self):
        for folder in ("Composition", "Material"):
            names = {p.stem for p in (COMMON_DATA/folder).glob("*.txt")}
            self.assertEqual(names, ORIGINAL_MATERIALS, folder)

    def test_well_models_are_always_bundled(self):
        # The original WEFFTRAN has no usable well models: EffSuite's own are kept.
        from effsuite.model_io import ASSETS
        for name in ("Detector/well.txt", "Sample/Sample.txt", "Standard/Standard.txt"):
            self.assertTrue((ASSETS/"well"/name).is_file(), name)

    def test_bundled_models_use_only_original_materials(self):
        from effsuite.model_io import ASSETS
        for path in ASSETS.glob("*/[DSs]*/*.txt"):
            if path.parent.name not in ("Detector", "Sample", "Standard"):
                continue
            for line in path.read_text().splitlines():
                word = line.strip()
                if word and not word.replace(".", "").replace("-", "").isdigit():
                    self.assertIn(word, ORIGINAL_MATERIALS, path)


class DataFolderSetting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = {"APPDATA": str(self.root/"appdata"), "XDG_CONFIG_HOME": str(self.root/"config")}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("EFFSUITE_DATA", None)   # restored by patch.dict

    def test_default_is_builtin_then_saved_then_environment(self):
        self.assertEqual(paths.get_data_dir(), paths.builtin_data_dir())
        self.assertEqual(paths.data_dir_source(), "built-in")
        chosen = self.root/"my data"
        self.assertEqual(paths.set_data_dir(chosen), chosen.resolve())
        self.assertTrue((chosen/"Composition").is_dir() and (chosen/"Material").is_dir())
        self.assertEqual(paths.data_dir_source(), "settings")
        self.assertTrue(paths.settings_file().is_file())
        with patch.dict(os.environ, {"EFFSUITE_DATA": str(self.root/"env")}):
            self.assertEqual(paths.get_data_dir(), self.root/"env")
            self.assertEqual(paths.data_dir_source(), "environment")
        self.assertEqual(paths.set_data_dir(None), paths.builtin_data_dir())
        self.assertEqual(paths.data_dir_source(), "built-in")

    def test_user_materials_are_found_and_shadow_the_originals(self):
        chosen = paths.set_data_dir(self.root/"lab")
        (chosen/"Composition"/"my_resin.txt").write_text(" 1.18\nC5H8O2\n 1\n")
        (chosen/"Composition"/"water.txt").write_text(" 0.998\nH2O\n 1\n")
        self.assertIn("my_resin", material_names())
        self.assertIn("lead", material_names())   # the originals stay available
        self.assertAlmostEqual(default_material_density("my_resin"), 1.18)
        self.assertAlmostEqual(default_material_density("water"), 0.998)
        self.assertEqual(find_material_file("lead"), COMMON_DATA/"Composition"/"lead.txt")
        # A project's own folder comes before the default one.
        project = self.root/"project"
        (project/"Composition").mkdir(parents=True)
        (project/"Composition"/"water.txt").write_text(" 0.95\nH2O\n 1\n")
        self.assertAlmostEqual(default_material_density("water", project), 0.95)

    def test_cli_config_round_trip(self):
        import contextlib, io
        from effsuite.app_cli import main
        chosen = self.root/"cli data"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["config", "--data-dir", str(chosen)]), 0)
            self.assertEqual(main(["config"]), 0)
        self.assertEqual(paths.get_data_dir(), chosen.resolve())
        self.assertIn("(from settings)", out.getvalue())
        self.assertTrue((chosen/"Material").is_dir())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["config", "--reset-data-dir"]), 0)
        self.assertEqual(paths.data_dir_source(), "built-in")


class WellMaterialInDefaultFolder(unittest.TestCase):
    def test_well_run_uses_composition_only_material_from_default_folder(self):
        """A laboratory material only in the default data folder (no attenuation table yet):
        the well run finds it, XCOM creates its table there, and the provenance lists it."""
        from effsuite.suite import run_project
        fixture = Path(__file__).parent/"data"/"materials"/"Composition"/"Plastic_vial_det07.txt"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"EFFSUITE_DATA": str(Path(tmp)/"Data")}):
            data = paths.ensure_data_dir()
            (data/"Composition"/"Plastic_vial_det07.txt").write_bytes(fixture.read_bytes())
            source = [17.0, 20.75, 1.5, 1.5, 10.0, "water", "Plastic_vial_det07"]
            project = {"schema_version": 1, "geometry": "well", "task": "summing",
                       "detector": [72.0, 69.0, 0.7, 25.5, 43.0, "Ge", "aluminium"], "sample": source,
                       "nuclides": ["CO-60"], "workers": 1}
            result = run_project(project, Path(tmp)/"out")
            self.assertTrue((data/"Material"/"Plastic_vial_det07.txt").is_file())
            self.assertIn("Composition/Plastic_vial_det07.txt", result["scientific_data_sha256"])
            self.assertIn("zzaa.txt", result["scientific_data_sha256"])
            self.assertEqual(result["scientific_data_directory"], str(data))
            self.assertTrue(result["summing"])


if __name__ == "__main__":
    unittest.main()
