"""The material editor window: the original Material workbook as a form.

The user enters a name, a density and up to 10 compounds with relative
weights. "Apply" runs XCOM (see materials.py), saves the composition and
attenuation files in the chosen data folder and selects the material in
the field the window was opened from (Detector or Standard & Sample page).

The window is separate and non-modal: the user can keep editing the
detector, sample and standard forms while it is open.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from .materials import TEMPLATE, create_material, default_library, load_composition, save_definition, validate_composition
from .model_io import COMMON_DATA
from .qt_icons import with_icon, APPLY, CLEAR, OPEN, SAVE

MAX_COMPOUNDS = 10
RIGHT_ALIGNED = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
SUMMARY_NEUTRAL = "background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;padding:4px 8px;color:#334155;font-weight:500;"
SUMMARY_OK = "background:#f0fdf4;border:1px solid #bbf7d0;border-radius:4px;padding:4px 8px;color:#166534;font-weight:600;"
SUMMARY_ERROR = "background:#fef2f2;border:1px solid #fecaca;border-radius:4px;padding:4px 8px;color:#991b1b;font-weight:500;"


class MaterialEditor(QWidget):
    """Material window. ``owner`` is the main window (for tasks, data folder and the forms to update).

    It is a top-level window without parent, so it does not stay in front of
    the (almost full-screen) main window. Closing it only hides it, so a
    half-typed material is kept until the next opening.
    """

    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.Window)
        self.owner = owner
        self.loading = False   # True while we fill the form ourselves (no recalculation)
        self.setWindowTitle("EffSuite Material Editor")
        self.resize(900, 640)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addLayout(self._title_bar())
        layout.addWidget(self._name_and_density_box())
        layout.addWidget(self._composition_box(), 1)
        layout.addWidget(self._output_box())
        layout.addLayout(self._apply_bar())
        self.name.textChanged.connect(self.update_fractions)
        self.density.textChanged.connect(self.update_fractions)

    # --- building the form -------------------------------------------------
    def _title_bar(self):
        bar = QHBoxLayout()
        title = QLabel("Material composition and XCOM attenuation")
        title.setStyleSheet("font-size:13.5pt;font-weight:600;color:#0f172a;")
        bar.addWidget(title)
        bar.addStretch()
        # Which form field "Apply" selects the material in (set by set_target).
        self.target_label = QLabel()
        self.target_label.setTextFormat(Qt.TextFormat.RichText)
        self.target_label.setStyleSheet("color:#1e40af;background:#eff6ff;border:1px solid #bfdbfe;"
                                        "border-radius:4px;padding:4px 10px;")
        bar.addWidget(self.target_label)
        self.set_target(None)
        return bar

    def _name_and_density_box(self):
        box = QGroupBox("1. Material name and bulk density")   # "&&" shows a single "&"
        row = QHBoxLayout(box)
        row.setSpacing(16)
        row.setContentsMargins(10, 12, 10, 8)

        name_form = QFormLayout()
        name_form.setSpacing(8)
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Salt_water, Glucose")
        name_label = QLabel("Material name")
        name_label.setStyleSheet("font-weight:600;color:#1e293b;")
        name_form.addRow(name_label, self.name)
        row.addLayout(name_form, 2)

        density_form = QFormLayout()
        density_form.setSpacing(8)
        self.density = QLineEdit()
        self.density.setPlaceholderText("e.g. 1.346")
        self.density.setAlignment(RIGHT_ALIGNED)
        density_label = QLabel('Density <span style="color:#64748b;font-weight:normal;">[g/cm³]</span>')
        density_label.setTextFormat(Qt.TextFormat.RichText)
        density_label.setStyleSheet("font-weight:600;color:#1e293b;")
        density_form.addRow(density_label, self.density)
        row.addLayout(density_form, 1)
        return box

    def _composition_box(self):
        box = QGroupBox(f"2. Chemical composition (up to {MAX_COMPOUNDS} compounds)")
        column = QVBoxLayout(box)
        column.setSpacing(6)
        column.setContentsMargins(10, 12, 10, 8)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._task_buttons = []   # buttons that start a background task (see set_busy)
        for text, action, pixmap in [("Load composition / Excel…", self.load, OPEN), ("Store JSON…", self.save, SAVE),
                                     ("Copy Excel template…", self.copy_template, None), ("Clear", self.clear, CLEAR)]:
            button = QPushButton(text)
            if pixmap is not None:
                with_icon(button, pixmap)
            button.clicked.connect(action)
            buttons.addWidget(button)
            if action == self.load:
                self._task_buttons.append(button)
        buttons.addStretch()
        column.addLayout(buttons)

        # Columns: formula, relative weight, normalized fraction (calculated, read-only).
        self.table = QTableWidget(MAX_COMPOUNDS, 3)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(25)
        self.table.setHorizontalHeaderLabels(["Chemical formula (e.g. H2O, NaCl, C6H12O6)", "Relative weight by mass",
                                              "Normalized mass fraction [%]"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.update_fractions)
        column.addWidget(self.table, 1)

        self.summary = QLabel("Enter chemical formulas and relative weights")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(SUMMARY_NEUTRAL)
        column.addWidget(self.summary)
        return box

    def _output_box(self):
        box = QGroupBox("3. Output data folder")
        row = QHBoxLayout(box)
        row.setSpacing(10)
        row.setContentsMargins(10, 12, 10, 8)
        label = QLabel("Data folder:")
        label.setStyleSheet("font-weight:600;color:#334155;")
        row.addWidget(label)
        # Start in the data folder the main window uses, so the new material is
        # saved where the calculations look for it.
        self.library = QLineEdit(str(getattr(self.owner, "data_directory", None) or default_library()))
        row.addWidget(self.library, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse)
        row.addWidget(browse)
        return box

    def _apply_bar(self):
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#334155;font-weight:500;")
        bar.addWidget(self.status, 1)
        self.apply_button = with_icon(QPushButton("Apply: create material and XCOM table"), APPLY)
        self.apply_button.setToolTip("Save the composition, generate the XCOM attenuation table and update the "
                                     "material lists of the Detector and Standard & Sample pages")
        self.apply_button.setStyleSheet("font-weight:600;font-size:10pt;background:#16a34a;color:#ffffff;"
                                        "border:1px solid #15803d;padding:7px 18px;border-radius:5px;")
        self.apply_button.clicked.connect(self.generate)
        bar.addWidget(self.apply_button)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        bar.addWidget(close)
        return bar

    # --- window state ------------------------------------------------------
    def set_target(self, description: str | None):
        """Show which form field "Apply" will select the material in (None: no field)."""
        if description:
            self.target_label.setText(f"Apply selects the material in: <b>{description}</b>")
        else:
            self.target_label.setText("Apply adds the material to every material list")

    def set_busy(self, busy: bool):
        """Disable the buttons that start a background task while another one runs."""
        self.apply_button.setEnabled(not busy)
        for button in self._task_buttons:
            button.setEnabled(not busy)
        text = self.status.text()
        if busy and not text.startswith("Creating"):
            self.status.setText("A calculation is running. Apply is available when it has finished.")
        elif not busy and text.startswith(("A calculation is running", "Creating")):
            self.status.setText("")   # finished without success message (failed or cancelled)

    def error(self, message):
        """Show an error in front of this window (not behind it, in the main window)."""
        QMessageBox.warning(self, "EffSuite — Material Editor", str(message))

    def clear(self):
        self.loading = True
        self.name.clear()
        self.density.clear()
        self.table.clearContents()
        self.loading = False
        self.update_fractions()

    def _cell_text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def collect(self) -> dict:
        """The checked material definition from the form ("0,5" is read as 0.5)."""
        components = []
        for row in range(MAX_COMPOUNDS):
            formula, weight = self._cell_text(row, 0), self._cell_text(row, 1)
            if formula or weight:
                components.append({"formula": formula, "weight": weight.replace(",", ".")})
        return validate_composition({"name": self.name.text(), "density_g_cm3": self.density.text().replace(",", "."),
                                     "components": components})

    def set_definition(self, definition: dict):
        """Fill the form with a material definition."""
        self.loading = True
        self.name.setText(definition["name"])
        self.density.setText(str(definition["density_g_cm3"]))
        self.table.clearContents()
        for row, component in enumerate(definition["components"]):
            weight = QTableWidgetItem(str(component["weight"]))
            weight.setTextAlignment(RIGHT_ALIGNED)
            self.table.setItem(row, 0, QTableWidgetItem(component["formula"]))
            self.table.setItem(row, 1, weight)
        self.loading = False
        self.update_fractions()

    def update_fractions(self, *unused):
        """Recalculate the normalized fractions and the summary line after each edit."""
        if self.loading:
            return
        self.loading = True
        try:
            for row in range(MAX_COMPOUNDS):
                weight = self.table.item(row, 1)
                if weight:
                    weight.setTextAlignment(RIGHT_ALIGNED)
            definition = self.collect()
            total = sum(component["weight"] for component in definition["components"])
            index = 0   # position in definition["components"] (empty rows are skipped)
            for row in range(MAX_COMPOUNDS):
                if self._cell_text(row, 0):
                    fraction = QTableWidgetItem(format(100 * definition["components"][index]["weight"] / total, ".9g"))
                    fraction.setTextAlignment(RIGHT_ALIGNED)
                    fraction.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)   # read-only
                    fraction.setBackground(QColor("#f0f9ff"))
                    fraction.setForeground(QColor("#0f172a"))
                    self.table.setItem(row, 2, fraction)
                    index += 1
                else:
                    self.table.takeItem(row, 2)
            self.summary.setText(f'{len(definition["components"])} compound(s), density = {definition["density_g_cm3"]:g} g/cm³, '
                                 f"total weight = {total:g} (normalized to 100%)")
            self.summary.setStyleSheet(SUMMARY_OK)
        except Exception as exc:   # incomplete or invalid input: show why
            for row in range(MAX_COMPOUNDS):
                self.table.takeItem(row, 2)
            self.summary.setText(str(exc))
            self.summary.setStyleSheet(SUMMARY_ERROR)
        finally:
            self.loading = False

    # --- buttons -----------------------------------------------------------
    def _start_folder(self, subfolder: str | None = None) -> Path:
        """Folder in which file dialogs open: the data folder (or its subfolder)."""
        text = self.library.text().strip()
        folder = Path(text) if text else default_library()
        if subfolder and (folder / subfolder).is_dir():
            return folder / subfolder
        return folder

    def load(self, *unused):
        filename, _ = QFileDialog.getOpenFileName(self, "Load material composition", str(self._start_folder("Composition")),
                                                  "Material definition (*.txt *.json *.xlsx *.xlsm *.xls);;All files (*)")
        if filename:
            self.owner.start_task(lambda log: load_composition(filename), self.set_definition)

    def save(self, *unused):
        try:
            definition = self.collect()
        except Exception as exc:
            self.error(exc)
            return
        folder = self._start_folder("Composition")
        folder.mkdir(parents=True, exist_ok=True)
        filename, _ = QFileDialog.getSaveFileName(self, "Store composition definition",
                                                  str(folder / (definition["name"] + ".material.json")), "Material JSON (*.json)")
        if filename:
            try:
                save_definition(filename, definition)
                self.status.setText("Saved " + filename)
            except Exception as exc:
                self.error(exc)

    def copy_template(self, *unused):
        folder = self._start_folder()
        folder.mkdir(parents=True, exist_ok=True)
        filename, _ = QFileDialog.getSaveFileName(self, "Copy editable Excel template", str(folder / "Material_Composition.xlsx"),
                                                  "Excel workbook (*.xlsx)")
        if filename:
            # This is only a blank template and the save dialog has already asked
            # "Replace?", so an existing file may be replaced here.
            try:
                Path(filename).write_bytes(TEMPLATE.read_bytes())
                QDesktopServices.openUrl(QUrl.fromLocalFile(filename))
            except OSError as exc:
                self.error(f"Could not copy the template to {filename}: {exc}")

    def browse(self, *unused):
        folder = QFileDialog.getExistingDirectory(self, "Output data folder", self.library.text())
        if folder:
            self.library.setText(folder)

    def _material_exists(self, name: str, library: Path) -> bool:
        """True when creating ``name`` would replace (or shadow) an existing material:
        one in the output folder or a bundled original material."""
        def has(folder: Path) -> bool:
            return any((folder / sub / (name + ".txt")).exists() for sub in ("Composition", "Material"))
        return has(library) or has(COMMON_DATA)

    def generate(self, *unused):
        """Run XCOM and save the material (asks before replacing an existing one)."""
        if self.owner.thread is not None:
            self.error("A calculation is still running. Apply the material when it has finished.")
            return
        try:
            definition = self.collect()
        except Exception as exc:
            self.error(exc)
            return
        if not self.library.text().strip():
            self.error("Choose an output data folder")
            return
        library = Path(self.library.text().strip())
        mode = self.owner.current_mode()
        base = self.owner.data_directory
        overwrite = False
        if self._material_exists(definition["name"], library):
            answer = QMessageBox.question(
                self, "Material already exists",
                f"Material '{definition['name']}' already exists.\n\nOverwrite it with this composition "
                "and recalculate the attenuation table?\nChoose No to go back and save it under a new name.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True

        def accepted(result):
            # Use the library everywhere and select the new material in the target field.
            self.owner.material_applied(definition, result)
            self.status.setText(f"'{definition['name']}' created and applied. "
                                "The window stays open for more materials.")

        self.status.setText(f"Creating '{definition['name']}' (XCOM)…")
        self.owner.start_task(lambda log: create_material(definition, library, geometry=mode, base_directory=base,
                                                          cancel=self.owner.cancel_event, progress=log, overwrite=overwrite),
                              accepted, cancellable=True)
