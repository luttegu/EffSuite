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
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtTest import QTest
    from effsuite.gui import MainWindow
except ImportError:MainWindow=None


@unittest.skipIf(MainWindow is None,"Install .[desktop] for GUI tests")
class ClassicGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.disclaimer_patch=patch.object(MainWindow,"check_first_run_disclaimer",lambda window:None);self.disclaimer_patch.start()
        self.window=MainWindow();self.errors=[];self.window.error=lambda error:self.errors.append(str(error));self.window.material_editor.error=self.window.error
    def tearDown(self):
        self.addCleanup(self.disclaimer_patch.stop)
        if self.window.thread is not None:
            self.window.cancel_event.set();deadline=time.monotonic()+15
            while self.window.thread is not None and time.monotonic()<deadline:QTest.qWait(10);time.sleep(.002)
        self.window.dirty=False;self.window.close();self.app.processEvents();self.temporary.cleanup()
    def test_original_tab_names_and_model_field_counts(self):
        self.assertEqual([self.window.tabs.tabText(i) for i in range(self.window.tabs.count())],["Welcome","Detector","Standard && Sample","Efficiency","Certificate","Library"])
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
    def wait_task(self, seconds=30):
        deadline = time.monotonic() + seconds
        while self.window.thread is not None and time.monotonic() < deadline:
            QTest.qWait(10); time.sleep(.002)
        self.assertIsNone(self.window.thread)
    def test_material_editor_is_a_separate_non_modal_window(self):
        from PySide6.QtCore import Qt
        editor = self.window.material_editor
        self.assertTrue(editor.isWindow())
        self.assertEqual(editor.windowModality(), Qt.WindowModality.NonModal)
        self.assertEqual(self.window.tabs.indexOf(editor), -1)
        self.window.tabs.setCurrentIndex(1)
        self.window.open_material_editor_for_input(None)
        self.assertTrue(editor.isVisible())
        # The main window stays where it was and usable.
        self.assertEqual(self.window.tabs.currentIndex(), 1)
        self.assertTrue(self.window.tabs.isEnabled())
        self.assertIn("every material list", editor.target_label.text())
        # A geometry change keeps the window and what was typed in it.
        editor.name.setText("half_typed")
        self.window.mode.setCurrentIndex(self.window.mode.findData("marinelli"))
        self.assertIs(self.window.material_editor, editor)
        self.assertEqual(editor.name.text(), "half_typed")
        # Closing the main window also closes the editor.
        self.window.dirty = False
        self.window.close()
        self.assertFalse(editor.isVisible())
    def test_modify_material_button_and_workflow(self):
        self.window.load_example()
        self.window.tabs.setCurrentIndex(2)
        editor = self.window.material_editor
        sample_combo = self.window.source_form.inputs['sample', 5]
        sample_combo.setCurrentText('water')
        self.window.source_form.modify_material('sample', 5)
        # The editor window opens with the material; the Source page stays shown.
        self.assertTrue(editor.isVisible())
        self.assertEqual(self.window.tabs.currentIndex(), 2)
        self.assertEqual(editor.name.text(), 'water')
        self.assertAlmostEqual(float(editor.density.text()), 1.0, places=3)
        self.assertEqual(editor.table.item(0, 0).text(), 'H2O')
        self.assertIn("Sample", editor.target_label.text())

        # Modify name and apply: the new material is selected in the sample field.
        editor.name.setText('GUI_test_water_mod')
        editor.density.setText('1.05')
        editor.library.setText(str(self.root/'data2'))
        editor.apply_button.click()
        self.wait_task()
        self.assertFalse(self.errors, self.errors)
        self.assertTrue(editor.isVisible())
        self.assertEqual(self.window.tabs.currentIndex(), 2)
        self.assertEqual(sample_combo.currentText(), 'GUI_test_water_mod')
        self.assertAlmostEqual(self.window.source_form.values('sample')[7], 1.05, places=6)
        detector_combos = [e for e in self.window.detector_form.inputs.values() if hasattr(e, 'findText')]
        self.assertTrue(all(c.findText('GUI_test_water_mod') >= 0 for c in detector_combos))

        # Overwriting the same material with a new density updates the density field.
        with patch("effsuite.material_gui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            editor.density.setText('1.10')
            editor.apply_button.click()
            self.wait_task()
        self.assertFalse(self.errors, self.errors)
        self.assertEqual(sample_combo.currentText(), 'GUI_test_water_mod')
        self.assertAlmostEqual(self.window.source_form.values('sample')[7], 1.10, places=6)

        # Container material: loaded into the editor, target changes.
        container_combo = self.window.source_form.inputs['sample', 6]
        container_combo.setCurrentText('polystyrene')
        self.window.source_form.modify_material('sample', 6)
        self.assertEqual(editor.name.text(), 'polystyrene')
        self.assertAlmostEqual(float(editor.density.text()), 1.0, places=2)
        self.assertIn("container", editor.target_label.text().lower())

    def test_standard_column_hidden_for_summing_only(self):
        w = self.window
        w.load_example()
        w.tabs.setCurrentIndex(2)
        form, preview = w.source_form, w.source_diagram.live_widget
        standard = form.inputs['standard', 0]
        # Sample column first, standard second.
        self.assertLess(form._grid.indexOf(standard), form._grid.indexOf(form.inputs['sample', 0]))
        self.assertFalse(standard.isHidden())
        preview.set_kind('Standard')
        self.assertEqual(preview.source.currentText(), 'Standard')
        w._workflow_radios["summing"].setChecked(True)
        self.assertTrue(standard.isHidden())
        self.assertTrue(form.load_buttons['standard'].isHidden())
        self.assertTrue(form._col_headers['standard'].isHidden())
        self.assertFalse(form.inputs['sample', 0].isHidden())
        self.assertFalse(w.source_hint.isHidden())
        self.assertEqual(preview.source.currentText(), 'Sample')
        for live in (preview, w.diagram.live_widget):
            self.assertFalse(live.source.model().item(live.source.findText('Standard')).isEnabled())
        self.assertIn("Standard not needed", w._banners["source"][0].text())
        self.assertEqual(w._nav_next["detector"].text(), "Next: Sample ▶")
        self.assertFalse([m for m in w.missing_items() if "Standard" in m[1]])
        # Back to complete analysis: the standard (with its values) returns.
        w._workflow_radios["both"].setChecked(True)
        self.assertFalse(standard.isHidden())
        self.assertTrue(standard.text())
        self.assertEqual(w._nav_next["detector"].text(), "Next: Standard && Sample ▶")
        self.assertTrue(w._nav_next["detector"].shortcut().isEmpty())
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
        self.assertEqual(self.window.library_table.item(0, 4).text(), "")
        # CO-60 also has a TCS uncertainty u(C) in percent
        self.assertGreater(float(self.window.library_table.item(0, 3).text()), 0)
        # Check RA-223 and RN-219 have blank factor, blank u(C) and asterisk in Not Computed
        self.assertEqual(self.window.library_table.item(2, 2).text(), "")
        self.assertEqual(self.window.library_table.item(2, 3).text(), "")
        self.assertEqual(self.window.library_table.item(2, 4).text(), "*")
        self.assertEqual(self.window.library_table.item(3, 2).text(), "")
        self.assertEqual(self.window.library_table.item(3, 3).text(), "")
        self.assertEqual(self.window.library_table.item(3, 4).text(), "*")
        # The u(C) inputs change only u(C): the factors stay on screen.
        factor_before = self.window.library_table.item(0, 2).text()
        u_before = float(self.window.library_table.item(0, 3).text())
        enabled = self.window.tcs_inputs["nlb"]["enabled"]
        enabled.setChecked(False)
        self.assertIsNotNone(self.window.summing_result)
        self.assertEqual(self.window.library_table.item(0, 2).text(), factor_before)
        self.assertEqual(self.window.library_table.item(0, 3).text(), "")
        enabled.setChecked(True)
        self.assertEqual(float(self.window.library_table.item(0, 3).text()), u_before)
        self.window.tcs_inputs["ctf"]["total_efficiency_percent"].setValue(20.)   # the other page's box
        self.assertEqual(self.window.library_table.item(0, 2).text(), factor_before)
        self.assertGreater(float(self.window.library_table.item(0, 3).text()), u_before)

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
        for idx in (0, 1, 2, 3, 5):
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

    def test_source_density_gui_autofill_on_material_change_and_custom_preservation(self):
        from effsuite.app_cli import example_path
        # Verify 8 fields in SourceForm across all three geometries
        for mode_name in ("cylinder", "marinelli", "well"):
            self.window.apply_project(json.loads(example_path(mode_name).read_text()))
            QApplication.processEvents()
            vals = self.window.source_form.values("sample")
            self.assertEqual(len(vals), 8)
            # Selecting 'soil' in Source material auto-fills nominal density 1.4 g/cm³
            mat_combo = self.window.source_form.inputs["sample", 5]
            mat_combo.setCurrentText("soil")
            QApplication.processEvents()
            self.assertAlmostEqual(self.window.source_form.values("sample")[7], 1.4, places=4)
            # Selecting 'heavy' (H2O at 2 g/cm³) auto-fills nominal density 2.0 g/cm³
            mat_combo.setCurrentText("heavy")
            QApplication.processEvents()
            self.assertAlmostEqual(self.window.source_form.values("sample")[7], 2.0, places=4)
            # Loading a source model with a custom density (e.g., water at 1.35 g/cm³) preserves 1.35
            custom = list(self.window.source_form.values("sample"))
            custom[5] = "water"
            custom[7] = 1.35
            self.window.source_form.set_values("sample", custom)
            self.assertEqual(self.window.source_form.values("sample")[5], "water")
            self.assertAlmostEqual(self.window.source_form.values("sample")[7], 1.35, places=4)
    def test_default_data_folder_menu_saves_setting_and_updates_lists(self):
        from effsuite import paths
        chosen=self.root/"Lab data"
        (chosen/"Composition").mkdir(parents=True)
        (chosen/"Composition"/"gui_lab_resin.txt").write_text(" 1.18\nC5H8O2\n 1\n")
        env={k:v for k,v in os.environ.items() if k!="EFFSUITE_DATA"}
        env["APPDATA"]=str(self.root/"appdata");env["XDG_CONFIG_HOME"]=str(self.root/"config")
        with patch.dict(os.environ,env,clear=True), \
             patch("effsuite.gui.QFileDialog.getExistingDirectory",return_value=str(chosen)), \
             patch("effsuite.gui.QMessageBox.question",return_value=QMessageBox.StandardButton.Yes):
            self.window.choose_default_data()
            self.assertFalse(self.errors,self.errors)
            self.assertEqual(paths.get_data_dir(),chosen.resolve())
            self.assertEqual(paths.data_dir_source(),"settings")
            self.assertTrue((chosen/"Material").is_dir())          # created on request
            self.assertEqual(self.window.data_directory,str(chosen.resolve()))
            self.assertIn(str(chosen.resolve()),self.window.data_label.text())
            combo=self.window.source_form.inputs['sample',5]
            items=[combo.itemText(i) for i in range(combo.count())]
            self.assertIn("gui_lab_resin",items);self.assertIn("water",items)
            self.assertEqual(self.window.data_folder("Detector"),chosen.resolve()/"Detector")
            self.window.reset_default_data()
            self.assertEqual(paths.data_dir_source(),"built-in")
            self.assertEqual(self.window.data_directory,str(paths.builtin_data_dir()))
