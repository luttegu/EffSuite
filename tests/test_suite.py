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
                if name=="well":
                    p["nuclides"]=["CO-60","CS-134"]
                service=run_project(p,self.root/(name+"_service"))
                p["workers"]=0;file=self.root/(name+".json");file.write_text(json.dumps(p))
                done=subprocess.run([sys.executable,"-m","effsuite.app_cli","run",str(file),"--out",str(self.root/(name+"_cli"))],capture_output=True,text=True,timeout=300)
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

    def test_source_density_scaling_matches_heavywater_across_all_three_geometries(self):
        # Verify EFFTRAN 4.9 / MEFFTRAN 1.8 / WEFFTRAN 8th-line density scaling:
        # 'water' (rho0=1.0) with sample[7]=2.0 must match 'HeavyWater' (rho0=2.0) with sample[7]=2.0
        for name in ["cylinder", "marinelli", "well"]:
            with self.subTest(name=name):
                cal = [
                    {"energy_keV": 60.0, "efficiency": 0.02, "u_rel_percent": 3.0},
                    {"energy_keV": 661.7, "efficiency": 0.01, "u_rel_percent": 3.0},
                    {"energy_keV": 1332.5, "efficiency": 0.005, "u_rel_percent": 3.0},
                ]
                p_water2 = self.example(name)
                p_water2.update(task="both", nuclides=["CO-60"], workers=0, standard=list(p_water2["sample"]), calibration=cal)
                p_water2["standard"][5] = "water"
                p_water2["standard"][7] = 1.0
                p_water2["sample"][5] = "water"
                p_water2["sample"][7] = 2.0

                p_heavy = copy.deepcopy(p_water2)
                p_heavy["sample"][5] = "HeavyWater"
                p_heavy["sample"][7] = 2.0

                res_water2 = run_project(p_water2, self.root / f"{name}_water_rho2")
                res_heavy = run_project(p_heavy, self.root / f"{name}_heavywater")

                for r_w, r_h in zip(res_water2["efficiency"], res_heavy["efficiency"]):
                    self.assertLess(r_w["transfer_factor"], 1.0)
                    self.assertAlmostEqual(r_w["transfer_factor"], r_h["transfer_factor"], places=6)
                for s_w, s_h in zip(res_water2["summing"], res_heavy["summing"]):
                    self.assertAlmostEqual(s_w["activity_multiplier"], s_h["activity_multiplier"], places=6)

    def test_point_source_zero_density_does_not_crash_with_nan(self):
        from effsuite.model_io import read_model
        point_src = read_model("cylindrical", "standard", Path("src/effsuite/assets/engines/cylindrical/Standard/Point.txt"))
        self.assertEqual(len(point_src), 8)
        self.assertEqual(point_src[5], "vacuum")
        self.assertEqual(point_src[7], 0.0)
        p = self.example("cylinder")
        p.update(
            task="transfer",
            standard=point_src,
            calibration=[
                {"energy_keV": 100.0, "efficiency": 0.02, "u_rel_percent": 3.0},
                {"energy_keV": 1000.0, "efficiency": 0.005, "u_rel_percent": 3.0},
            ],
        )
        res = run_project(p, self.root / "point_transfer")
        for row in res["efficiency"]:
            self.assertTrue(0.0 < row["transfer_factor"] < 1.0)

    def test_backward_compatible_7_field_source_model(self):
        from effsuite.model_io import read_model, validate_model
        legacy_txt = self.root / "legacy_7line.txt"
        legacy_txt.write_text("70.0\n50.0\n1.0\n1.0\n0.0\nsoil\nplexiglass\n", encoding="utf-8")
        vals = read_model("cylindrical", "sample", legacy_txt)
        self.assertEqual(len(vals), 8)
        self.assertAlmostEqual(vals[7], 1.4, places=4)
        vals_json = validate_model("marinelli", "sample", [100.0, 80.0, 90.0, 2.0, 2.0, "HeavyWater", "plexiglass"])
        self.assertEqual(len(vals_json), 8)
        self.assertAlmostEqual(vals_json[7], 2.0, places=4)
