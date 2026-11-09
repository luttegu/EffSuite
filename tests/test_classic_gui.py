"""Real offscreen Qt forms, project reuse and background calculation lifecycle."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from effsuite.gui import MainWindow
except ImportError:MainWindow=None


@unittest.skipIf(MainWindow is None,"Install .[desktop] for GUI tests")
class ClassicGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.window=MainWindow();self.errors=[];self.window.error=lambda error:self.errors.append(str(error))
    def tearDown(self):
        if self.window.thread is not None:
            self.window.cancel_event.set();deadline=time.monotonic()+15
            while self.window.thread is not None and time.monotonic()<deadline:QTest.qWait(10);time.sleep(.002)
        self.window.dirty=False;self.window.close();self.app.processEvents();self.temporary.cleanup()
    def test_original_tab_names_and_model_field_counts(self):
        self.assertEqual([self.window.tabs.tabText(i) for i in range(self.window.tabs.count())],["Welcome","Detector","Source","Efficiency","Certificate","Library","Material"])
        from effsuite.app_cli import example_path
        for mode,count in [("cylinder",19),("marinelli",16),("well",7)]:
            self.window.apply_project(json.loads(example_path(mode).read_text()))
            self.assertEqual(len(self.window.detector_form.values()),count)
            self.assertEqual(self.window.draft()["geometry"],"cylindrical" if mode=="cylinder" else mode)
    def test_cancel_button_targets_the_current_event(self):
        import threading
        new=threading.Event();self.window.cancel_event=new;self.window.cancel_button.setEnabled(True);self.window.cancel_button.click();self.assertTrue(new.is_set())
    def test_loaded_values_round_trip_without_decimal_truncation(self):
        from effsuite.app_cli import example_path
        project=json.loads(example_path("cylinder").read_text())
        project["detector"][2]=56.12345678901234
        project["calibration"][0]["efficiency"]=.012345678901234567
        self.window.apply_project(project)
        saved=self.window.draft()
        self.assertEqual(saved["detector"],project["detector"])
        self.assertEqual(saved["calibration"],project["calibration"])
    def test_input_change_clears_previous_displayed_results(self):
        from PySide6.QtWidgets import QTableWidgetItem
        self.window.load_example()
        self.window.efficiency.setItem(0,3,QTableWidgetItem("old result"))
        self.window.library_table.setRowCount(1)
        self.window.library_table.setItem(0,2,QTableWidgetItem("old factor"))
        self.window.changed()
        self.assertIsNone(self.window.efficiency.item(0,3))
        self.assertEqual(self.window.library_table.rowCount(),0)
    def test_gui_runs_real_engine_and_uses_same_project_as_cli(self):
        self.window.load_example();self.window.workers.setValue(1);project=self.window.collect("both")
        def directory(folder=""):
            path=self.root/folder;path.mkdir(parents=True,exist_ok=True);return path
        with patch("effsuite.gui.documents",side_effect=directory),patch("effsuite.app_cli.default_output",return_value=self.root/"result"):
            self.window.calculate("both")
            deadline=time.monotonic()+45
            while self.window.thread is not None and time.monotonic()<deadline:QTest.qWait(10);time.sleep(.002)
        self.assertIsNone(self.window.thread,"GUI job timed out")
        self.assertFalse(self.errors,self.errors)
        self.assertIsNotNone(self.window.transfer_result);self.assertIsNotNone(self.window.summing_result)
        self.assertEqual(self.window.summing_result["project"]["detector"],project["detector"])
        self.assertEqual(self.window.library_table.rowCount(),len(self.window.summing_result["summing"]))
        self.assertTrue((self.root/"result/results.json").exists())
    def test_material_editor_runs_xcom_and_refreshes_model_choices(self):
        editor=self.window.material_editor
        editor.set_definition({'name':'GUI_test_water','density_g_cm3':1.,'components':[{'formula':'H2O','weight':1.}]})
        editor.library.setText(str(self.root/'data'));editor.generate()
        deadline=time.monotonic()+30
        while self.window.thread is not None and time.monotonic()<deadline:QTest.qWait(10);time.sleep(.002)
        self.assertIsNone(self.window.thread);self.assertFalse(self.errors,self.errors)
        self.assertTrue((self.root/'data/Material/GUI_test_water.txt').is_file())
        self.assertEqual(self.window.data_directory,str(self.root/'data'))
        self.assertGreaterEqual(self.window.source_form.inputs['sample',5].findText('GUI_test_water'),0)
    def test_modify_material_button_and_workflow(self):
        self.window.load_example()
        sample_combo = self.window.source_form.inputs['sample', 5]
        sample_combo.setCurrentText('water_liquid')
        self.window.source_form.modify_material('sample', 5)
        # Verify switched to Material Editor
        self.assertEqual(self.window.tabs.currentWidget(), self.window.material_editor)
        self.assertEqual(self.window.material_editor.name.text(), 'water_liquid')
        self.assertAlmostEqual(float(self.window.material_editor.density.text()), 1.0, places=3)
        self.assertEqual(self.window.material_editor.table.item(0, 0).text(), 'H2O')
        self.assertFalse(self.window.material_editor.return_button.isHidden())
        self.assertIn("Source", self.window.material_editor.return_button.text())

        # Modify name and generate new material
        self.window.material_editor.name.setText('GUI_test_water_mod')
        self.window.material_editor.density.setText('1.05')
        self.window.material_editor.library.setText(str(self.root/'data2'))
        self.window.material_editor.generate()
        deadline = time.monotonic() + 30
        while self.window.thread is not None and time.monotonic() < deadline:
            QTest.qWait(10); time.sleep(.002)
        self.assertIsNone(self.window.thread)
        self.assertFalse(self.errors, self.errors)
        # Verify returned to Source tab and sample combo has the new material selected
        self.assertEqual(self.window.tabs.currentIndex(), 2)
        self.assertEqual(sample_combo.currentText(), 'GUI_test_water_mod')

        # Test container material modification
        container_combo = self.window.source_form.inputs['sample', 6]
        container_combo.setCurrentText('polyethylene')
        self.window.source_form.modify_material('sample', 6)
        self.assertEqual(self.window.tabs.currentWidget(), self.window.material_editor)
        self.assertEqual(self.window.material_editor.name.text(), 'polyethylene')
        self.assertAlmostEqual(float(self.window.material_editor.density.text()), 0.92, places=2)
        # Test clicking return button takes back to Source tab
        self.window.material_editor.return_button.click()
        self.assertEqual(self.window.tabs.currentIndex(), 2)

    def test_guided_workflow_choice_and_summing_source(self):
        w=self.window
        # Default: complete analysis with nuclide library
        self.assertEqual(w.visible_steps(),["welcome","detector","source","efficiency","nlb"])
        self.assertFalse(w.tabs.isTabVisible(4));self.assertTrue(w.tabs.isTabVisible(5))
        # Switch to certificate
        w._source_radios["ctf"].setChecked(True)
        self.assertEqual(w.summing_source,"ctf")
        self.assertTrue(w.tabs.isTabVisible(4));self.assertFalse(w.tabs.isTabVisible(5))
        # Switch back to nuclide library
        w._source_radios["nlb"].setChecked(True)
        self.assertEqual(w.summing_source,"nlb")
        # Summing only hides the efficiency step
        w._workflow_radios["summing"].setChecked(True)
        self.assertEqual(w.visible_steps(),["welcome","detector","source","nlb"])
        self.assertFalse(w.tabs.isTabVisible(3))
        self.assertIn("Run Coincidence Summing",w._nav_next["nlb"].text())
        # Transfer only: no summing step
        w._workflow_radios["transfer"].setChecked(True)
        self.assertEqual(w.visible_steps(),["welcome","detector","source","efficiency"])
        self.assertIn("Run Efficiency Transfer",w._nav_next["efficiency"].text())
        # Next navigation skips hidden steps
        w.tabs.setCurrentIndex(2);w.go_step(1);self.assertEqual(w.tabs.currentIndex(),3)
        # Running with missing inputs points to the first incomplete step
        w.tabs.setCurrentIndex(0);w.run_workflow()
        self.assertTrue(self.errors);self.assertEqual(w.tabs.currentIndex(),1)
    def test_process_library_with_missing_decay_data_nuclides(self):
        self.window.load_example()
        self.window.workers.setValue(1)
        self.window.library_rows = [
            {"nuclide": "CO-60", "energy": 1173.2, "abundance": .99, "record": 1, "line": 1},
            {"nuclide": "CO-60", "energy": 1332.5, "abundance": .99, "record": 1, "line": 2},
            {"nuclide": "RA-223", "energy": 269.46, "abundance": .13, "record": 2, "line": 1},
            {"nuclide": "RN-219", "energy": 271.23, "abundance": .10, "record": 3, "line": 1},
        ]
        self.window.nuclides.setText("CO-60, RA-223, RN-219")
        def directory(folder=""):
            path=self.root/folder;path.mkdir(parents=True,exist_ok=True);return path
        with patch("effsuite.gui.documents",side_effect=directory),patch("effsuite.app_cli.default_output",return_value=self.root/"result_nlb"):
            self.window.calculate("summing")
            deadline = time.monotonic() + 30
            while self.window.thread is not None and time.monotonic() < deadline:
                QTest.qWait(10); time.sleep(.002)
        self.assertIsNone(self.window.thread)
        self.assertFalse(self.errors, self.errors)
        self.assertEqual(self.window.library_table.rowCount(), 4)
        # Check CO-60 has correction factor and no asterisk
        co60_factor = self.window.library_table.item(0, 2).text()
        self.assertTrue(len(co60_factor) > 0)
        self.assertEqual(self.window.library_table.item(0, 3).text(), "")
        # Check RA-223 and RN-219 have blank factor and asterisk in Not Computed
        self.assertEqual(self.window.library_table.item(2, 2).text(), "")
        self.assertEqual(self.window.library_table.item(2, 3).text(), "*")
        self.assertEqual(self.window.library_table.item(3, 2).text(), "")
        self.assertEqual(self.window.library_table.item(3, 3).text(), "*")

    def test_detector_geometry_preservation_and_conversion_between_efftran_and_mefftran(self):
        # Cylindrical (EFFTRAN) has 19 fields (including absorber diameter, thickness, and material)
        # Marinelli (MEFFTRAN) has 16 fields (no absorber)
        self.window.load_example()  # loads cylindrical example
        c_vals = self.window.detector_form.values()
        self.assertEqual(len(c_vals), 19)

        # Switch GUI mode to Marinelli beakers
        self.window.mode.setCurrentIndex(1)
        m_vals = self.window.detector_form.values()
        self.assertEqual(len(m_vals), 16)
        # The 12 physical crystal/housing dimensions match
        self.assertEqual(m_vals[:12], c_vals[:12])
        # The 4 materials (crystal, window, endcap, holder) are properly mapped
        self.assertEqual(m_vals[12:], c_vals[14:18])

        # Switch GUI mode back to Cylindrical
        self.window.mode.setCurrentIndex(0)
        c_back = self.window.detector_form.values()
        self.assertEqual(len(c_back), 19)
        self.assertEqual(c_back[:12], m_vals[:12])
        self.assertEqual(c_back[14:18], m_vals[12:])

    def test_window_title_and_icon_on_startup(self):
        # 1. Window title reflects current version
        from effsuite import __version__
        self.assertIn(f"EffSuite v{__version__}", self.window.windowTitle())

        # 2. Application icon is loaded and valid
        self.assertFalse(self.window.windowIcon().isNull())

    def test_responsive_layout_and_painted_radio_indicators_on_1080p_and_720p(self):
        from PySide6.QtWidgets import QScrollArea
        from effsuite.gui import PaintedRadio

        # 1. Verify PaintedRadio is used and draws a visible checked indicator in the left 20px
        r_both = self.window._workflow_radios["both"]
        self.assertIsInstance(r_both, PaintedRadio)
        self.assertTrue(r_both.isChecked())
        self.window.resize(1920, 1000)
        self.window.splitter.setSizes([835, 110])
        self.window.show()
        QApplication.processEvents()
        img = r_both.grab().toImage()
        has_dark_indicator = any(
            img.pixelColor(x, y).lightness() < 160
            for x in range(min(20, img.width()))
            for y in range(img.height())
        )
        self.assertTrue(has_dark_indicator, "Checked PaintedRadio must draw visible indicator pixels")

        # 2. At 1920x1000 (1080p), every visible tab fits with zero vertical scroll and pinned footer inside viewport
        for idx in (0, 1, 2, 3, 5, 6):
            self.window.tabs.setCurrentIndex(idx)
            QApplication.processEvents()
            page = self.window.tabs.widget(idx)
            sc = page.findChild(QScrollArea)
            if sc is not None:
                self.assertEqual(sc.verticalScrollBar().maximum(), 0, f"Tab {idx} should not require vertical scroll at 1080p")
            foot = page.findChild(object, "PageFooter")
            if foot is not None:
                self.assertTrue(foot.isVisible())
                self.assertLessEqual(foot.geometry().bottom(), page.height())

        # 3. At 1280x720 (1080p @ 150% DPI scaling), every step page keeps its pinned footer inside the viewport
        self.window.resize(1280, 720)
        self.window.splitter.setSizes([555, 110])
        QApplication.processEvents()
        for idx in (0, 1, 2, 3, 5):
            self.window.tabs.setCurrentIndex(idx)
            QApplication.processEvents()
            page = self.window.tabs.widget(idx)
            foot = page.findChild(object, "PageFooter")
            self.assertIsNotNone(foot)
            self.assertTrue(foot.isVisible())
            self.assertLessEqual(foot.geometry().bottom(), page.height())
