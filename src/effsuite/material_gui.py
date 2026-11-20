"""The material editor tab: the original Material workbook as a form.

The user enters a name, a density and up to 10 compounds with relative
weights. "Create Material" runs XCOM (see materials.py) and saves the
composition and attenuation files in the chosen data folder.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from .materials import TEMPLATE, create_material, default_library, load_composition, save_definition, validate_composition
from .model_io import COMMON_DATA

MAX_COMPOUNDS = 10
RIGHT_ALIGNED = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
SUMMARY_NEUTRAL = "background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;padding:4px 8px;color:#334155;font-weight:500;"
SUMMARY_OK = "background:#f0fdf4;border:1px solid #bbf7d0;border-radius:4px;padding:4px 8px;color:#166534;font-weight:600;"
SUMMARY_ERROR = "background:#fef2f2;border:1px solid #fecaca;border-radius:4px;padding:4px 8px;color:#991b1b;font-weight:500;"


class MaterialEditor(QWidget):
    """Material form. ``owner`` is the main window (for status, tasks and data folder)."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.loading = False   # True while we fill the form ourselves (no recalculation)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addLayout(self._title_bar())
        layout.addWidget(self._name_and_density_box())
        layout.addWidget(self._composition_box(), 1)
        layout.addWidget(self._output_box())
        self.name.textChanged.connect(self.update_fractions)
        self.density.textChanged.connect(self.update_fractions)

    # --- building the form -------------------------------------------------
    def _title_bar(self):
        bar = QHBoxLayout()
        title = QLabel("Material & XCOM Attenuation Builder")
        title.setStyleSheet("font-size:13.5pt;font-weight:700;color:#0f172a;")
        bar.addWidget(title)
        bar.addStretch()
        # Shown when the user came here from a source form's "Edit" button.
        self.return_button = QPushButton("◀ Return to Source")
        self.return_button.setVisible(False)
        self.return_button.setStyleSheet("font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #93c5fd;"
                                         "padding:5px 14px;border-radius:5px;")
        self.return_button.clicked.connect(self.return_to_caller)
        bar.addWidget(self.return_button)
        return bar

    def _name_and_density_box(self):
        box = QGroupBox("1. Material Name && Bulk Density")   # "&&" shows a single "&"
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
        box = QGroupBox(f"2. Chemical Composition (up to {MAX_COMPOUNDS} compounds)")
        column = QVBoxLayout(box)
        column.setSpacing(6)
        column.setContentsMargins(10, 12, 10, 8)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        for text, action in [("📂 Load Composition / Excel…", self.load), ("💾 Store JSON…", self.save),
                             ("📋 Copy Excel Template…", self.copy_template), ("🧹 Clear", self.clear)]:
            button = QPushButton(text)
            button.clicked.connect(action)
            buttons.addWidget(button)
        buttons.addStretch()
        column.addLayout(buttons)

        # Columns: formula, relative weight, normalized fraction (calculated, read-only).
        self.table = QTableWidget(MAX_COMPOUNDS, 3)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(25)
        self.table.setHorizontalHeaderLabels(["Chemical Formula (e.g. H2O, NaCl, C6H12O6)", "Relative Weight by Mass",
                                              "Normalized Mass Fraction [%]"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.update_fractions)
        column.addWidget(self.table, 1)

        self.summary = QLabel("Enter chemical formulas and relative weights.")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(SUMMARY_NEUTRAL)
        column.addWidget(self.summary)
        return box

    def _output_box(self):
        box = QGroupBox("3. Output Data Folder && XCOM Generation")
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
        generate = QPushButton("⚡ Create Material and Attenuation Table")
        generate.setStyleSheet("font-weight:600;font-size:10pt;background:#16a34a;color:#ffffff;"
                               "border:1px solid #15803d;padding:7px 18px;border-radius:5px;")
        generate.clicked.connect(self.generate)
        row.addWidget(generate)
        return box

    # --- reading and filling the form --------------------------------------
    def return_to_caller(self):
        """Go back to the tab the user came from (the source tab by default)."""
        tab = getattr(self.owner, "_return_tab_index", None)
        self.owner.tabs.setCurrentIndex(tab if tab is not None else 2)

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
            self.summary.setText(f'✔ {len(definition["components"])} compound(s), density = {definition["density_g_cm3"]:g} g/cm³, '
                                 f"total weight = {total:g} (normalized to 100%).")
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
            self.owner.error(exc)
            return
        folder = self._start_folder("Composition")
        folder.mkdir(parents=True, exist_ok=True)
        filename, _ = QFileDialog.getSaveFileName(self, "Store composition definition",
                                                  str(folder / (definition["name"] + ".material.json")), "Material JSON (*.json)")
        if filename:
            try:
                save_definition(filename, definition)
                self.owner.status.setText("Saved " + filename)
            except Exception as exc:
                self.owner.error(exc)

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
                self.owner.error(f"Could not copy the template to {filename}: {exc}")

    def browse(self, *unused):
        folder = QFileDialog.getExistingDirectory(self, "Output data folder", self.library.text())
        if folder:
            self.library.setText(folder)

    def _material_exists(self, name: str, library: Path, base: Path) -> bool:
        """True when creating ``name`` would replace an existing material."""
        def has(folder: Path) -> bool:
            return any((folder / sub / (name + ".txt")).exists() for sub in ("Composition", "Material"))
        # A new library starts as a copy of the base data, so check the base too.
        return has(library) if library.exists() else has(base)

    def generate(self, *unused):
        """Run XCOM and save the material (asks before replacing an existing one)."""
        try:
            definition = self.collect()
        except Exception as exc:
            self.owner.error(exc)
            return
        if not self.library.text().strip():
            self.owner.error("Choose an output data folder")
            return
        library = Path(self.library.text().strip())
        mode = self.owner.current_mode()
        base = self.owner.data_directory
        overwrite = False
        if self._material_exists(definition["name"], library, Path(base) if base else COMMON_DATA):
            answer = QMessageBox.question(
                self, "Material Already Exists",
                f"Material '{definition['name']}' already exists.\n\nDo you want to overwrite it with this new composition "
                "and recalculate attenuation?\n(Select 'No' to go back and rename it to save as a new material).",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True

        def accepted(result):
            # Use the library everywhere, select the new material where the user came from.
            self.owner.data_directory = result["data_directory"]
            self.owner.data_label.setText("Data library: " + result["data_directory"])
            self.owner.refresh_materials()
            self.owner.changed()
            self.owner.status.setText("Created " + definition["name"] + " — applied to selection.")
            self.owner.log.appendPlainText("Material saved: " + result["attenuation_file"])
            target_input = getattr(self.owner, "_target_material_input", None)
            if isinstance(target_input, QComboBox):
                try:
                    target_input.setCurrentText(definition["name"])
                except RuntimeError:
                    pass   # the form was rebuilt meanwhile (mode change): nothing to select
            tab = getattr(self.owner, "_return_tab_index", None)
            if tab is not None:
                self.owner.tabs.setCurrentIndex(tab)

        self.owner.start_task(lambda log: create_material(definition, library, geometry=mode, base_directory=base,
                                                          cancel=self.owner.cancel_event, progress=log, overwrite=overwrite),
                              accepted, cancellable=True)
