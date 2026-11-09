"""CAM adapter contracts with a synthetic transport; real CAM needs Windows."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from effsuite.genie import export_copy,match_factor
from effsuite.parallel_coincidence import CoincidenceError


class GenieTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.source=self.root/"original.NLB";self.source.write_bytes(b"original")
        self.result={"summing":[{"nuclide":"CO-60","energy_keV":1173,"activity_multiplier":1.25,"status":"candidate"}],"efficiency":[]}
    def tearDown(self):self.temporary.cleanup()
    def test_missing_factor_never_becomes_one(self):
        with self.assertRaises(CoincidenceError):match_factor(self.result,"CS-137",661.66)
    def test_invalid_nearest_factor_is_not_replaced_with_a_valid_neighbor(self):
        self.result["summing"] += [{"nuclide":"CO-60","energy_keV":1174,"activity_multiplier":None,"status":"invalid"}]
        with self.assertRaises(CoincidenceError):match_factor(self.result,"CO-60",1173.9)
    def test_roundtrip_source_preservation_and_abundance_division(self):
        original=[{"nuclide":"CO-60","energy":1173.2,"abundance":.99,"record":1,"line":1}]
        state={"written":False}
        def cam(action,path,updates=None):
            if action=="write_nlb":
                self.assertNotEqual(Path(path),self.source)
                self.assertAlmostEqual(updates[0]["value"],.99/1.25)
                Path(path).write_bytes(b"corrected");state["written"]=True;return {"ok":True}
            rows=copy.deepcopy(original)
            if state["written"] and Path(path)!=self.source:rows[0]["abundance"]=.99/1.25
            return {"ok":True,"rows":rows}
        with patch("effsuite.genie._call",side_effect=cam):
            report=export_copy(self.source,self.root/"corrected.NLB",self.result,"nlb")
        self.assertTrue(report["roundtrip_verified"]);self.assertEqual(self.source.read_bytes(),b"original")
    def test_failed_roundtrip_does_not_publish_output(self):
        rows=[{"nuclide":"CO-60","energy":1173.2,"abundance":.99,"record":1,"line":1}]
        with patch("effsuite.genie._call",return_value={"ok":True,"rows":rows}):
            with self.assertRaises(CoincidenceError):export_copy(self.source,self.root/"bad.NLB",self.result,"nlb")
        self.assertFalse((self.root/"bad.NLB").exists());self.assertEqual(self.source.read_bytes(),b"original")
    def test_tiny_coefficient_underflow_is_rejected(self):
        self.result["summing"][0]["activity_multiplier"]=2.
        rows=[{"nuclide":"CO-60","energy":1173.2,"abundance":1e-30,"record":1,"line":1}]
        calls=[0]
        def cam(action,path,updates=None):
            if action.startswith("write"):return {"ok":True}
            r=copy.deepcopy(rows)
            if Path(path)!=self.source:r[0]["abundance"]=0.
            return {"ok":True,"rows":r}
        with patch("effsuite.genie._call",side_effect=cam):
            with self.assertRaises(CoincidenceError):export_copy(self.source,self.root/"underflow.NLB",self.result,"nlb")
        self.assertFalse((self.root/"underflow.NLB").exists())
    def test_uncomputed_line_abundance_remains_unchanged_in_export(self):
        original=[{"nuclide":"CO-60","energy":1173.2,"abundance":.99,"record":1,"line":1},
                  {"nuclide":"CS-137","energy":661.66,"abundance":.85,"record":2,"line":1}]
        state={"written":False}
        def cam(action,path,updates=None):
            if action=="write_nlb":
                self.assertAlmostEqual(updates[0]["value"],.99/1.25)
                self.assertAlmostEqual(updates[1]["value"],.85)  # unchanged
                Path(path).write_bytes(b"corrected");state["written"]=True;return {"ok":True}
            rows=copy.deepcopy(original)
            if state["written"] and Path(path)!=self.source:
                rows[0]["abundance"]=.99/1.25;rows[1]["abundance"]=.85
            return {"ok":True,"rows":rows}
        with patch("effsuite.genie._call",side_effect=cam):
            report=export_copy(self.source,self.root/"mixed.NLB",self.result,"nlb")
        self.assertTrue(report["roundtrip_verified"])
