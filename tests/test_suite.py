"""Actual native workflows and user-facing input validation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from effsuite.app_cli import example_path
from effsuite.model_io import calibration_rows,normalize_nuclides,fields
from effsuite.parallel_coincidence import CoincidenceError,CalculationCancelled
from effsuite.suite import run_project,validate_project,engine_folder


class SuiteTests(unittest.TestCase):
    def setUp(self):self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
    def tearDown(self):self.temporary.cleanup()
    def example(self,mode):return json.loads(example_path(mode).read_text())
    def test_nuclides_accept_simple_spelling_and_commas(self):
        self.assertEqual(normalize_nuclides(["Co60,Cs-134 Eu152","Co-60"]),["CO-60","CS-134","EU-152"])
    def test_calibration_percent_is_not_silently_treated_as_fraction(self):
        p=self.root/"cal.csv";p.write_text("energy_keV,efficiency,u_rel_percent\n100,5,3\n1000,2,3\n")
        with self.assertRaises(CoincidenceError):calibration_rows(p)
    def test_malformed_first_data_row_is_not_silently_skipped(self):
        p=self.root/"cal.txt";p.write_text("100 bad 3\n200 .01 3\n1000 .005 3\n")
        with self.assertRaises(CoincidenceError):calibration_rows(p)
    def test_invalid_geometry_model_fails_before_execution(self):
        p=self.example("well");p["detector"][3]=1000
        with self.assertRaises(CoincidenceError):validate_project(p)
    def test_all_native_geometries_have_expected_original_field_counts(self):
        self.assertEqual([len(fields(m,"detector")) for m in ["cylindrical","marinelli","well"]],[19,16,7])
    def test_existing_output_is_preserved(self):
        p=self.root/"existing";p.mkdir();(p/"keep").write_text("unchanged")
        with self.assertRaises(CoincidenceError):run_project(self.example("cylinder"),p)
        self.assertEqual((p/"keep").read_text(),"unchanged")
    def test_cancelled_job_does_not_publish_partial_output(self):
        stop=threading.Event();stop.set();p=self.root/"cancelled"
        with self.assertRaises(CalculationCancelled):run_project(self.example("cylinder"),p,cancel=stop)
        self.assertFalse(p.exists());self.assertFalse(list(self.root.glob(".effsuite-job-*")))
    def test_identity_transfer_is_one_for_all_three_geometries(self):
        for name in ["cylinder","marinelli","well"]:
            with self.subTest(name=name):
                p=self.example(name);p.update(task="transfer",standard=p["sample"],calibration=[{"energy_keV":100.,"efficiency":.01,"u_rel_percent":3.},{"energy_keV":1000.,"efficiency":.005,"u_rel_percent":3.}])
                result=run_project(p,self.root/name)
                self.assertEqual([r["transfer_factor"] for r in result["efficiency"]],[1.,1.])
                self.assertTrue((self.root/name/"report.html").is_file())
                self.assertIn("<svg",(self.root/name/"report.html").read_text())
    def test_cli_matches_shared_service_for_all_three_geometries(self):
        for name in ["cylinder","marinelli","well"]:
            with self.subTest(name=name):
                p=self.example(name);p["workers"]=1;p["verify_serial"]=False
                service=run_project(p,self.root/(name+"_service"))
                p["workers"]=2;file=self.root/(name+".json");file.write_text(json.dumps(p))
                done=subprocess.run([sys.executable,"-m","effsuite.app_cli","run",str(file),"--out",str(self.root/(name+"_cli"))],capture_output=True,text=True,timeout=180)
                self.assertEqual(done.returncode,0,done.stderr)
                cli=json.loads(done.stdout)
                self.assertEqual(cli["efficiency"],service["efficiency"])
                self.assertEqual(cli["summing"],service["summing"])
                co=next(r for r in cli["summing"] if r["nuclide"]=="CO-60" and r["energy_keV"]==1173)
                self.assertGreater(co["activity_multiplier"],1.)
                if name!="well":
                    tiny=next(r for r in cli["summing"] if r["nuclide"]=="CO-60" and r["energy_keV"]==2506)
                    self.assertTrue(0<tiny["activity_multiplier"]<.0005)
    def test_cli_batch_and_plot_geometry(self):
        from effsuite.app_cli import main as cli_main
        plot_out=self.root/"geom_test.png"
        rc=cli_main(["plot-geometry","--geometry","cylinder","--detector","Low-energy","--sample","Water","--out",str(plot_out)])
        self.assertEqual(rc,0)
        self.assertTrue(plot_out.is_file())
        batch_csv=self.root/"jobs.csv"
        batch_csv.write_text(
            "id,geometry,detector,sample,sample_height_mm,sample_material,sample_density_g_cm3,sample_gap_mm,standard,calibration,library,certificate,nuclides,output_cal,output_nlb,output_ctf\n"
            "Job1,cylinder,Low-energy,Water,25.0,,,,Water,,, ,CO-60,,,\n",
            encoding="utf-8",
        )
        batch_out=self.root/"batch_out"
        rc2=cli_main(["batch",str(batch_csv),"--out",str(batch_out),"--workers","1","--plot-geometry"])
        self.assertEqual(rc2,0)
        self.assertTrue((batch_out/"batch_summary.csv").is_file())
        self.assertTrue((batch_out/"Job1/geometry.png").is_file())
        res_json=json.loads((batch_out/"Job1/results.json").read_text(encoding="utf-8"))
        self.assertEqual(res_json["project"]["sample"][1],25.0)

    def test_detector_geometry_cross_compatibility_efftran_and_mefftran(self):
        from effsuite.model_io import read_model, validate_model
        cyl_det = Path("src/effsuite/assets/engines/cylindrical/Detector/High-energy.txt")
        mar_det = Path("src/effsuite/assets/engines/marinelli/Detector/High-energy.txt")

        # 1. Loading EFFTRAN 19-line detector in Marinelli mode
        m = read_model("marinelli", "detector", cyl_det)
        self.assertEqual(len(m), 16)
        self.assertEqual(m, read_model("marinelli", "detector", mar_det))

        # 2. Loading MEFFTRAN 16-line detector in Cylindrical mode
        c = read_model("cylindrical", "detector", mar_det)
        self.assertEqual(len(c), 19)
        self.assertEqual(c[:12], m[:12])
        self.assertEqual(c[12:14], [0.0, 0.0])
        self.assertEqual(c[14:18], m[12:])
        self.assertEqual(c[18], "copper")
