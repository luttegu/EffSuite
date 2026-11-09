"""Material workbook contract, actual XCOM and downstream native use."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from effsuite.materials import (TEMPLATE,validate_composition,load_composition,composition_bytes,
 generate_attenuation,attenuation_rows,create_material,save_definition)
from effsuite.parallel_coincidence import CoincidenceError,CalculationCancelled
from effsuite.model_io import ASSETS, COMMON_DATA
from effsuite.app_cli import example_path
from effsuite.suite import run_project


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.water={'name':'Test_water','density_g_cm3':1.,'components':[{'formula':'H2O','weight':1.}]}
    def tearDown(self):self.temp.cleanup()
    def test_invalid_compositions_fail_before_xcom(self):
        cases=[[],dict(self.water,components=[None]),dict(self.water,density_g_cm3=0),dict(self.water,name='../bad'),dict(self.water,name='CON'),dict(self.water,components=[{'formula':'Ca(OH)2','weight':1}]),dict(self.water,components=[{'formula':'Xx2','weight':1}]),dict(self.water,components=[{'formula':'H0','weight':1}]),dict(self.water,components=[{'formula':'H2O','weight':0}]),dict(self.water,components=[{'formula':'H2O','weight':-1}])]
        for d in cases:
            with self.subTest(d=d),self.assertRaises(CoincidenceError):validate_composition(d)
    def test_original_text_and_json_round_trip(self):
        path=self.root/'Test_water.txt';path.write_bytes(composition_bytes(self.water))
        self.assertEqual(load_composition(path),validate_composition(self.water))
        path=self.root/'composition.json';save_definition(path,self.water)
        self.assertEqual(load_composition(path),validate_composition(self.water))
    def test_excel_template_inputs_are_read_without_cached_formula_dependence(self):
        d=load_composition(TEMPLATE)
        self.assertEqual(d['name'],'New_water');self.assertEqual(d['density_g_cm3'],1.)
        self.assertEqual(d['components'],[{'formula':'H2O','weight':1.}])
    def test_native_xcom_water_matches_supplied_attenuation_table(self):
        raw,_=generate_attenuation(self.water)
        actual=attenuation_rows(raw);reference=attenuation_rows((COMMON_DATA/'Material/water.txt').read_bytes())
        self.assertEqual(len(actual),len(reference))
        for a,b in zip(actual,reference):
            self.assertEqual(a[0],b[0])
            for x,y in zip(a[1:],b[1:]):self.assertAlmostEqual(x,y,delta=max(1e-12,abs(y)*.002))
    def test_relative_weight_scale_does_not_change_table(self):
        d=dict(self.water,components=[{'formula':'H2O','weight':90},{'formula':'NaCl','weight':10}]);e=copy.deepcopy(d)
        for row in e['components']:row['weight']/=100
        self.assertEqual(generate_attenuation(d)[0],generate_attenuation(e)[0])
    def test_bulk_density_does_not_change_mass_attenuation_coefficients(self):
        self.assertEqual(generate_attenuation(self.water)[0],generate_attenuation(dict(self.water,density_g_cm3=2.))[0])
    def test_cancellation_publishes_nothing(self):
        stop=threading.Event();stop.set();library=self.root/'library'
        with self.assertRaises(CalculationCancelled):create_material(self.water,library,cancel=stop)
        self.assertFalse(library.exists())
    def test_existing_material_is_preserved(self):
        library=self.root/'library';result=create_material(self.water,library)
        before=Path(result['attenuation_file']).read_bytes()
        with self.assertRaises(CoincidenceError):create_material(dict(self.water,density_g_cm3=2.),library)
        self.assertEqual(Path(result['attenuation_file']).read_bytes(),before)
    def test_generated_material_is_used_in_all_three_transfer_and_summing_modes(self):
        for mode in ['cylinder','marinelli','well']:
            with self.subTest(mode=mode):
                library=self.root/(mode+'_data');create_material(dict(self.water,density_g_cm3=2.),library,geometry=mode)
                p=json.loads(example_path(mode).read_text());p.update(task='both',nuclides=['CO-60'],workers=1,data_directory=str(library),standard=list(p['sample']),calibration=[{'energy_keV':100.,'efficiency':.01,'u_rel_percent':3.},{'energy_keV':1000.,'efficiency':.005,'u_rel_percent':3.}])
                p['standard'][5]='water';p['sample'][5]='Test_water'
                result=run_project(p,self.root/(mode+'_result'))
                self.assertLess(result['efficiency'][0]['transfer_factor'],1.)
                co=next(row for row in result['summing'] if row['nuclide']=='CO-60' and row['energy_keV']==1173)
                self.assertGreater(co['activity_multiplier'],1.)
                self.assertTrue(result['all_reported_factors_valid'])
    def test_cli_excel_and_direct_inputs_generate_identical_files(self):
        for label,args in [('excel',['--input',str(TEMPLATE),'--name','Test_water']),('direct',['--name','Test_water','--density','1','--compound','H2O=1'])]:
            done=subprocess.run([sys.executable,'-m','effsuite.app_cli','material',*args,'--library',str(self.root/label)],capture_output=True,text=True,timeout=30)
            self.assertEqual(done.returncode,0,done.stderr)
        self.assertEqual((self.root/'excel/Material/Test_water.txt').read_bytes(),(self.root/'direct/Material/Test_water.txt').read_bytes())
    def test_common_directory_shared_across_all_geometries(self):
        self.assertTrue((COMMON_DATA/'Composition').is_dir())
        self.assertTrue((COMMON_DATA/'Material').is_dir())
        self.assertTrue((COMMON_DATA/'Composition/water.txt').is_file())
        self.assertTrue((COMMON_DATA/'Material/water.txt').is_file())
        for mode in ['cylinder','marinelli','well']:
            with self.subTest(mode=mode):
                p=json.loads(example_path(mode).read_text())
                p.update(task='transfer',workers=1,standard=list(p['sample']),calibration=[{'energy_keV':100.,'efficiency':.01,'u_rel_percent':3.},{'energy_keV':1000.,'efficiency':.005,'u_rel_percent':3.}])
                result=run_project(p,self.root/(mode+'_common_test'))
                self.assertEqual(result['efficiency'][0]['transfer_factor'],1.)
