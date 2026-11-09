"""Evidence pairing and criterion checks for laboratory comparison exports."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from effsuite.lab_comparison import FIELDS,compare_files


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        evidence=self.root/"evidence.txt";evidence.write_text("synthetic test evidence\n")
        self.row=dict(zip(FIELDS,["case1","well","detector1","sample1","inputs1","CO-60","1173","1173","summing_activity_multiplier","1","multiply_activity","1.1","0.01",evidence.name,hashlib.sha256(evidence.read_bytes()).hexdigest()]))
        self.plan={"schema_version":1,"plan_id":"TEST-ONLY","reference_kind":"demonstration","criteria_approved":False,"programs":{role:{"name":role,"version":"test","build_id":"synthetic"} for role in ["reference","candidate"]},"criteria":[{"geometry":"well","quantity":"summing_activity_multiplier","atol":0.,"rtol":.01,"energy_tolerance_keV":.01}]}
        self.write_plan();self.write_rows("reference.csv",[self.row]);self.write_rows("candidate.csv",[self.row])
    def tearDown(self):self.temporary.cleanup()
    def write_plan(self):(self.root/"plan.json").write_text(json.dumps(self.plan))
    def write_rows(self,name,rows):
        with (self.root/name).open("w",newline="") as file:
            writer=csv.DictWriter(file,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    def compare(self,**kwargs):return compare_files(self.root/"reference.csv",self.root/"candidate.csv",self.root/"plan.json",**kwargs)
    def test_synthetic_match_never_authorizes_routine_use(self):
        result=self.compare();self.assertTrue(result["numerical_comparison_passed"]);self.assertFalse(result["controlled_comparison_passed"]);self.assertFalse(result["routine_use_authorized"])
    def test_empty_comparison_cannot_pass(self):
        self.write_rows("candidate.csv",[])
        with self.assertRaisesRegex(ValueError,"empty comparison"):self.compare()
    def test_changed_source_evidence_is_rejected(self):
        (self.root/"evidence.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError,"has changed"):self.compare()
    def test_different_input_set_is_rejected(self):
        self.write_rows("candidate.csv",[dict(self.row,input_set_id="different")])
        with self.assertRaisesRegex(ValueError,"input_set_id"):self.compare()
    def test_predeclared_tolerance_failure_is_reported(self):
        self.write_rows("candidate.csv",[dict(self.row,value="1.2")])
        self.assertFalse(self.compare()["numerical_comparison_passed"])
    def test_uncertainty_check_needs_explicit_cross_covariance(self):
        self.plan["criteria"][0]["maximum_standardized_difference"]=2.;self.write_plan()
        with self.assertRaisesRegex(ValueError,"cross-covariance"):self.compare()
        covariance=self.root/"covariance.json";covariance.write_text(json.dumps([{"case_id":"case1","quantity":"summing_activity_multiplier","nuclide":"CO-60","line_id":"1173","covariance":0.,"basis":"independent synthetic observations"}]))
        self.assertEqual(self.compare(covariance_file=covariance)["metrics"][0]["standardized_difference"],0.)
    def test_impossible_covariance_is_rejected(self):
        self.plan["criteria"][0]["maximum_standardized_difference"]=2.;self.write_plan()
        covariance=self.root/"covariance.json";covariance.write_text(json.dumps([{"case_id":"case1","quantity":"summing_activity_multiplier","nuclide":"CO-60","line_id":"1173","covariance":.1,"basis":"invalid synthetic input"}]))
        with self.assertRaisesRegex(ValueError,"positive-semidefinite"):self.compare(covariance_file=covariance)
