"""Desktop GUI (PySide6): guided workflow over the Start, Detector, Standard & Sample, Efficiency and Library / Certificate pages."""
from __future__ import annotations
from functools import partial
import os
import json
import math
import multiprocessing
from pathlib import Path
import threading
import time

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt, QTimer, QRect, QSize, QPointF
from PySide6.QtGui import QAction, QFont, QPainter, QPen, QColor, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
                               QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QSplitter, QScrollArea, QStyledItemDelegate, QFrame, QRadioButton, QButtonGroup, QDialog, QListView, QSizePolicy, QProgressDialog, QTextBrowser)

from .model_io import (COMMON_DATA, MODES, fields, read_model, model_bytes, calibration_rows, normalize_nuclides, default_material_density,
                       find_material_file, material_names)
from .suite import VERSION, run_project, validate_project
from .parallel_coincidence import CalculationCancelled, CoincidenceError
from . import tcs_uncertainty
from . import updater
from .qt_icons import icon, with_icon, OPEN, SAVE, FOLDER, RUN, STOP, NEXT, CLEAR, INFO, WARNING
from . import gui_theme as theme
from .gui_theme import app_stylesheet, set_role, set_size



class PaintedRadio(QRadioButton):
    """Custom-painted radio button whose indicator dot is always visible regardless of OS theme or DPI."""
    INDICATOR_D = 16

    def __init__(self, text="", parent=None):
        """Radio button drawn by hand, so it looks the same on every Windows theme."""
        super().__init__(text, parent)
        f = self.font()
        f.setWeight(QFont.Weight.DemiBold)
        self.setFont(f)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        """Room for the circle and the text."""
        fm = self.fontMetrics()
        return QSize(self.INDICATOR_D + 10 + fm.horizontalAdvance(self.text()) + 8, max(self.INDICATOR_D + 6, fm.height() + 6))

    def minimumSizeHint(self):
        """Smallest useful size."""
        fm = self.fontMetrics()
        return QSize(self.INDICATOR_D + 60, max(self.INDICATOR_D + 6, fm.height() + 6))

    def paintEvent(self, event):
        """Draw the circle (filled when selected) and the text."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        d = self.INDICATOR_D
        center = QPointF(2 + d / 2.0, h / 2.0)
        enabled = self.isEnabled()
        blue = QColor(theme.ACCENT) if enabled else QColor(theme.TEXT_TERTIARY)
        ring = blue if (self.isChecked() or (self.underMouse() and enabled)) else (QColor("#a9a9b2") if enabled else QColor(theme.SEPARATOR))
        if self.isChecked():
            # Filled accent disc with a white centre, as on macOS.
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(blue)
            p.drawEllipse(center, d / 2.0 - 0.5, d / 2.0 - 0.5)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(center, 3.0, 3.0)
        else:
            p.setPen(QPen(ring, 1.2))
            p.setBrush(QColor(theme.SURFACE) if enabled else QColor(theme.FILL))
            p.drawEllipse(center, d / 2.0 - 1.0, d / 2.0 - 1.0)
        if self.hasFocus():
            p.setPen(QPen(QColor(theme.ACCENT), 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(center, d / 2.0 + 1.5, d / 2.0 + 1.5)
        p.setPen(QColor(theme.TEXT) if enabled else QColor(theme.TEXT_TERTIARY))
        p.setFont(self.font())
        p.drawText(QRect(d + 10, 0, max(10, self.width() - d - 10),
                         h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


def _fit_dialog(dialog):
    """Size a dialog to its content at its actual width.

    The default size is computed from the word-wrapped labels at a narrower
    width, which leaves the dialog too tall and the spare height inside the labels.
    """
    width = max(dialog.minimumWidth(), dialog.sizeHint().width())
    height = dialog.heightForWidth(width)
    if height > 0:
        dialog.resize(width, height)


def documents(folder=""):
    """A folder in the EffSuite data root (created if needed)."""
    from .paths import get_effsuite_root
    path = get_effsuite_root() / folder if folder else get_effsuite_root()
    path.mkdir(parents=True, exist_ok=True)
    return path


def numeric(text):
    """Read a number typed by the user ("0,5" works too); NaN and infinity are refused."""
    text = str(text).strip()
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Enter a finite number")
    return value


class NumberEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        """Text box for one number, right-aligned."""
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
    def value(self):
        """The number typed in the box (a comma is accepted as decimal point)."""
        return numeric(self.text())


SHORT_LABELS = {
    "Bulletization (crystal rounding) radius":"Bulletization radius",
    "Crystal hole (cavity) diameter":"Crystal bore diameter",
    "Crystal hole (cavity) length":"Crystal bore length",
    "End cap (housing) diameter":"End cap diameter",
    "End cap (housing) thickness":"End cap thickness",
    "End cap (housing) material":"End cap material",
    "Mount cup (holder) thickness":"Mount cup thickness",
    "Mount cup (holder) material":"Mount cup material",
    "Sample bottom–well bottom distance":"Sample–well bottom gap",
}


def _field_label(label, unit):
    """Short label with its unit for a form field."""
    short = SHORT_LABELS.get(label, label)
    if unit in ("mm", "g/cm³"):
        lbl = QLabel(f"{short} <span style='color:{theme.TEXT_SECONDARY};font-size:9pt;'>[{unit}]</span>")
    else:
        lbl = QLabel(short)
    lbl.setToolTip(f"{label} ({unit})")
    set_role(lbl, "fieldLabel")
    return lbl


def form_value(edit, label, unit):
    """The value of one form field, checked (material name or number)."""
    if unit=="material":
        value = edit.currentText().strip()
        if not value:
            raise ValueError(label+": choose a material")
        return value
    try:
        return edit.value()
    except ValueError as exc:
        raise ValueError(f"{label}: enter a finite number in {unit}") from exc


class ModelForm(QWidget):
    changed = Signal()
    def __init__(self, mode, kind, owner=None, parent=None):
        """Form with one input per detector field (see model_io.fields)."""
        super().__init__(parent)
        self.mode = mode
        self.kind = kind
        self.owner = owner
        self.inputs = {}
        grid = QGridLayout(self)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(2, 2, 2, 2)
        materials = material_names()
        def_fields = fields(mode, kind, extended=True)
        if kind=="detector":
            if mode=="well":
                groups = [("Crystal and well (Standard)", [0, 1, 3, 4, 2, 5, 6]),
                        ("Holder and dead layers (Optional)", [7, 8, 9, 10, 11])]
            elif mode=="marinelli":
                groups = [("Crystal", [2, 3, 11, 4, 5, 9, 8, 12]), ("Housing, window and holder", [0, 1, 14, 6, 7, 13, 10, 15])]
            else:
                groups = [("Crystal", [2, 3, 11, 4, 5, 9, 8,
                                       14]), ("Housing, window, holder and absorber", [0, 1, 16, 6, 7, 15, 10, 17, 12, 13, 18])]
        else:
            groups = [("Source", list(range(len(def_fields))))]
        for col, (title, indices) in enumerate(groups):
            box = QGroupBox(title)
            form = QFormLayout(box)
            form.setVerticalSpacing(5)
            form.setHorizontalSpacing(10)
            form.setContentsMargins(10, 8, 10, 6)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for index in indices:
                label, unit = def_fields[index]
                if unit=="material":
                    edit = QComboBox()
                    edit.setEditable(True)
                    edit.setMinimumWidth(95)
                    edit.setMaximumWidth(145)
                    edit_view = QListView(edit)
                    edit.setView(edit_view)
                    edit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                    edit.addItem("")
                    edit.addItems(materials)
                    edit.currentTextChanged.connect(self.changed)
                    if mode=="well" and index==11:
                        edit.setCurrentText("copper")
                    btn = QPushButton("Edit")
                    btn.setFixedWidth(58)
                    set_size(btn, "small")
                    btn.setToolTip(f"Edit the composition or density of {label.lower()} in the Material Editor")
                    btn.clicked.connect(partial(self.modify_material, index))
                    cell = QWidget()
                    cl = QHBoxLayout(cell)
                    cl.setContentsMargins(0, 0, 0, 0)
                    cl.setSpacing(4)
                    cl.addWidget(edit, 1)
                    cl.addWidget(btn)
                    self.inputs[index] = edit
                    form.addRow(_field_label(label, unit), cell)
                else:
                    edit = NumberEdit()
                    edit.setPlaceholderText("0.0 mm")
                    edit.setMinimumWidth(85)
                    edit.setMaximumWidth(115)
                    edit.textEdited.connect(self.changed)
                    if mode=="well" and index in (7, 8):
                        edit.setPlaceholderText("Default: absorber")
                    self.inputs[index] = edit
                    form.addRow(_field_label(label, unit), edit)
            grid.addWidget(box, 0, col, Qt.AlignmentFlag.AlignTop)
        grid.setRowStretch(1, 1)
    def modify_material(self, index):
        """Open the material editor for the material chosen in field ``index``."""
        if self.owner and hasattr(self.owner, "open_material_editor_for_input"):
            label = fields(self.mode, self.kind, extended=True)[index][0]
            self.owner.open_material_editor_for_input(self.inputs[index], "Detector: "+label)
    def values(self):
        """The detector model as a list, in file order (raises ValueError on bad input)."""
        def_fields = fields(self.mode, self.kind, extended=True)
        res = []
        for i, (label, unit) in enumerate(def_fields):
            if i in self.inputs:
                edit = self.inputs[i]
                if isinstance(edit, QComboBox):
                    text = edit.currentText().strip()
                    res.append(text if text else ("copper" if i == 11 else ""))
                else:
                    text = edit.text().strip()
                    if not text:
                        res.append(None if i in (7, 8) else 0.0)
                    else:
                        # Same rules as the other forms: "0,5" is accepted, NaN/inf are not.
                        try:
                            res.append(numeric(text))
                        except ValueError as exc:
                            raise ValueError(f"{label}: enter a finite number in {unit}") from exc
        if self.mode == "well" and self.kind == "detector":
            dd = res[2] if len(res) > 2 and res[2] is not None else 0.0
            if res[7] is None:
                res[7] = dd
            if res[8] is None:
                res[8] = dd
            if res[9] is None:
                res[9] = 0.0
            if res[10] is None:
                res[10] = 0.0
            if not res[11]:
                res[11] = "copper"
            if res[7] == dd and res[8] == dd and res[9] == 0.0 and res[10] == 0.0 and res[11] == "copper":
                return res[:7]
            return res
        return [form_value(self.inputs[i], label, unit) for i, (label, unit) in enumerate(def_fields)]
    def set_values(self, values):
        """Fill the form from a detector model (converts EFFTRAN/MEFFTRAN forms)."""
        if self.kind == "detector":
            if self.mode == "marinelli" and len(values) == 19:
                values = list(values[:12]) + [values[14], values[15], values[16], values[17]]
            elif self.mode in ("cylindrical", "efftran") and len(values) == 16:
                values = list(values[:12]) + [0.0, 0.0, values[12], values[13], values[14], values[15], "copper"]
        for index in sorted(self.inputs):
            edit = self.inputs[index]
            if index < len(values):
                val = values[index]
                if isinstance(edit, QComboBox):
                    edit.setCurrentText(str(val))
                else:
                    if val is not None and str(val).strip():
                        edit.setText(str(float(val)))
                    else:
                        edit.clear()
            else:
                if isinstance(edit, QComboBox):
                    edit.setCurrentText("copper" if index==11 else "")
                else:
                    edit.clear()


class SourceForm(QWidget):
    changed = Signal()
    kind_edited = Signal(str)
    def __init__(self, mode, owner=None):
        """Forms for the sample and the standard, side by side (standard first, as in the original EFFTRAN)."""
        super().__init__()
        self.mode = mode
        self.owner = owner
        self.inputs = {}
        self._setting_values = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QGroupBox("Geometry and materials")
        g = QGridLayout(card)
        g.setHorizontalSpacing(20)
        g.setVerticalSpacing(8)
        hdr_param = QLabel("Parameter")
        set_role(hdr_param, "columnHeader")
        g.addWidget(hdr_param, 0, 0)
        self._col_headers = {}
        self._standard_widgets = []   # everything in the standard column (hidden for summing only)
        self._grid = g
        for column, (kind, subtitle) in enumerate([("standard", "Standard (reference)"), ("sample", "Sample (measured)")], 1):
            hdr = QLabel(subtitle)
            hdr.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            set_role(hdr, "columnHeader")
            g.addWidget(hdr, 0, column)
            self._col_headers[kind] = hdr
            if kind=="standard":
                self._standard_widgets.append(hdr)
        order = [2, 5, 7, 0, 4, 1, 3, 6] if mode=="marinelli" else [1, 5, 7, 0, 2, 3, 6, 4]
        materials = material_names()
        for row, index in enumerate(order, 1):
            label, unit = fields(mode, "sample")[index]
            g.addWidget(_field_label(label, unit), row, 0)
            for column, kind in enumerate(("standard", "sample"), 1):
                if unit=="material":
                    edit = QComboBox()
                    edit.setEditable(True)
                    edit.setMinimumContentsLength(10)
                    edit_view = QListView(edit)
                    edit.setView(edit_view)
                    edit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                    edit.addItem("")
                    edit.addItems(materials)
                    if index==5:
                        edit.currentTextChanged.connect(lambda t, k=kind:self._on_source_material_changed(k, t))
                    else:
                        edit.currentTextChanged.connect(lambda _t, k=kind:(self.kind_edited.emit(k.title()), self.changed.emit()))
                    btn = QPushButton("Edit")
                    btn.setFixedWidth(58)
                    set_size(btn, "small")
                    btn.setToolTip(f"Edit the composition or nominal density [g/cm³] of the {kind} {label.lower()}")
                    btn.clicked.connect(partial(self.modify_material, kind, index))
                    cell = QWidget()
                    cl = QHBoxLayout(cell)
                    cl.setContentsMargins(0, 0, 0, 0)
                    cl.setSpacing(4)
                    cl.addWidget(edit, 1)
                    cl.addWidget(btn)
                    self.inputs[kind, index] = edit
                    g.addWidget(cell, row, column)
                    if kind=="standard":
                        self._standard_widgets.append(cell)
                else:
                    edit = NumberEdit()
                    edit.setPlaceholderText(f"0.0 {unit}")
                    edit.textEdited.connect(lambda _t, k=kind:(self.kind_edited.emit(k.title()), self.changed.emit()))
                    self.inputs[kind, index] = edit
                    g.addWidget(edit, row, column)
                    if kind=="standard":
                        self._standard_widgets.append(edit)
        row = len(order)+1
        self.load_buttons = {}
        self.save_buttons = {}
        for column, kind in enumerate(("standard", "sample"), 1):
            bar = QHBoxLayout()
            bar.setSpacing(6)
            load = with_icon(set_role(QPushButton(f"Load {kind}…"), "tinted"), OPEN)
            save = with_icon(QPushButton(f"Store {kind}…"), SAVE)
            bar.addWidget(load)
            bar.addWidget(save)
            g.addLayout(bar, row, column)
            self.load_buttons[kind] = load
            self.save_buttons[kind] = save
            if kind=="standard":
                self._standard_widgets += [load, save]
        g.setColumnStretch(1, 1)
        g.setColumnStretch(2, 1)
        outer.addWidget(card)
        outer.addStretch(1)
    def _on_source_material_changed(self, kind:str, material_name:str):
        """A new source material: fill in its default density."""
        if not self._setting_values and (kind, 7) in self.inputs:
            mat = material_name.strip()
            if mat:
                data_dir = getattr(self.owner, "data_directory", None) if self.owner else None
                try:
                    self.inputs[kind, 7].setText(str(float(default_material_density(mat, data_dir))))
                except CoincidenceError:
                    pass  # name not complete or unknown yet: keep the density already shown
        self.kind_edited.emit(kind.title())
        self.changed.emit()
    def set_standard_visible(self, visible:bool):
        """Show the standard column only when an efficiency transfer is done.

        Coincidence summing only needs the sample: the standard column is then
        hidden (its values are kept and come back with the column).
        """
        for widget in self._standard_widgets:
            widget.setVisible(visible)
        self._grid.setColumnStretch(1, 1 if visible else 0)
    def modify_material(self, kind, index):
        """Open the material editor for a material of the sample or standard form."""
        if self.owner and hasattr(self.owner, "open_material_editor_for_input"):
            label = fields(self.mode, "sample")[index][0]
            self.owner.open_material_editor_for_input(self.inputs[kind, index], kind.title()+" — "+label)
    def values(self, kind):
        """The sample or standard model (``kind``) as a list, in file order."""
        return [form_value(self.inputs[kind, i], kind.title()+" — "+label, unit) for i, (label, unit) in enumerate(fields(self.mode, kind))]
    def set_values(self, kind, values):
        """Fill the sample or standard form from a model."""
        vals = list(values)
        if len(vals)==7:
            data_dir = getattr(self.owner, "data_directory", None) if self.owner else None
            vals.append(default_material_density(vals[5], data_dir))
        self._setting_values = True
        try:
            for i, value in enumerate(vals):
                if (kind, i) not in self.inputs:
                    continue
                edit = self.inputs[kind, i]
                if isinstance(edit, QComboBox):
                    edit.setCurrentText(str(value))
                else:
                    edit.setText(str(float(value)))
        finally:
            self._setting_values = False


class Schematic(QWidget):
    """Live geometry preview (dimensioned cross-section) shown inside a tab."""
    def __init__(self, owner, default_kind="Sample"):
        """Live geometry preview widget for one tab."""
        super().__init__()
        self.owner = owner
        from .geometry_view import LiveGeometryWidget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.live_widget = LiveGeometryWidget(owner, default_kind=default_kind)
        layout.addWidget(self.live_widget, 1)
    def set_kind(self, kind):
        """Show the sample, the standard or the detector only."""
        self.live_widget.set_kind(kind)
    def refresh(self, *unused):
        """Redraw from the current form values."""
        self.live_widget.refresh()
    def open(self, *unused):
        """Open the full-screen, dimensioned view."""
        self.live_widget.open()


def _num_item(text, *, editable=True, bold=False, bg=None, fg=None,
              align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter, tooltip=""):
    """A table cell with the given look (alignment, bold, colours, tooltip)."""
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align)
    if not editable:
        item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
    if bold:
        font = item.font()
        font.setBold(True)
        item.setFont(font)
    if bg:
        item.setBackground(QColor(bg))
    if fg:
        item.setForeground(QColor(fg))
    if tooltip:
        item.setToolTip(tooltip)
    return item


class CalibrationTable(QTableWidget):
    def keyPressEvent(self, event):
        """Ctrl+V pastes a block of cells copied from Excel or a text file."""
        if event.matches(__import__('PySide6.QtGui', fromlist=['QKeySequence']).QKeySequence.StandardKey.Paste):
            text = QApplication.clipboard().text()
            start = max(0, self.currentRow())
            column = max(0, self.currentColumn())
            # Fill all cells silently, then announce ONE change at the end
            # (one signal per cell made the window refresh hundreds of times).
            self.blockSignals(True)
            try:
                self._paste_rows(text, start, column)
            finally:
                self.blockSignals(False)
            self.itemChanged.emit(self.item(start, column))
            return
        super().keyPressEvent(event)
    def _paste_rows(self, text, start, column):
        """Write pasted text (tab, ; , or space separated) into the table."""
        import csv
        for offset, line in enumerate(text.splitlines()):
            if start+offset>=self.rowCount():
                break
            if '\t' in line:
                cells = line.split('\t')
            elif ';' in line or ',' in line:
                cells = next(csv.reader([line], delimiter=';' if ';' in line else ','))
            else:
                cells = line.split()
            for j, token in enumerate(cells):
                if column+j<3:   # only energy, efficiency and uncertainty columns
                    self.setItem(start+offset, column+j, _num_item(token.strip(), editable=True))


class CalibrationDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        """Only the first 3 columns (energy, efficiency, uncertainty) are editable."""
        editor = super().createEditor(parent, option, index) if index.column()<3 else None
        if isinstance(editor, QLineEdit):
            editor.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        return editor


CANCELLED_MESSAGE = "Calculation cancelled"


class TaskWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()
    progress = Signal(str)
    def __init__(self, operation):
        """Runs one slow operation in a background thread."""
        super().__init__()
        self.operation = operation
    @Slot()
    def run(self):
        """Run the operation; report its result or its error to the window."""
        try:
            self.succeeded.emit(self.operation(self.progress.emit))
        except CalculationCancelled:
            self.failed.emit(CANCELLED_MESSAGE)
        except CoincidenceError as exc:
            self.failed.emit(str(exc))   # our own, already readable messages
        except Exception as exc:
            # Unexpected error: keep its type (a bare KeyError would only show 'energy')
            # and print the full traceback in the console for debugging.
            import traceback
            traceback.print_exc()
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.finished.emit()


def get_app_icon() -> QIcon:
    """Return the high-resolution multi-size application icon for EffSuite."""
    root_assets = Path(__file__).parent / "assets"
    ico = root_assets / "icon.ico"
    if ico.is_file():
        return QIcon(str(ico))
    png = root_assets / "icon.png"
    if png.is_file():
        return QIcon(str(png))
    return QIcon()


class UpdateSignals(QObject):
    """Results of the update check and download, sent from their worker threads."""
    checked = Signal(object, bool)        # Release or None, manual check
    check_failed = Signal(str, bool)
    progress = Signal(int, int)           # bytes received, total
    downloaded = Signal(object)           # installer path
    download_failed = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        """Build the main window: top bar, tabs, log panel and status bar."""
        super().__init__()
        self._loading = True
        self.dirty = False
        self.thread = None
        self.worker = None
        self.cancel_event = threading.Event()
        self.project_path = None
        self.setWindowIcon(get_app_icon())
        from .paths import get_data_dir
        self.data_directory = str(get_data_dir())   # the user's own materials and models
        self.transfer_result = None
        self.summing_result = None
        self.library_file = None
        self.certificate_file = None
        self.library_rows = []
        self.certificate_rows = []
        self.calibration_template = None
        self.last_task = None
        self._target_material_input = None
        self.btn_export_cal_on_sum = {}
        # TCS uncertainty inputs (kept here because the tabs are rebuilt on geometry changes).
        self.tcs_settings = tcs_uncertainty.validate_settings(None)
        self.tcs_inputs = {}
        self._tcs_note_shown = False   # log the "result folder keeps old u(C)" note once per result
        self.btn_export_sum_on_eff = None
        self.update_signals = UpdateSignals(self)
        self.update_signals.checked.connect(self._update_checked)
        self.update_signals.check_failed.connect(self._update_check_failed)
        self.update_signals.progress.connect(self._update_progress)
        self.update_signals.downloaded.connect(self._update_downloaded)
        self.update_signals.download_failed.connect(self._update_download_failed)
        self._update_busy = False
        self._pending_release = None
        self._download_dialog = None
        self._download_cancel = None
        self.setWindowTitle(f"EffSuite v{VERSION} — EFFTRAN / MEFFTRAN / WEFFTRAN")
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        init_w = min(1920, int(avail.width()*0.96)) if avail else 1680
        init_h = min(1040, int(avail.height()*0.94)) if avail else 920
        self.setMinimumSize(1024, 650)
        self.resize(init_w, init_h)
        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)
        self.setCentralWidget(body)
        self._build_top_bar(outer)
        # The material editor is a separate, non-modal window. It is created
        # once here (not with the tabs, which are rebuilt on geometry changes),
        # so a material being typed survives a geometry change.
        from .material_gui import MaterialEditor
        self.material_editor = MaterialEditor(self)
        self.material_editor.setStyleSheet(app_stylesheet())
        self.material_editor.setWindowIcon(get_app_icon())
        self._build_tabs_and_log(outer)
        self._build_menus()
        self.workers.valueChanged.connect(self.changed)
        self.setStyleSheet(app_stylesheet())
        self.append_log(f"EffSuite v{VERSION} started")
        self.append_log("EffSuite built by ChatGPT, Gemini and Claude under the supervision of G. Lutter")
        self.append_log(f"Data directory: {self.data_directory or 'bundled assets'}")
        # Fill the material lists now, so the laboratory's own materials are
        # offered from the start (not only after a mode change).
        self.refresh_materials()
        self._loading = False
        QTimer.singleShot(100, self.check_first_run_disclaimer)
    def _build_top_bar(self, outer):
        """Top bar: geometry, software, workers, data folder and help buttons."""
        top_frame = QFrame()
        top_frame.setObjectName("TopBar")
        top = QHBoxLayout(top_frame)
        top.setContentsMargins(12, 7, 10, 7)
        top.setSpacing(8)
        app_lbl = QLabel("Geometry")
        set_role(app_lbl, "secondary")
        top.addWidget(app_lbl)
        self.mode = QComboBox()
        self.mode.setMinimumWidth(185)
        for key, name in MODES.items():
            self.mode.addItem(name+{"cylindrical":" — Cylindrical", "marinelli":" — Marinelli", "well":" — Well"}[key], key)
        top.addWidget(self.mode)
        sw_lbl = QLabel("Software")
        set_role(sw_lbl, "secondary")
        top.addWidget(sw_lbl)
        self.software = QComboBox()
        self.software.setToolTip("Auto: GammaVision for .EFT / .LIB files, Genie 2000 for .CAL / .NLB / .CTF files")
        for label, key in (("Auto (.CAL/.NLB/.CTF vs .EFT/.LIB)",
                            ""), ("Genie 2000 (.CAL/.NLB/.CTF)", "genie"), ("GammaVision (.EFT/.LIB, untested)", "gammavision")):
            self.software.addItem(label, key)
        # The choice is passed to the backend through the EFFSUITE_SOFTWARE
        # environment variable. Show the value already set (if any), so the
        # screen always matches what is really used.
        forced = os.environ.get("EFFSUITE_SOFTWARE", "").strip().lower()
        self.software.setCurrentIndex(max(0, self.software.findData(forced)))
        self.software.currentIndexChanged.connect(lambda *_:os.environ.__setitem__("EFFSUITE_SOFTWARE", self.software.currentData()))
        top.addWidget(self.software)
        sep_v = set_role(QFrame(), "vseparator")
        top.addWidget(sep_v)
        self.data_button = with_icon(QPushButton("Data folder…"), FOLDER)
        self.data_button.setToolTip("Data folder of this project: your own Composition, Material, Detector, Sample and Standard files.\n"
                                    "The original EFFTRAN / MEFFTRAN materials are always available.\n"
                                    "Default for every session: Tools → Default data folder…")
        self.data_button.clicked.connect(self.choose_data)
        top.addWidget(self.data_button)
        self.data_label = QLabel()
        self._show_data_directory()
        set_role(self.data_label, "caption")
        top.addWidget(self.data_label, 1)
        sep_v2 = set_role(QFrame(), "vseparator")
        top.addWidget(sep_v2)
        wrk_lbl = QLabel("Workers")
        set_role(wrk_lbl, "secondary")
        top.addWidget(wrk_lbl)
        self.workers = QSpinBox()
        self.workers.setRange(0, 64)
        self.workers.setSpecialValueText("Auto")
        self.workers.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.workers.setMinimumWidth(96)
        top.addWidget(self.workers)
        sep_v3 = set_role(QFrame(), "vseparator")
        top.addWidget(sep_v3)
        help_btn = QPushButton("Help")
        help_btn.clicked.connect(lambda:self.show_help_dialog("workflow"))
        top.addWidget(help_btn)
        outer.addWidget(top_frame)
    def _build_tabs_and_log(self, outer):
        """The step tabs and, below them, the status line and the log panel."""
        self.workflow = "both"
        self.summing_source = "nlb"
        self._building = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(150)
        self._refresh_timer.timeout.connect(self._refresh_drawings)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(360)
        self.splitter.addWidget(self.tabs)
        self._build_tabs()
        log_panel = QWidget()
        log_panel.setMinimumHeight(65)
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(0, 2, 0, 0)
        log_layout.setSpacing(6)
        footer = QHBoxLayout()
        footer.setContentsMargins(2, 0, 2, 0)
        footer.setSpacing(8)
        self.status = QLabel("Ready: choose a step above or load the built-in example")
        set_role(self.status, "status")
        footer.addWidget(self.status, 1)
        self.copy_btn = QPushButton("Copy log")
        self.copy_btn.setToolTip("Copy the whole log to the clipboard")
        set_size(self.copy_btn, "small")
        self.copy_btn.clicked.connect(self.copy_log)
        footer.addWidget(self.copy_btn)
        self.clear_btn = with_icon(set_size(QPushButton("Clear"), "small"), CLEAR)
        self.clear_btn.setToolTip("Clear the log")
        self.clear_btn.clicked.connect(self.clear_log)
        footer.addWidget(self.clear_btn)
        self.cancel_button = with_icon(set_size(set_role(QPushButton("Cancel calculation"), "danger"), "small"), STOP)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(lambda:self.cancel_event.set())
        footer.addWidget(self.cancel_button)
        log_layout.addLayout(footer)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(45)
        self.log.setMaximumBlockCount(10000)
        self.log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.log.setPlaceholderText("Calculation log")
        log_layout.addWidget(self.log, 1)
        self.splitter.addWidget(log_panel)
        self.splitter.setStretchFactor(0, 6)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([760, 110])
        outer.addWidget(self.splitter, 1)
    def _build_menus(self):
        """The File, Tools and Help menus."""
        menu = self.menuBar().addMenu("File")
        for label, slot in [
            ("New project", self.new_project),
            ("Open project…", self.open_project),
            ("Save project", self.save_project),
            ("Save project as…", partial(self.save_project, True)),
            ("Open result folder", self.open_results),
            ("Exit", self.close),
        ]:
            action = QAction(label, self)
            action.triggered.connect(slot)
            menu.addAction(action)

        tools_menu = self.menuBar().addMenu("Tools")
        action = QAction("Material Editor…", self)
        action.triggered.connect(lambda:self.open_material_editor_for_input(None))
        tools_menu.addAction(action)
        tools_menu.addSeparator()
        for label, slot, pixmap in [("Default data folder…", self.choose_default_data, FOLDER),
                                    ("Reset default data folder", self.reset_default_data, None)]:
            action = QAction(label, self)
            if pixmap is not None:
                with_icon(action, pixmap)
            action.triggered.connect(slot)
            tools_menu.addAction(action)

        help_menu = self.menuBar().addMenu("Help")
        for label, topic, pixmap in [
            ("Workflow guide", partial(self.show_help_dialog, "workflow"), None),
            ("Materials and density guide", partial(self.show_help_dialog, "materials"), None),
            ("Command line and batch guide", partial(self.show_help_dialog, "cli"), None),
            ("Disclaimer…", lambda:self.show_disclaimer_dialog(is_first_run=False), WARNING),
            ("About EffSuite", partial(self.show_help_dialog, "about"), INFO),
        ]:
            action = QAction(label, self)
            if pixmap is not None:
                with_icon(action, pixmap)
            action.triggered.connect(topic)
            help_menu.addAction(action)
        help_menu.addSeparator()
        action = QAction("Check for updates…", self)
        action.triggered.connect(lambda:self.check_for_updates(manual=True))
        help_menu.addAction(action)
        from .paths import load_settings
        action = QAction("Check for updates at startup", self, checkable=True)
        action.setChecked(bool(load_settings().get(updater.SETTING_AUTO, True)))
        action.toggled.connect(self._set_auto_update_check)
        help_menu.addAction(action)
        self.mode.currentIndexChanged.connect(self.change_mode)

    def check_first_run_disclaimer(self):
        """Show the disclaimer once, the first time the program starts."""
        from .paths import get_effsuite_root
        marker = get_effsuite_root() / ".disclaimer_accepted"
        if not marker.exists():
            self.show_disclaimer_dialog(is_first_run=True)

    def show_disclaimer_dialog(self, is_first_run=False):
        """Dialog explaining that results must be verified before use."""
        from .paths import get_effsuite_root
        dialog = QDialog(self)
        dialog.setWindowTitle("EffSuite disclaimer")
        dialog.setMinimumWidth(540)
        vl = QVBoxLayout(dialog)
        vl.setContentsMargins(18, 16, 18, 16)
        vl.setSpacing(12)

        banner = QFrame()
        banner.setProperty("notice", "danger")
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.setSpacing(6)
        t = QLabel("<b>Disclaimer</b>")
        t.setStyleSheet(f"font-size:12pt;color:{theme.DANGER_TEXT};")
        bl.addWidget(t)

        msg = QLabel(
            f"<p style='color:{theme.TEXT};font-size:10pt;line-height:1.45;margin:0;'>"
            "Provided strictly on an <b>AS-IS</b> basis. <b>G. Lutter accepts NO responsibility or liability</b> "
            "under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. "
            "Users must independently verify all results."
            "</p>"
        )
        msg.setWordWrap(True)
        bl.addWidget(msg)
        vl.addWidget(banner)

        note = QLabel(
            f"<p style='font-size:9.5pt;color:{theme.TEXT_SECONDARY};margin:0;line-height:1.4;'>"
            f"<b>EffSuite v{VERSION}</b>, built by ChatGPT, Gemini and Claude under the supervision of G. Lutter.<br>"
            f"Physics engines based on EFFTRAN / MEFFTRAN / WEFFTRAN by Tim Vidmar and NIST XCOM."
            f"</p>"
        )
        note.setWordWrap(True)
        note.setProperty("notice", "neutral")
        note.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        vl.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = set_role(QPushButton("I understand and accept" if is_first_run else "Close"), "primary")
        btn_ok.setDefault(True)
        def on_accept():
            try:
                marker = get_effsuite_root() / ".disclaimer_accepted"
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("accepted\n", encoding="utf-8")
            except Exception:
                pass
            dialog.accept()
        btn_ok.clicked.connect(on_accept)
        btn_row.addWidget(btn_ok)
        vl.addLayout(btn_row)
        _fit_dialog(dialog)
        dialog.exec()

    def current_mode(self):
        """The selected geometry: "cylindrical", "marinelli" or "well"."""
        return self.mode.currentData()
    def _page(self, title, scrollable=True):
        """An empty tab page (optionally scrollable) with a title."""
        outer = QWidget()
        outer.setObjectName("Page")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        body = QWidget()
        body.setObjectName("PageBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 6, 16, 10)
        layout.setSpacing(8)
        heading = QLabel(title)
        set_role(heading, "pageTitle")
        # Large text reads better slightly tightened (Qt style sheets cannot set tracking).
        hfont = heading.font()
        hfont.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 98.5)
        heading.setFont(hfont)
        layout.addWidget(heading)
        if scrollable:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(body)
            outer_layout.addWidget(scroll, 1)
        else:
            outer_layout.addWidget(body, 1)
        return outer, layout
    def _attach_footer(self, page, row_layout):
        """Add the Previous step / Next navigation bar at the bottom of a page."""
        foot = QFrame()
        foot.setObjectName("PageFooter")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(16, 9, 16, 9)
        fl.setSpacing(8)
        fl.addLayout(row_layout)
        page.layout().addWidget(foot, 0)
    # ---------------------------------------------------------------- guided workflow
    STEP_KEYS = ("welcome", "detector", "source", "efficiency", "ctf", "nlb")
    STEP_TITLES = {"welcome":"Choose calculation", "detector":"Detector", "source":"Standard & Sample",
                 "efficiency":"Efficiency (.CAL / .EFT)", "ctf":"Certificate (.CTF)", "nlb":"Nuclide library (.NLB / .LIB)"}
    RUN_LABELS = {"transfer":"Run efficiency transfer", "summing":"Run coincidence summing", "both":"Run complete analysis"}
    def tab_index(self, key):
        """Position of a step's tab (e.g. "detector")."""
        return self.STEP_KEYS.index(key)
    def visible_steps(self):
        """The steps (tabs) used by the chosen workflow, in order."""
        keys = ["welcome", "detector", "source"]
        if self.workflow in ("transfer", "both"):
            keys.append("efficiency")
        if self.workflow in ("summing", "both"):
            keys.append(self.summing_source)
        return keys
    def _step_banner(self, key, title_text, description="", input_req=None, extra_widgets=None):
        """Step line at the top of a page: step number and title, expected input, page buttons."""
        frame = QFrame()
        frame.setObjectName("StepBanner")
        fl = QHBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)
        h = QLabel(f"<b>{title_text}</b>")
        set_role(h, "stepTitle")
        fl.addWidget(h)
        self._banners[key] = (h, title_text)
        if input_req:
            req = QLabel(f"Input: <span style='color:{theme.TEXT}'>{input_req}</span>")
            set_role(req, "chip")
            fl.addWidget(req)
        fl.addStretch()
        if extra_widgets:
            for w in extra_widgets:
                fl.addWidget(w)
        return frame
    def _nav_row(self, key, extra_btn=None):
        """Previous step / Next buttons for a step page."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        back = QPushButton("Previous step")
        back.clicked.connect(lambda:self.go_step(-1))
        row.addWidget(back)
        row.addStretch()
        if extra_btn is not None:
            row.addWidget(extra_btn)
        nxt = QPushButton("Next")
        nxt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)   # icon after the text
        nxt.clicked.connect(lambda:self.go_step(1))
        row.addWidget(nxt)
        self._nav_next[key] = nxt
        return row
    def go_step(self, delta):
        """Go to the next (delta=1) or previous (delta=-1) step; past the last step, run."""
        keys = self.visible_steps()
        cur = self.tabs.currentIndex()
        key = self.STEP_KEYS[cur] if cur<len(self.STEP_KEYS) else "welcome"
        pos = (keys.index(key) if key in keys else 0)+delta
        if pos>=len(keys):
            self.run_workflow()
            return
        if pos<0:
            return
        self.tabs.setCurrentIndex(self.tab_index(keys[pos]))
    def set_workflow(self, workflow=None, summing_source=None):
        """Choose the workflow (transfer, summing, both) and/or the summing source (nlb, ctf)."""
        if workflow:
            self.workflow = workflow
        if summing_source and summing_source!=self.summing_source:
            # A result calculated from the other file type (NLB vs CTF) no longer applies.
            self.summing_source = summing_source
            self.summing_result = None
        self.apply_workflow()
    def apply_workflow(self):
        """Show only the tabs and buttons that the chosen workflow needs."""
        if not hasattr(self, "efficiency"):
            return
        keys = self.visible_steps()
        for key in ("efficiency", "ctf", "nlb"):
            self.tabs.setTabVisible(self.tab_index(key), key in keys)
        total = len(keys)-1
        if "source" in self._banners:
            label, _ = self._banners["source"]
            self._banners["source"] = (label, "Sample geometry (Standard not needed for coincidence summing)"
                                       if self.workflow=="summing" else "Standard & Sample geometries")
            self.tabs.setTabText(self.tab_index("source"),
                                 "Sample" if self.workflow=="summing" else "Standard && Sample")   # "&&" shows a single "&"
        for i, key in enumerate(keys[1:], 1):
            if key in self._banners:
                label, title = self._banners[key]
                label.setText(f"<b>Step {i} of {total}: {title}</b>")
        summing_only = self.workflow=="summing"
        for key, button in self._nav_next.items():
            if key not in keys:
                continue
            pos = keys.index(key)
            if pos==len(keys)-1:
                button.setText(self.RUN_LABELS[self.workflow])
                with_icon(set_role(button, "success"), RUN)
            else:
                following = keys[pos+1]
                title = "Sample" if following=="source" and summing_only else self.STEP_TITLES[following]
                button.setText(f"Next: {title.replace('&', '&&')}")   # "&&" shows a single "&"
                with_icon(set_role(button, "primary"), NEXT)
        for value, radio in self._workflow_radios.items():
            radio.blockSignals(True)
            radio.setChecked(value==self.workflow)
            radio.blockSignals(False)
        for value, radio in self._source_radios.items():
            radio.blockSignals(True)
            radio.setChecked(value==self.summing_source)
            radio.setEnabled(self.workflow!="transfer")
            radio.blockSignals(False)
        self._source_box.setEnabled(self.workflow!="transfer")
        self.needs_label.setText(self.needs_text())
        self.source_hint.setVisible(self.workflow=="summing")
        if hasattr(self, "source_form"):
            self.source_form.set_standard_visible(self.workflow!="summing")
        for diagram in (getattr(self, "diagram", None), getattr(self, "source_diagram", None)):
            if diagram is not None:
                diagram.live_widget.set_standard_available(self.workflow!="summing")
        if getattr(self, "btn_export_sum_on_eff", None) is not None:
            self.btn_export_sum_on_eff.setVisible(self.workflow=="both")
            self.btn_export_sum_on_eff.setText("Export corrected "+("library (.NLB / .LIB)…" if self.summing_source=="nlb" else "certificate (.CTF)…"))
        if hasattr(self, "btn_export_cal_on_sum"):
            for btn in self.btn_export_cal_on_sum.values():
                btn.setVisible(self.workflow=="both")
    def needs_text(self):
        """HTML list of the files the chosen workflow needs (Start page)."""
        items = ["<b>Detector (.txt)</b> from <code>Data/Detector</code>",
               "<b>Sample (.txt)</b>: geometry, matrix and density, from <code>Data/Standard</code> or <code>Data/Sample</code>"]
        if self.workflow in ("transfer", "both"):
            items += ["<b>Standard (.txt)</b>: calibration source geometry, from <code>Data/Standard</code>",
                    "<b>Reference calibration (.CAL / .EFT / .txt / .csv)</b> from <code>Data/Calibration</code> → exports the Sample .CAL or .EFT"]
        if self.workflow in ("summing", "both"):
            items.append("<b>Genie certificate (.CTF)</b> → exports the corrected .CTF"
                         if self.summing_source=="ctf" else
                         "<b>Nuclide library (Genie .NLB / GammaVision .LIB)</b> from <code>Data/NuclideLibrary</code> → exports the corrected .NLB or .LIB")
        code = f"<span style='font-family:Cascadia Mono,Consolas,monospace;font-size:9pt;color:{theme.TEXT_SECONDARY};'>"
        items = [i.replace("<code>", code).replace("</code>", "</span>") for i in items]
        return "<ol style='margin:0px;line-height:1.35;'>"+"".join(f"<li>{i}</li>" for i in items)+"</ol>"
    def missing_items(self):
        """What must still be entered before running: [(step, message), ...]."""
        out = []
        try:
            self.detector_form.values()
        except Exception as exc:
            out.append(("detector", "Detector: "+str(exc)))
        try:
            self.source_form.values("sample")
        except Exception as exc:
            out.append(("source", str(exc)))
        if self.workflow in ("transfer", "both"):
            try:
                self.source_form.values("standard")
            except Exception as exc:
                out.append(("source", str(exc)))
            try:
                if not self.calibration():
                    out.append(("efficiency", "Efficiency: import the reference calibration (.CAL / .EFT / .txt / .csv)"))
            except Exception as exc:
                out.append(("efficiency", "Efficiency: "+str(exc)))
        if self.workflow in ("summing", "both"):
            if self.summing_source=="ctf" and not self.certificate_rows:
                out.append(("ctf", "Certificate: open the Genie certificate (.CTF)"))
            if self.summing_source=="nlb" and not self.library_rows and not self.nuclides.text().strip():
                out.append(("nlb", "Nuclide library: open the Genie (.NLB) or GammaVision (.LIB) library, or type a nuclide list"))
        return out
    def sync_nuclides(self):
        """Copy the nuclide names of the loaded library/certificate into the nuclide list."""
        rows = self.certificate_rows if self.summing_source=="ctf" else self.library_rows
        if rows:
            self.nuclides.setText(", ".join(dict.fromkeys(str(r["nuclide"]) for r in rows)))
    def run_workflow(self, *unused):
        """Run the chosen workflow, or point the user to the first missing input."""
        missing = self.missing_items()
        if missing:
            self.error("Complete these items before running:\n\n"+"\n".join("• "+text for _, text in missing))
            self.tabs.setCurrentIndex(self.tab_index(missing[0][0]))
            return
        if self.workflow in ("summing", "both"):
            self.sync_nuclides()
        self.calculate(self.workflow)
    def _build_tabs(self):
        """(Re)create every tab for the selected geometry."""
        self._building = True
        while self.tabs.count():
            old = self.tabs.widget(0)
            self.tabs.removeTab(0)
            old.deleteLater()
        self._banners = {}
        self._nav_next = {}
        self._workflow_radios = {}
        self._source_radios = {}
        mode = self.current_mode()
        self._build_welcome_tab()
        self._build_detector_tab(mode)
        self._build_source_tab(mode)
        self._build_efficiency_tab()
        self._build_summing_tabs()
        # The old form fields are gone: "Apply" in the material window has no target any more.
        self._target_material_input = None
        self.material_editor.set_target(None)
        self._building = False
        self.apply_workflow()
        self.refresh_geometry()
    def _build_welcome_tab(self):
        """The Start page: choice of workflow and of the summing input (library or certificate)."""
        page, layout = self._page("Choose the calculation")
        box = QGroupBox("A. Calculation")
        bl = QVBoxLayout(box)
        bl.setSpacing(1)
        bl.setContentsMargins(12, 10, 12, 8)
        group = QButtonGroup(box)
        for value, title, desc in [("both", "Complete analysis: efficiency transfer and coincidence summing (recommended)",
                                    "Exports the transferred Sample .CAL / .EFT and the summing-corrected .NLB / .LIB or .CTF"),
                                 ("transfer", "Efficiency transfer only",
                                  "Computes F_ε(E) = ε_sample / ε_standard and exports the transferred Sample .CAL / .EFT"),
                                 ("summing", "True coincidence summing only",
                                  "Computes cascade summing factors C and exports the corrected .NLB / .LIB or .CTF")]:
            radio = PaintedRadio(title)
            group.addButton(radio)
            bl.addWidget(radio)
            self._workflow_radios[value] = radio
            radio.toggled.connect(lambda checked, v=value:checked and self.set_workflow(workflow=v))
            note = QLabel(desc)
            note.setWordWrap(True)
            set_role(note, "caption")
            note.setContentsMargins(26, 0, 0, 6)
            bl.addWidget(note)
        bl.addStretch(1)
        self._source_box = QGroupBox("B. Coincidence summing file")
        sl = QVBoxLayout(self._source_box)
        sl.setSpacing(1)
        sl.setContentsMargins(12, 10, 12, 8)
        group2 = QButtonGroup(self._source_box)
        for value, title, desc in [("nlb", "Nuclide library (Genie .NLB / GammaVision .LIB), for sample analysis",
                                    "Updates gamma abundances (P_corr = P / C). Lines without a factor (*) are kept unchanged."),
                                 ("ctf", "Genie certificate (.CTF), for calibration certificates",
                                  "Updates certificate emission rates (R_corr = R / C)")]:
            radio = PaintedRadio(title)
            group2.addButton(radio)
            sl.addWidget(radio)
            self._source_radios[value] = radio
            radio.toggled.connect(lambda checked, v=value:checked and self.set_workflow(summing_source=v))
            note = QLabel(desc)
            note.setWordWrap(True)
            set_role(note, "caption")
            note.setContentsMargins(26, 0, 0, 6)
            sl.addWidget(note)
        sl.addStretch(1)
        ab_row = QHBoxLayout()
        ab_row.setSpacing(10)
        ab_row.addWidget(box, 3)
        ab_row.addWidget(self._source_box, 2)
        layout.addLayout(ab_row)
        need = QGroupBox("C. Required files")
        nl = QVBoxLayout(need)
        nl.setContentsMargins(12, 10, 12, 8)
        self.needs_label = QLabel()
        self.needs_label.setWordWrap(True)
        nl.addWidget(self.needs_label)
        layout.addWidget(need)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        start = with_icon(set_role(QPushButton("Start guided setup"), "primary"), NEXT)
        start.setLayoutDirection(Qt.LayoutDirection.RightToLeft)   # icon after the text
        start.clicked.connect(lambda:self.go_step(1))
        example = QPushButton("Load built-in example")
        example.clicked.connect(self.load_example)
        open_project = with_icon(QPushButton("Open project…"), OPEN)
        open_project.clicked.connect(self.open_project)
        row.addWidget(start)
        row.addWidget(example)
        row.addWidget(open_project)
        row.addStretch()
        self._attach_footer(page, row)
        self.tabs.addTab(page, "Start")
    def _build_detector_tab(self, mode):
        """The Detector page: model form and live geometry preview."""
        page, layout = self._page("Detector geometry and materials")
        if mode=="well":
            untested_banner = QFrame()
            untested_banner.setProperty("notice", "warning")
            ub_l = QHBoxLayout(untested_banner)
            ub_l.setContentsMargins(12, 8, 12, 8)
            ub_l.setSpacing(10)
            ub_icon = QLabel()
            ub_icon.setPixmap(icon(WARNING).pixmap(20, 20))
            ub_l.addWidget(ub_icon)
            ub_text = QLabel("<b>WEFFTRAN is not yet qualified in the laboratory.</b> The well engine has the 3D spatial summing model and the ray boundary patch, but has not been fully tested. Verify well results independently.")
            ub_text.setWordWrap(True)
            ub_text.setStyleSheet(f"color:{theme.WARNING_TEXT};")
            ub_l.addWidget(ub_text, 1)
            layout.addWidget(untested_banner)
        load = with_icon(set_role(QPushButton("Load detector…"), "tinted"), OPEN)
        save = with_icon(QPushButton("Store detector…"), SAVE)
        load.clicked.connect(partial(self.load_model, "detector"))
        save.clicked.connect(partial(self.store_model, "detector"))
        layout.addWidget(self._step_banner("detector", "Detector geometry and materials",
                                           input_req="Data\\Detector\\*.txt",
                                           extra_widgets=[self._materials_button(), load, save]))
        det_split = QHBoxLayout()
        det_split.setSpacing(10)
        self.detector_form = ModelForm(mode, "detector", owner=self)
        self.detector_form.changed.connect(self.changed)
        det_split.addWidget(self.detector_form, 6)
        self.diagram = Schematic(self, default_kind="Detector only")
        det_split.addWidget(self.diagram, 5)
        layout.addLayout(det_split, 1)
        self._attach_footer(page, self._nav_row("detector"))
        self.tabs.addTab(page, "Detector")
    def _materials_button(self):
        """Page button that opens the material editor window (no target field)."""
        button = QPushButton("Materials…")
        button.setToolTip("Open the Material Editor in its own window, to create or edit a material "
                          "while this page stays open")
        button.clicked.connect(lambda:self.open_material_editor_for_input(None))
        return button
    def _build_source_tab(self, mode):
        """The Standard & Sample page: sample and standard forms and their preview."""
        page, layout = self._page("Standard and Sample geometries")
        layout.addWidget(self._step_banner("source", "Standard & Sample geometries", input_req="Data\\Standard\\*.txt",
                                           extra_widgets=[self._materials_button()]))
        self.source_hint = QLabel("Coincidence summing only needs the Sample. The Standard (reference "
                                  "calibration source) is used only for efficiency transfer, so it is hidden.")
        self.source_hint.setProperty("notice", "info")
        self.source_hint.setWordWrap(True)
        layout.addWidget(self.source_hint)
        src_split = QHBoxLayout()
        src_split.setSpacing(12)
        self.source_form = SourceForm(mode, owner=self)
        self.source_form.changed.connect(self.changed)
        src_split.addWidget(self.source_form, 3)
        self.source_diagram = Schematic(self, default_kind="Sample")
        src_split.addWidget(self.source_diagram, 2)
        self.source_form.kind_edited.connect(self.source_diagram.set_kind)
        layout.addLayout(src_split, 1)
        for kind in ("standard", "sample"):
            self.source_form.load_buttons[kind].clicked.connect(partial(self.load_model, kind))
            self.source_form.save_buttons[kind].clicked.connect(partial(self.store_model, kind))
        self._attach_footer(page, self._nav_row("source"))
        self.tabs.addTab(page, "Standard && Sample")   # "&&" shows a single "&"
    def _build_efficiency_tab(self):
        """The Efficiency page: reference calibration table, chart and export buttons."""
        page, layout = self._page("Efficiency transfer")
        layout.addWidget(self._step_banner("efficiency", "Reference efficiency calibration (.CAL / .EFT)",
                                           input_req="Data\\Calibration\\*.CAL, *.EFT, *.txt, *.csv (0 &lt; ε &le; 1)"))
        controls = QHBoxLayout()
        load = with_icon(set_role(QPushButton("Import standard efficiency (.CAL / .EFT / CSV)…"), "primary"), OPEN)
        load.clicked.connect(self.import_calibration)
        transfer = with_icon(QPushButton("Calculate transfer only"), RUN)
        transfer.clicked.connect(partial(self.calculate, "transfer"))
        export = with_icon(set_role(QPushButton("Export sample efficiency (.CAL / .EFT)…"), "tinted"), SAVE)
        export.clicked.connect(self.export_calibration)
        self.btn_export_sum_on_eff = with_icon(set_role(QPushButton("Export corrected library (.NLB / .LIB)…"), "tinted"), SAVE)
        self.btn_export_sum_on_eff.clicked.connect(lambda:self.export_genie(self.summing_source))
        for b in (load, transfer, export, self.btn_export_sum_on_eff):
            controls.addWidget(b)
        controls.addStretch()
        layout.addLayout(controls)
        self.efficiency = CalibrationTable(93, 6)
        self.efficiency.setAlternatingRowColors(True)
        self.efficiency.setMinimumHeight(170)
        self.efficiency.setHorizontalHeaderLabels(["E [keV]",
                                                   "Standard ε", "Standard u [%]", "Sample ε (transferred)", "Sample u [%]", "Transfer factor F_ε"])
        self.efficiency.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.efficiency.horizontalHeader().setStretchLastSection(True)
        self.efficiency.itemChanged.connect(self.changed)
        layout.addWidget(self.efficiency, 3)
        self.efficiency.setItemDelegate(CalibrationDelegate(self.efficiency))
        for column, width in enumerate((110, 190, 150, 200, 150, 180)):
            self.efficiency.setColumnWidth(column, width)
        self.efficiency.verticalHeader().setDefaultSectionSize(25)
        self.chart = None
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            self.figure = Figure(figsize=(7, 1.8), tight_layout=True)
            self.chart = FigureCanvasQTAgg(self.figure)
            self.chart.setMinimumHeight(145)
            self.chart.setMaximumHeight(220)
            layout.addWidget(self.chart, 2)
        except ImportError:
            layout.addWidget(QLabel("Install the desktop dependencies to display efficiency graphs."))
        self._attach_footer(page, self._nav_row("efficiency"))
        self.tabs.addTab(page, "Efficiency")
    def _build_summing_tabs(self):
        """The Certificate and Library pages (only the one chosen on the Start page is shown)."""
        for kind, title in [("ctf", "Certificate"), ("nlb", "Library")]:
            page, layout = self._page("True coincidence summing: "+("Genie certificate (.CTF)" if kind=="ctf" else "nuclide library (Genie .NLB / GammaVision .LIB)"))
            need = "Data\\Certificates\\*.CTF (Genie)" if kind=="ctf" else "Data\\NuclideLibrary\\*.NLB (Genie), *.LIB (GammaVision)"
            layout.addWidget(self._step_banner(kind, "Coincidence summing: "+("certificate (.CTF)" if kind=="ctf" else "nuclide library (.NLB / .LIB)"), input_req=need))
            bar = QHBoxLayout()
            load = with_icon(set_role(QPushButton("Open "+("Genie certificate (.CTF)…" if kind=="ctf" else "library (.NLB / GammaVision .LIB)…")), "primary"), OPEN)
            load.clicked.connect(partial(self.import_genie, kind))
            process = with_icon(QPushButton("Calculate summing only"), RUN)
            process.clicked.connect(partial(self.process_genie, kind))
            export = with_icon(set_role(QPushButton("Export corrected "+("certificate (.CTF)…" if kind=="ctf" else "library (.NLB / .LIB)…")), "tinted"), SAVE)
            export.clicked.connect(partial(self.export_genie, kind))
            export_cal = with_icon(set_role(QPushButton("Export sample efficiency (.CAL / .EFT)…"), "tinted"), SAVE)
            export_cal.clicked.connect(self.export_calibration)
            self.btn_export_cal_on_sum[kind] = export_cal
            switch = QPushButton("Switch to "+("nuclide library (.NLB / .LIB)" if kind=="ctf" else "certificate (.CTF)"))
            other = "nlb" if kind=="ctf" else "ctf"
            switch.clicked.connect(lambda checked=False, o=other:(self.set_workflow(summing_source=o),
                                                                  self.tabs.setCurrentIndex(self.tab_index(o))))
            for b in (load, process, export, export_cal):
                bar.addWidget(b)
            bar.addStretch()
            bar.addWidget(switch)
            layout.addLayout(bar)
            if kind=="nlb":
                self.nuclides = QLineEdit()
                self.nuclides.setPlaceholderText("e.g. Co-60, Cs-134, Eu-152, Ba-133, Y-88 (filled from the .NLB / .LIB)")
                self.nuclides.textEdited.connect(self.changed)
                nbar = QHBoxLayout()
                nlbl = QLabel("<b>Nuclides:</b>")
                nbar.addWidget(nlbl)
                nbar.addWidget(self.nuclides, 1)
                layout.addLayout(nbar)
            layout.addLayout(self._tcs_input_row(kind))
            table = QTableWidget(0, 5)
            table.setAlternatingRowColors(True)
            table.setHorizontalHeaderLabels(["Nuclide", "Energy E [keV]", "Summing factor C", "u(C) [%] (k=1)", "Not computed"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            table.horizontalHeader().setStretchLastSection(True)
            table.setColumnWidth(0, 140)
            table.setColumnWidth(1, 160)
            table.setColumnWidth(2, 190)
            table.setColumnWidth(3, 150)
            table.verticalHeader().setDefaultSectionSize(25)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            layout.addWidget(table, 1)
            if kind=="nlb":
                self.library_table = table
            else:
                self.certificate_table = table
            foot_note = QLabel("A_corr = C · A.  * = no EFFTRAN decay data (original yield kept).  "
                               "u(C): propagated from the efficiency uncertainties above; decay-data uncertainties not included "
                               "(see docs/TCS_UNCERTAINTY.md).")
            foot_note.setWordWrap(True)
            set_role(foot_note, "caption")
            layout.addWidget(foot_note)
            self._attach_footer(page, self._nav_row(kind))
            self.tabs.addTab(page, title)
    def _tcs_input_row(self, kind):
        """Inputs of the TCS uncertainty: u(ε_peak), u(ε_total), their correlation, on/off."""
        row = QHBoxLayout()
        label = QLabel("<b>TCS uncertainty inputs:</b>")
        label.setToolTip("Relative standard uncertainties (k=1) of the peak and total efficiencies computed by the "
                         "detector model. They are propagated to u(C) through sensitivity coefficients. "
                         "Defaults are assumptions; enter your laboratory's values. See docs/TCS_UNCERTAINTY.md.")
        row.addWidget(label)
        widgets = {}
        for key, text, low, high, step, decimals, suffix in [
                ("peak_efficiency_percent", "u(ε peak)", 0., 100., .5, 2, " %"),
                ("total_efficiency_percent", "u(ε total)", 0., 100., .5, 2, " %"),
                ("peak_total_correlation", "correlation", -1., 1., .1, 2, "")]:
            caption = QLabel(text)
            set_role(caption, "secondary")
            box = QDoubleSpinBox()
            box.setRange(low, high)
            box.setSingleStep(step)
            box.setDecimals(decimals)
            box.setSuffix(suffix)
            box.setValue(self.tcs_settings[key])
            box.setMinimumWidth(90)
            box.valueChanged.connect(partial(self._tcs_setting_changed, key))
            row.addWidget(caption)
            row.addWidget(box)
            widgets[key] = box
        enabled = QCheckBox("Calculate u(C)")
        enabled.setToolTip("On: each calculation also computes u(C) (four extra engine runs, about one second).\n"
                           "Off: no u(C) column. The summing factors are the same either way.")
        enabled.setChecked(self.tcs_settings["enabled"])
        enabled.toggled.connect(partial(self._tcs_setting_changed, "enabled"))
        row.addWidget(enabled)
        widgets["enabled"] = enabled
        row.addStretch()
        self.tcs_inputs[kind] = widgets
        return row
    def _tcs_setting_changed(self, key, value):
        """Store a TCS uncertainty input and show the same value on the other summing page.

        These inputs change only u(C), never the summing factors or the
        efficiency transfer, so the results stay on screen: u(C) is
        recalculated at once from the sensitivities of the last calculation.
        """
        self.tcs_settings[key] = bool(value) if key == "enabled" else float(value)
        for widgets in self.tcs_inputs.values():
            widget = widgets.get(key)
            if widget is None:
                continue
            widget.blockSignals(True)
            if key == "enabled":
                widget.setChecked(bool(value))
            else:
                widget.setValue(float(value))
            widget.blockSignals(False)
        if self._loading:
            return
        self.dirty = True
        if self.summing_result:
            self.populate_summing()
            calculated = (self.summing_result.get("tcs_uncertainty") or {}).get("enabled", False)
            if self.tcs_settings["enabled"] and not calculated:
                self.append_log("The last calculation was made without u(C); run it again to calculate u(C).")
            elif not self._tcs_note_shown:
                self._tcs_note_shown = True
                self.append_log("u(C) updated on screen for the new inputs. The saved result folder keeps the values "
                                "of the last calculation; run again to save the new ones.")
    def refresh_geometry(self):
        """Redraw both geometry previews."""
        if hasattr(self, "diagram"):
            self.diagram.refresh()
        if hasattr(self, "source_diagram"):
            self.source_diagram.refresh()
    def changed(self, *unused):
        """An input changed: old results no longer apply; redraw shortly after."""
        if self._loading:
            return
        self.dirty = True
        self.transfer_result = None
        self.summing_result = None
        # Results calculated for the old inputs must disappear at once (fast).
        self.efficiency.blockSignals(True)
        for row in range(self.efficiency.rowCount()):
            for col in range(3, 6):
                self.efficiency.takeItem(row, col)
        self.efficiency.blockSignals(False)
        self.populate_summing()
        # Redrawing the chart and the geometry pictures is slow: wait until the
        # user stops typing for 150 ms, then redraw once (see _refresh_drawings).
        self._refresh_timer.start()
    def _refresh_drawings(self):
        """Redraw the chart and the geometry previews (called 150 ms after the last edit)."""
        self.draw_chart()
        self.refresh_geometry()
    def change_mode(self, *unused, keep_detector=True):
        """The geometry was changed: rebuild the forms for the new geometry."""
        if self.thread is not None:
            return
        # Detector values can only be carried over between cylindrical and
        # Marinelli: their fields mean the same thing. A well detector has
        # completely different fields (crystal/well diameters...), so copying
        # values to or from it would put numbers in the wrong boxes.
        old_mode = self.detector_form.mode
        new_mode = self.current_mode()
        compatible = {"cylindrical", "marinelli"}
        saved_detector = None
        if keep_detector and old_mode in compatible and new_mode in compatible:
            try:
                saved_detector = self.detector_form.values()
            except Exception:
                pass  # incomplete form: start the new mode with empty fields
        data_dir = self.data_directory
        self._loading = True
        self._build_tabs()
        self._loading = False
        self.dirty = True
        self.transfer_result = None
        self.summing_result = None
        self.library_rows = []
        self.certificate_rows = []
        self.library_file = None
        self.certificate_file = None
        self.calibration_template = None
        self.last_task = None
        self.data_directory = data_dir
        self._show_data_directory()
        self.refresh_materials()
        if saved_detector is not None:
            try:
                self.detector_form.set_values(saved_detector)
            except Exception:
                pass
        self.refresh_geometry()
        if self.current_mode() == "well":
            self.status.setText("WEFFTRAN (well): experimental, not yet qualified in the laboratory. Verify the results")
            self.log.appendPlainText("[WARN] WEFFTRAN selected. The spatial summing model and the ray boundary patch are not yet qualified in the laboratory; verify all results independently.")
    def data_folder(self, sub=""):
        """A subfolder (Detector, Sample, Calibration…) of the data folder in use (created if needed)."""
        from .paths import get_data_dir
        path = Path(self.data_directory or get_data_dir()) / sub
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            return documents()
        return path
    def _show_data_directory(self):
        """Show the session's data folder in the top bar."""
        from .paths import get_data_dir
        folder = self.data_directory or str(get_data_dir())
        default = Path(folder) == get_data_dir()
        self.data_label.setText("Data folder: "+folder+("" if default else "  (project)"))
        self.data_label.setToolTip(folder+"\n\nYour own materials (Composition, Material) and models are read from and saved here;\n"
                                   "the original EFFTRAN / MEFFTRAN materials are bundled with the program.")
    def _pick_data_folder(self, title):
        """Ask for a data folder; create its Composition and Material subfolders. None when cancelled."""
        from .paths import ensure_data_dir, get_data_dir
        start = self.data_directory or str(get_data_dir())
        filename = QFileDialog.getExistingDirectory(self, title, start if Path(start).is_dir() else str(documents()))
        if not filename:
            return None
        folder = Path(filename)
        if not all((folder/sub).is_dir() for sub in ("Composition", "Material")):
            answer = QMessageBox.question(self, title, f"{folder}\n\nhas no Composition / Material folders yet. Create them?",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if answer != QMessageBox.StandardButton.Yes:
                return None
            try:
                ensure_data_dir(folder)
            except OSError as exc:
                self.error(f"Cannot create the data folder: {exc}")
                return None
        return folder
    def choose_data(self, *unused):
        """Choose the data folder of this session / project (with Material and Composition)."""
        folder = self._pick_data_folder("Data folder for this project")
        if folder is None:
            return
        self.data_directory = str(folder)
        self._show_data_directory()
        self.refresh_materials()
        self.changed()
    def choose_default_data(self, *unused):
        """Choose the default data folder, saved for every next session (and the CLI)."""
        from .paths import data_dir_source, get_data_dir, set_data_dir
        if data_dir_source() == "environment":
            self.error(f"The default data folder is set by the EFFSUITE_DATA environment variable:\n{get_data_dir()}\n\n"
                       "Remove that variable to choose it here.")
            return
        folder = self._pick_data_folder("Default data folder (your own materials and models)")
        if folder is None:
            return
        try:
            set_data_dir(folder)
        except OSError as exc:
            self.error(f"Cannot save the setting: {exc}")
            return
        self.data_directory = str(folder)
        self._show_data_directory()
        self.refresh_materials()
        self.append_log(f"Default data folder set to {folder}")
    def reset_default_data(self, *unused):
        """Go back to the built-in default data folder (<EffSuite root>\\Data)."""
        from .paths import set_data_dir
        try:
            folder = set_data_dir(None)
        except OSError as exc:
            self.error(f"Cannot save the setting: {exc}")
            return
        self.data_directory = str(folder)
        self._show_data_directory()
        self.refresh_materials()
        self.append_log(f"Default data folder reset to {folder}")
    def refresh_materials(self):
        """Fill every material list with the user's and the bundled original materials."""
        folder = Path(self.data_directory) if self.data_directory else None
        sorted_names = material_names(self.data_directory)
        for edit in list(self.detector_form.inputs.values())+list(self.source_form.inputs.values()):
            if isinstance(edit, QComboBox):
                current = edit.currentText()
                edit.blockSignals(True)
                edit.clear()
                edit.addItem("")
                edit.addItems(sorted_names)
                edit.setCurrentText(current)
                edit.blockSignals(False)
        if self.data_directory:
            self.material_editor.library.setText(str(folder))
    def open_material_editor_for_input(self, target_input=None, target_description=None):
        """Show the material editor window (non-modal).

        With ``target_input`` (a material field of a form), the field's material
        is loaded and "Apply" selects the new material in that field. Without
        it, the window opens with its current content and Apply only updates
        the material lists.
        """
        from .materials import load_composition
        editor = self.material_editor
        self._target_material_input = target_input
        editor.set_target(target_description if target_input is not None else None)
        if target_input is not None:
            mat_name = target_input.currentText().strip()
            comp_file = find_material_file(mat_name, "Composition", self.data_directory) if mat_name else None
            if comp_file is not None:
                try:
                    editor.set_definition(load_composition(comp_file))
                    editor.status.setText(f"Loaded '{mat_name}'. Adjust density [g/cm³] or formula, then click \"Apply: create material and XCOM table\".")
                except Exception as exc:
                    editor.status.setText("")
                    editor.error(f"Could not load composition for '{mat_name}': {exc}")
            else:
                editor.clear()
                if mat_name:
                    editor.name.setText(mat_name)
                editor.status.setText(f"Define the composition of '{mat_name or 'new material'}', then click \"Apply: create material and XCOM table\".")
        editor.set_busy(self.thread is not None)
        editor.show()
        editor.raise_()
        editor.activateWindow()
    def material_applied(self, definition, result):
        """A material was created in the editor window: update lists and the target field."""
        name = definition["name"]
        self.data_directory = result["data_directory"]
        self._show_data_directory()
        self.refresh_materials()
        target = self._target_material_input
        if target is not None:
            try:
                target.setCurrentText(name)
                # A source matrix material: show the density just entered, also when
                # the name did not change (an existing material was overwritten).
                for (kind, index), edit in self.source_form.inputs.items():
                    if edit is target and index==5 and (kind, 7) in self.source_form.inputs:
                        self.source_form.inputs[kind, 7].setText(str(float(definition["density_g_cm3"])))
            except RuntimeError:
                pass   # the form was rebuilt meanwhile (geometry change): nothing to select
        self.changed()
        self.status.setText(f"Material '{name}' created and applied.")
        self.append_log("Material saved: "+result["attenuation_file"])
    def new_project(self, *unused):
        """Start a new, empty project (asks first if there are unsaved changes)."""
        if self.dirty and QMessageBox.question(self, "New project", "Discard the current unsaved project?")!=QMessageBox.StandardButton.Yes:
            return
        self.project_path = None
        self.change_mode(keep_detector=False)
        self.dirty = False
        self.tabs.setCurrentIndex(0)
    def error(self, message):
        """Show an error message."""
        QMessageBox.warning(self, "EffSuite", str(message))
    def show_help_dialog(self, topic="workflow", *unused):
        """The built-in user guide."""
        from .paths import get_effsuite_root
        dialog = QDialog(self)
        dialog.setWindowTitle("EffSuite help")
        dialog.resize(820, 620)
        vl = QVBoxLayout(dialog)
        vl.setContentsMargins(14, 12, 14, 12)
        vl.setSpacing(10)
        tabs = QTabWidget()
        gammavision_note = ("<p><b>GammaVision support is untested.</b> ORTEC GammaVision files (<code>.EFT</code> efficiency,"
                            " <code>.LIB</code> nuclide library) are handled as in EFFTRAN and MEFFTRAN, but the author has no"
                            " GammaVision installation to test them. Feedback from GammaVision users is welcome.</p>")
        pre = f"<pre style='background:{theme.WINDOW};padding:8px;'>"
        topics = [
            ("workflow", "Workflow",
             "<h3>Calculation steps</h3>"
             + gammavision_note +
             "<p><b>1. Start</b>: choose the calculation.</p>"
             "<ul>"
             "<li><b>Complete analysis</b> (recommended): efficiency transfer (Standard → Sample) and true coincidence summing corrections in one run. Exports the transferred Sample <code>.CAL</code> (Genie 2000) or <code>.EFT</code> (GammaVision), and the summing-corrected nuclide library (<code>.NLB</code> / <code>.LIB</code>) or Genie certificate (<code>.CTF</code>).</li>"
             "<li><b>Efficiency transfer only</b>: computes the transfer factors <i>F<sub>ε</sub>(E) = ε<sub>sample</sub>(E) / ε<sub>standard</sub>(E)</i> and exports the Sample <code>.CAL</code> or <code>.EFT</code>.</li>"
             "<li><b>True coincidence summing only</b>: computes the cascade summing factors <i>C</i> (<i>A<sub>corr</sub> = C · A</i>) for the Sample geometry. No reference calibration is needed.</li>"
             "</ul>"
             "<p><b>2. Detector</b>: load a detector model (<code>Data/Detector/*.txt</code>) or enter the crystal, dead layer, window and housing dimensions in mm. The cross-section drawing follows the inputs and shows all dimensions.</p>"
             "<p><b>3. Standard &amp; Sample</b> (<b>Sample</b> with coincidence summing only): load or edit the <b>Sample</b> (measured geometry) and the <b>Standard</b> (reference calibration geometry). The Standard is only needed for efficiency transfer; with <b>True coincidence summing only</b> its column is hidden. Enter the apparent <b>Source density [g/cm³]</b> on this page (filled in when you choose a material), or click <b>Edit</b> next to a material to define a new composition.</p>"
             "<p><b>4. Efficiency (.CAL / .EFT), then Library (.NLB / .LIB) or Certificate (.CTF)</b>: import the Genie 2000 (<code>.CAL</code> / <code>.NLB</code> / <code>.CTF</code>) or GammaVision (<code>.EFT</code> / <code>.LIB</code>) reference files, run the calculation and export the corrected files. Each export names its target software, Genie 2000 or GammaVision.</p>"),
            ("materials", "Materials and density",
             "<h3>Material composition and bulk density</h3>"
             "<p>Self-attenuation in gamma-ray spectrometry depends on the <b>chemical composition</b> (mass attenuation coefficient <i>μ/ρ</i>) and on the <b>bulk density</b> <i>ρ</i> [g/cm³] of the sample matrix: <i>μ = (μ/ρ) · ρ</i>.</p>"
             "<ul>"
             "<li><b>Source density</b>: enter the apparent bulk density <i>ρ</i> [g/cm³] in the <b>Source density [g/cm³]</b> field of the Standard &amp; Sample page. No separate material file is needed. The engine scales the linear attenuation coefficient by <i>ρ / ρ<sub>0</sub></i>.</li>"
             "<li><b>XCOM tables</b>: if a material is in <code>Composition/</code> but not in <code>Material/</code>, EffSuite runs NIST XCOM to generate its photon attenuation table before the calculation.</li>"
             "<li><b>New materials</b>: click <b>Edit</b> next to a material, <b>Materials…</b> on the Detector and Standard &amp; Sample pages, or <b>Tools → Material Editor</b>. The Material Editor opens in its own window, so the other pages stay usable. Enter the chemical formulas and the nominal density [g/cm³], then click <b>Apply: create material and XCOM table</b>: the attenuation table is generated and the material appears in the Detector and Standard &amp; Sample material lists. When the editor was opened with <b>Edit</b>, the material is also selected in that field.</li>"
             "<li><b>Formulas</b>: up to 10 compounds (e.g. <code>H2O</code>, <code>C6H12O6</code>, <code>SiO2</code>, <code>CaCO3</code>) with relative weights by mass, normalized to 100%.</li>"
             "</ul>"),
            ("cli", "Command line",
             "<h3>Command line and batch runs</h3>"
             "<p>The GUI calculations can also run from the command line or from batch scripts, with <b>Genie 2000</b> (<code>.CAL</code> / <code>.NLB</code> / <code>.CTF</code>) or <b>GammaVision</b> (<code>.EFT</code> / <code>.LIB</code>) files.</p>"
             "<p>In the installed program run <code>EffSuite_CLI.exe</code> in place of <code>effsuite</code>; in a source checkout use <code>CLI.bat</code>.</p>"
             "<p><b>1a. Genie 2000, one sample, with overrides</b></p>"
             + pre +
             "effsuite cylinder --detector High-energy --standard Solution --sample Water \\\n"
             "  --sample-height 33.4 --sample-material Glucose --sample-density 1.346 \\\n"
             "  --calibration TF400_268_2025.CAL --library LIBRARY.NLB \\\n"
             "  --output-cal Sample_207724.CAL --output-nlb Sample_207724.NLB --plot-geometry"
             "</pre>"
             "<p><b>1b. GammaVision, one sample</b> (<code>.EFT</code> + <code>.LIB</code>, detected from the extension or set with <code>--software gammavision</code>)</p>"
             + pre +
             "effsuite cylinder --detector High-energy --standard Solution --sample Water \\\n"
             "  --calibration EFFTRAN.EFT --library EFFTRAN.Lib \\\n"
             "  --output-cal Sample_transferred.EFT --output-nlb Sample_corrected.LIB"
             "</pre>"
             "<p><b>2. Batch run from a CSV or JSON table</b></p>"
             + pre +
             "# Write a CSV template to fill in:\n"
             "effsuite batch --template my_samples.csv\n\n"
             "# Run every sample in the CSV; writes batch_summary.csv and the .CAL/.EFT and .NLB/.LIB files:\n"
             "effsuite batch my_samples.csv --out BatchResults_2026 --plot-geometry"
             "</pre>"
             "<p><b>3. Geometry drawing only (PNG / PDF / SVG)</b></p>"
             + pre +
             "effsuite plot-geometry --geometry cylinder --detector High-energy --sample Water --out geom.png"
             "</pre>"),
            ("about", "About",
             "<h3>EffSuite: EFFTRAN, MEFFTRAN, WEFFTRAN</h3>"
             f"<p><b>Version:</b> {VERSION} (beta)</p>"
             "<p>EffSuite built by ChatGPT, Gemini and Claude under the supervision of G. Lutter.</p>"
             f"<div style='background:{theme.DANGER_TINT};padding:8px;margin:8px 0;'>"
             f"<b style='color:{theme.DANGER_TEXT};'>Disclaimer:</b><br>"
             f"<span style='color:{theme.TEXT};font-size:9pt;"
             "'>Provided strictly on an AS-IS basis. G. Lutter accepts NO responsibility or liability under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. Users must independently verify all results.</span>"
             "</div>"
             + gammavision_note +
             "<p><b>Physics engines:</b> EFFTRAN 5.0 and MEFFTRAN 1.9 (2026), and WEFFTRAN (2018), by Tim Vidmar (<a href='https://efftran.github.io/'>https://efftran.github.io/</a>), with NIST XCOM photon cross-sections.</p>"
             "<p><b>Additions:</b> coincidence summing factors for all library nuclides in one pass, computed in parallel worker processes; spatial quadrature integration for well detectors.</p>"
             f"<p><b>User folder (data and results):</b> <code>{get_effsuite_root()}</code><br>"
             "Default: <code>C:\\GENIE2K\\EffSuite</code> when Genie 2000 is installed, otherwise <code>Documents\\EffSuite</code>.</p>"
             "<p><b>Qualification:</b> beta version, for evaluation and qualification. When you set up or change a detector or sample model, check the models and transfer factors against reference standards.</p>"
             "<p style='color:"+theme.TEXT_SECONDARY+";font-size:8.5pt;'>EFFTRAN copyright &copy;"
             " 2005–2026 Tim Vidmar. Permission to use, copy, modify, distribute and sell this software and its documentation for any purpose is hereby granted without fee, provided that copyright and permission notices appear in supporting documentation.</p>"),
        ]
        target_idx = 0
        for idx, (key, title, html) in enumerate(topics):
            if key==topic:
                target_idx = idx
            w = QScrollArea()
            w.setWidgetResizable(True)
            lbl = QLabel(html)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft)
            set_role(lbl, "helpText")
            w.setWidget(lbl)
            tabs.addTab(w, title)
        tabs.setCurrentIndex(target_idx)
        vl.addWidget(tabs, 1)
        close_row = QHBoxLayout()
        close_row.addStretch()
        btn = set_role(QPushButton("Close"), "primary")
        btn.setDefault(True)
        btn.clicked.connect(dialog.accept)
        close_row.addWidget(btn)
        vl.addLayout(close_row)
        dialog.exec()
    def load_model(self, kind, *unused):
        """Load a detector, sample or standard model file into the form."""
        folder = {"detector":"Detector", "sample":"Sample", "standard":"Standard"}[kind]
        default_dir = self.data_folder(folder)
        filename, _ = QFileDialog.getOpenFileName(self, "Load "+kind, str(default_dir), "EFFTRAN models (*.txt);;All files (*)")
        if not filename:
            return
        try:
            values = read_model(self.current_mode(), kind, filename)
            if kind=="detector":
                self.detector_form.set_values(values)
            else:
                self.source_form.set_values(kind, values)
                if hasattr(self, "source_diagram"):
                    self.source_diagram.set_kind(kind.title())
            self.changed()
            self.refresh_geometry()
            self.append_log(f"Loaded {kind.title()} model from {Path(filename).name}")
        except Exception as exc:
            self.error(exc)
    def store_model(self, kind, *unused):
        """Save the form of a detector, sample or standard as a model file."""
        folder = {"detector":"Detector", "sample":"Sample", "standard":"Standard"}[kind]
        target_dir = self.data_folder(folder)
        filename, _ = QFileDialog.getSaveFileName(self, "Store "+kind, str(target_dir/(kind+".txt")), "EFFTRAN models (*.txt)")
        if not filename:
            return
        try:
            values = self.detector_form.values() if kind=="detector" else self.source_form.values(kind)
            Path(filename).write_bytes(model_bytes(self.current_mode(), kind, values))
            self.append_log(f"Saved {kind.title()} model to {Path(filename).name}")
        except Exception as exc:
            self.error(exc)
    def calibration(self):
        """The reference calibration points typed in the Efficiency table."""
        rows = []
        for row in range(self.efficiency.rowCount()):
            cells = [self.efficiency.item(row, col).text().strip() if self.efficiency.item(row, col) else "" for col in range(3)]
            if not any(cells):
                continue
            if not cells[0] or not cells[1]:
                raise CoincidenceError(f"Calibration row {row+1} needs energy and efficiency")
            rows.append(dict(zip(("energy_keV", "efficiency",
                                  "u_rel_percent"), (numeric(cells[0]), numeric(cells[1]), numeric(cells[2]) if cells[2] else 0.))))
        return rows
    def collect(self, task="both"):
        """The complete, checked project for a calculation (``task``: transfer, summing, both)."""
        project = {"schema_version":1, "geometry":self.current_mode(),
                   "task":task, "detector":self.detector_form.values(), "sample":self.source_form.values("sample"), "nuclides":normalize_nuclides([self.nuclides.text()]), "workers":self.workers.value()}
        if task in {"transfer", "both"}:
            project.update(standard=self.source_form.values("standard"), calibration=self.calibration())
        if task in {"summing", "both"}:
            project["tcs_uncertainty"] = dict(self.tcs_settings)
        if self.calibration_template:
            project["calibration_template"] = str(self.calibration_template)
        if self.data_directory:
            project["data_directory"] = self.data_directory
        exports = {}
        if task in {"transfer", "both"} and self.calibration_template and Path(self.calibration_template).is_file():
            exports["cal"] = str(self.calibration_template)
        if task in {"summing", "both"}:
            if self.summing_source=="nlb" and self.library_file and Path(self.library_file).is_file():
                exports["nlb"] = str(self.library_file)
                if self.library_rows:
                    project["library_rows"] = [{"nuclide":str(r["nuclide"]), "energy_keV":float(r["energy"])} for r in self.library_rows]
            elif self.summing_source=="ctf" and self.certificate_file and Path(self.certificate_file).is_file():
                exports["ctf"] = str(self.certificate_file)
                if self.certificate_rows:
                    project["library_rows"] = [{"nuclide":str(r["nuclide"]),
                                                "energy_keV":float(r["energy"])} for r in self.certificate_rows]
        if exports:
            project["genie_exports"] = exports
        return validate_project(project)
    def draft(self):
        """The project as it is now, even incomplete (for saving)."""
        task = self.last_task or ("both" if self.calibration() and self.nuclides.text().strip() else "transfer" if self.calibration() else "summing")
        project = {"schema_version":1, "geometry":self.current_mode(),
                   "task":task, "detector":self.detector_form.values(), "sample":self.source_form.values("sample"), "nuclides":normalize_nuclides([self.nuclides.text()]), "workers":self.workers.value(), "calibration":self.calibration(),
                   "tcs_uncertainty":dict(self.tcs_settings)}
        try:
            project["standard"] = self.source_form.values("standard")
        except ValueError:
            pass
        if self.calibration_template:
            project["calibration_template"] = str(self.calibration_template)
        if self.data_directory:
            project["data_directory"] = self.data_directory
        return project
    def apply_project(self, project):
        # Check the essential keys first, so a broken file changes nothing.
        """Fill the whole window from a project (opened file or example)."""
        if project.get("geometry") not in MODES:
            raise CoincidenceError("The project has no valid geometry (cylindrical, marinelli or well)")
        for key in ("detector", "sample"):
            if key not in project:
                raise CoincidenceError(f"The project has no '{key}' section")
        self._loading = True
        try:
            if project.get("task") in ("transfer", "summing", "both"):
                self.workflow = project["task"]
            # Before _build_tabs(), which creates the input boxes from these values.
            self.tcs_settings = tcs_uncertainty.validate_settings(project.get("tcs_uncertainty"))
            index = list(MODES).index(project["geometry"])
            self.mode.blockSignals(True)
            self.mode.setCurrentIndex(index)
            self.mode.blockSignals(False)
            self._build_tabs()
            self.detector_form.set_values(project["detector"])
            self.source_form.set_values("sample", project["sample"])
            if project.get("standard"):
                self.source_form.set_values("standard", project["standard"])
            self.nuclides.setText(", ".join(project.get("nuclides", [])))
            self.workers.setValue(project.get("workers", 0))
            self.set_calibration(project.get("calibration", []))
            self.calibration_template = project.get("calibration_template")
            # Examples and older projects have no data folder: keep the one already chosen.
            self.data_directory = project.get("data_directory") or self.data_directory
            self._show_data_directory()
            self.refresh_materials()
            self.last_task = project.get("task")
        finally:
            # Always leave "loading" mode, even if a value above was invalid;
            # otherwise later edits would no longer clear old results.
            self._loading = False
        self.dirty = False
        self.transfer_result = None
        self.summing_result = None
        self.library_rows = []
        self.certificate_rows = []
        self.library_file = None
        self.certificate_file = None
        self.refresh_geometry()
        self.draw_chart()
    def load_example(self, *unused):
        """Load the built-in example of the selected geometry."""
        from .app_cli import example_path
        name = "cylinder" if self.current_mode()=="cylindrical" else self.current_mode()
        self.apply_project(json.loads(example_path(name).read_text()))
        self.project_path = None
        self.status.setText("Original example loaded. Replace the example models with your laboratory models.")
        self.tabs.setCurrentIndex(1)
        self.append_log(f"Loaded built-in example: {name}")
    def open_project(self, *unused):
        """Open a saved project file (.json)."""
        filename, _ = QFileDialog.getOpenFileName(self, "Open project", str(documents("Projects")), "EffSuite projects (*.json)")
        if filename:
            try:
                self.apply_project(json.loads(Path(filename).read_text()))
                self.project_path = Path(filename)
                self.tabs.setCurrentIndex(1)
                self.append_log(f"Opened project: {Path(filename).name}")
            except Exception as exc:
                self.error(exc)
    def save_project(self, save_as=False, *unused):
        """Save the project (asks for a file name the first time, or with save_as=True)."""
        try:
            project = self.draft()
        except Exception as exc:
            self.error("Load/enter detector and sample models before saving: "+str(exc))
            return
        if save_as or self.project_path is None:
            filename, _ = QFileDialog.getSaveFileName(self, "Save project",
                                                      str(documents("Projects")/"project.effsuite.json"), "EffSuite projects (*.json)")
            if not filename:
                return
            target = Path(filename)
        else:
            target = self.project_path
        try:
            target.write_text(json.dumps(project, indent=2)+"\n")
        except OSError as exc:
            self.error(f"Could not save the project to {target}: {exc}")
            return
        # Remember the file name only once it has really been written.
        self.project_path = target
        self.dirty = False
        self.status.setText("Saved "+str(self.project_path))
        self.append_log(f"Saved project: {self.project_path.name}")
    def set_calibration(self, rows):
        """Fill the Efficiency table with calibration points."""
        self.efficiency.blockSignals(True)
        self.efficiency.clearContents()
        for index, row in enumerate(rows):
            for col, key in enumerate(("energy_keV", "efficiency", "u_rel_percent")):
                self.efficiency.setItem(index, col, _num_item(str(float(row[key])), editable=True))
        self.efficiency.blockSignals(False)
    def import_calibration(self, *unused):
        """Import the reference calibration from .CAL, .EFT, .txt or .csv."""
        filename, _ = QFileDialog.getOpenFileName(self, "Import standard efficiency",
                                                  str(self.data_folder("Calibration")), "Calibration (*.CAL *.cal *.EFT *.eft *.txt *.csv);"
                                                                                                                          ";Genie calibration (*.CAL *.cal);"
                                                                                                                          ";GammaVision efficiency (*.EFT *.eft);;"
                                                                                                                          "Text calibration (*.txt *.csv);;All files (*)")
        if not filename:
            return
        def accepted(rows):
            self.set_calibration(rows)
            self.calibration_template = filename if Path(filename).suffix.lower() in {".cal", ".eft"} else None
            self.changed()
            self.draw_chart()
            self.append_log(f"Imported calibration from {Path(filename).name} ({len(rows)} energy points)")
        self.start_task(lambda log:calibration_rows(filename), accepted)
    def start_task(self, operation, callback, cancellable=False):
        """Run ``operation`` in the background; then call ``callback`` with its result."""
        if self.thread is not None:
            self.status.setText("Another task is still running")
            return
        self._callback = callback
        self.cancel_event = threading.Event()
        self.thread = QThread(self)
        self.worker = TaskWorker(operation)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.show_progress)
        self.worker.succeeded.connect(self.task_result)
        self.worker.failed.connect(self.task_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.task_finished)
        self.tabs.setEnabled(False)
        self.mode.setEnabled(False)
        self.workers.setEnabled(False)
        self.software.setEnabled(False)
        self.data_button.setEnabled(False)
        self.menuBar().setEnabled(False)
        self.cancel_button.setEnabled(cancellable)
        self.material_editor.set_busy(True)
        self.status.setText("Working…")
        self.thread.start()
    def copy_log(self):
        """Copy the log text to the clipboard."""
        text = self.log.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status.setText("Log copied to the clipboard")
    def clear_log(self):
        """Empty the log panel."""
        self.log.clear()
        self.status.setText("Log cleared")
    def append_log(self, message):
        """Add a time-stamped line to the log (keeps scrolling at the bottom)."""
        t = time.strftime("%H:%M:%S")
        sb = self.log.verticalScrollBar()
        at_bottom = (sb.value()>=sb.maximum()-35) if sb else True
        self.log.appendPlainText(f"[{t}] {message}")
        if at_bottom and sb:
            sb.setValue(sb.maximum())
        self.log.ensureCursorVisible()
    @Slot(str)
    def show_progress(self, message):
        """Progress message from the background task."""
        self.status.setText(message)
        self.append_log(message)
    @Slot(object)
    def task_result(self, value):
        """The background task finished: pass its result to the callback."""
        try:
            self._callback(value)
        except Exception as exc:
            self.error(exc)
    @Slot(str)
    def task_error(self, message):
        """The background task failed: show why (quietly for a Cancel)."""
        if message==CANCELLED_MESSAGE:
            # The user pressed Cancel: say so quietly, no warning dialog.
            self.status.setText(message)
            self.append_log(message)
            return
        self.status.setText("Calculation stopped: "+message)
        self.append_log("Error: "+message)
        self.error(message)
    @Slot()
    def task_finished(self):
        """Re-enable the window after a background task."""
        self.thread = None
        self.worker = None
        self.tabs.setEnabled(True)
        self.mode.setEnabled(True)
        self.workers.setEnabled(True)
        self.software.setEnabled(True)
        self.data_button.setEnabled(True)
        self.menuBar().setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.material_editor.set_busy(False)
    def calculate(self, task, *unused):
        """Run a calculation (transfer, summing or both) in the background."""
        try:
            project = self.collect(task)
        except Exception as exc:
            self.error(exc)
            return
        self.last_task = task
        task_label = "complete analysis (transfer and summing)" if task == "both" else ("efficiency transfer" if task == "transfer" else "coincidence summing")
        self.append_log(f"Starting {task_label}, {self.current_mode()} geometry…")
        try:
            recovery = documents("Recovery")/"last_project.json"
            temporary = recovery.with_suffix(".tmp")
            temporary.write_text(json.dumps(project, indent=2))
            temporary.replace(recovery)
        except OSError as exc:
            self.append_log("Could not save the recovery snapshot: "+str(exc))
        from .app_cli import default_output
        output = default_output()
        stop = self.cancel_event = threading.Event()
        # start_task creates the active event before the worker closure is called.
        self.start_task(lambda log:run_project(project, output,
                                               cancel=self.cancel_event, progress=log), self.accept_result, cancellable=True)
    def accept_result(self, result):
        """Show a finished calculation in the tables, chart and log."""
        self._loading = True
        self._tcs_note_shown = False
        if result["efficiency"]:
            self.transfer_result = result
            for i, row in enumerate(result["efficiency"]):
                for col, key, bold in [(3, "sample_efficiency",
                                        True), (4, "sample_relative_uncertainty_percent_legacy", False), (5, "transfer_factor", True)]:
                    item = _num_item(format(row[key], ".6g"), editable=False, bold=bold, bg=theme.ACCENT_TINT, fg=theme.TEXT)
                    self.efficiency.setItem(i, col, item)
            self.draw_chart()
        if result["summing"]:
            self.summing_result = result
            self.populate_summing()
        if result["efficiency"] and not result["summing"]:
            self.tabs.setCurrentIndex(3)
        elif result["summing"]:
            self.tabs.setCurrentIndex(self.tab_index(self.summing_source))
        self._loading = False
        self.status.setText("Completed: "+result["output_directory"])
        self.append_log("Saved "+result["output_directory"])
        for warning in result["warnings"]:
            self.append_log(warning)
        try:
            (documents("Recovery")/"last_project.json").write_text(json.dumps(result["project"], indent=2))
        except OSError:
            pass
        if result.get("efficiency") and result.get("summing"):
            self.show_complete_analysis_summary(result)
    def show_complete_analysis_summary(self, result):
        """Dialog listing the two exports of a complete analysis."""
        if QApplication.platformName()=="offscreen":
            return
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle("Complete analysis: exports")
        dialog.setMinimumWidth(720)
        vl = QVBoxLayout(dialog)
        vl.setSpacing(12)
        vl.setContentsMargins(16, 16, 16, 16)
        banner = QFrame()
        banner.setProperty("notice", "success")
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(4)
        t = QLabel("<b>Complete analysis finished</b>")
        t.setStyleSheet(f"font-size:12pt;color:{theme.SUCCESS_TEXT};")
        d = QLabel("Both output files are calculated and ready to export.")
        d.setStyleSheet(f"color:{theme.TEXT};")
        bl.addWidget(t)
        bl.addWidget(d)
        vl.addWidget(banner)
        box = QGroupBox("Exports")
        fl = QVBoxLayout(box)
        fl.setSpacing(10)
        cal_is_gv = Path(self.calibration_template or "").suffix.lower()==".eft" or os.environ.get("EFFSUITE_SOFTWARE",
                                                                                                   "").strip().lower()=="gammavision"
        cal_sw = "GammaVision" if cal_is_gv else "Genie 2000"
        cal_ext = ".EFT" if cal_is_gv else ".CAL"
        row1 = QHBoxLayout()
        info1 = QLabel(f"<b>1. Sample efficiency ({cal_sw} {cal_ext})</b><br><span style='color:{theme.TEXT_SECONDARY};font-size:9pt;'>Transferred efficiency calibration for the sample geometry</span>")
        btn1 = with_icon(set_role(QPushButton(f"Export sample {cal_ext} ({cal_sw})…"), "tinted"), SAVE)
        btn1.clicked.connect(self.export_calibration)
        info1.setWordWrap(True)
        row1.addWidget(info1, 1)
        row1.addWidget(btn1)
        fl.addLayout(row1)
        sep = set_role(QFrame(), "hseparator")
        fl.addWidget(sep)
        row2 = QHBoxLayout()
        sum_src = self.library_file if self.summing_source=="nlb" else self.certificate_file
        lib_is_gv = (self.summing_source=="nlb" and (Path(sum_src or "").suffix.lower()==".lib" or os.environ.get("EFFSUITE_SOFTWARE",
                                                                                                                  "").strip().lower()=="gammavision"))
        lib_sw = "GammaVision" if lib_is_gv else "Genie 2000"
        lib_ext = ".LIB" if lib_is_gv else (".NLB" if self.summing_source=="nlb" else ".CTF")
        kind_name = f"nuclide library ({lib_sw} {lib_ext})" if self.summing_source=="nlb" else "certificate (Genie 2000 .CTF)"
        desc_sum = "Yields P / C corrected for cascade coincidence summing" if self.summing_source=="nlb" else "Emission rates R / C corrected for cascade coincidence summing"
        info2 = QLabel(f"<b>2. Corrected {kind_name}</b><br><span style='color:{theme.TEXT_SECONDARY};font-size:9pt;'>{desc_sum}</span>")
        btn2 = with_icon(set_role(QPushButton(f"Export corrected {lib_ext} ({lib_sw})…"), "tinted"), SAVE)
        btn2.clicked.connect(lambda:self.export_genie(self.summing_source))
        info2.setWordWrap(True)
        row2.addWidget(info2, 1)
        row2.addWidget(btn2)
        fl.addLayout(row2)
        vl.addWidget(box)
        dest = result.get("output_directory", "")
        if dest:
            note = QLabel(f"<b>Result folder:</b> <span style='font-family:Consolas,monospace;font-size:9pt;'>{dest}</span>")
            note.setWordWrap(True)
            note.setProperty("notice", "neutral")
            note.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            vl.addWidget(note)
        actions = QHBoxLayout()
        btn_open = with_icon(QPushButton("Open result folder"), FOLDER)
        btn_open.clicked.connect(self.open_results)
        btn_close = set_role(QPushButton("Close"), "primary")
        btn_close.setDefault(True)
        btn_close.clicked.connect(dialog.accept)
        actions.addWidget(btn_open)
        actions.addStretch()
        actions.addWidget(btn_close)
        vl.addLayout(actions)
        _fit_dialog(dialog)
        dialog.show()
    def draw_chart(self):
        """Efficiency chart: standard calibration and transferred sample efficiency."""
        if self.chart is None:
            return
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        try:
            rows = self.calibration()
        except Exception:
            rows = []
        if rows:
            axes.loglog([r["energy_keV"] for r in rows], [r["efficiency"] for r in rows],
                        "o-", label="Standard (reference)", color=theme.CHART_STANDARD, markersize=4, linewidth=1.4)
        if self.transfer_result:
            rows = self.transfer_result["efficiency"]
            axes.loglog([r["energy_keV"] for r in rows], [r["sample_efficiency"] for r in rows],
                        "s-", label="Sample (transferred)", color=theme.CHART_SAMPLE, markersize=4, linewidth=1.4)
        axes.set_xlabel("Energy [keV]", fontsize=9.5)
        axes.set_ylabel("Full-energy efficiency ε", fontsize=9.5)
        axes.grid(True, which="both", alpha=theme.CHART_GRID_ALPHA, color=theme.TEXT_SECONDARY, linewidth=.6)
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axes.spines[side].set_color(theme.SEPARATOR)
        axes.tick_params(colors=theme.TEXT_SECONDARY, labelsize=8.5)
        axes.xaxis.label.set_color(theme.TEXT_SECONDARY)
        axes.yaxis.label.set_color(theme.TEXT_SECONDARY)
        if axes.lines:
            axes.legend(fontsize=9, frameon=False)
        self.chart.draw_idle()
    def import_genie(self, kind, *unused):
        """Open a nuclide library (.NLB/.LIB) or a certificate (.CTF)."""
        folder = "NuclideLibrary" if kind=="nlb" else "Certificates"
        camfiles = Path("C:/GENIE2K/CAMFILES")
        default_dir = camfiles if (kind == "nlb" and camfiles.is_dir()) else self.data_folder(folder)
        filename, _ = QFileDialog.getOpenFileName(self, "Open Genie / GammaVision file",
                                                  str(default_dir), "Genie / GammaVision files (*."+kind.upper()+" *."+kind+(" *.LIB *.lib" if kind=="nlb" else "")+")")
        if not filename:
            return
        from .software import read_library, read_certificate
        def accepted(rows):
            # Results calculated for the previous file no longer apply.
            self.summing_result = None
            if kind=="nlb":
                self.library_file = filename
                self.library_rows = rows
            else:
                self.certificate_file = filename
                self.certificate_rows = rows
            self.nuclides.setText(", ".join(dict.fromkeys(str(r["nuclide"]) for r in rows)))
            self.summing_source = kind
            self.populate_summing()
            self.apply_workflow()
            self.status.setText("Loaded "+filename+". Next: "+("click "+self.RUN_LABELS[self.workflow] if self.workflow!="transfer" else "continue"))
        self.start_task(lambda log:(read_library if kind=="nlb" else read_certificate)(filename), accepted)
    def process_genie(self, kind, *unused):
        """Run the summing calculation for the lines of the loaded file."""
        rows = self.library_rows if kind=="nlb" else self.certificate_rows
        if rows:
            self.nuclides.setText(", ".join(dict.fromkeys(str(r["nuclide"]) for r in rows)))
        self.calculate("summing")
    def populate_summing(self):
        """Fill the library and certificate tables (factor, or * when not corrected)."""
        from .software import match_factor
        for table, records in [(self.library_table, self.library_rows), (self.certificate_table, self.certificate_rows)]:
            rows = records if records else ([dict(nuclide=r["nuclide"],
                                                  energy=r["energy_keV"]) for r in self.summing_result["summing"]] if self.summing_result else [])
            table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                factor = None
                reason = "Not calculated"
                if self.summing_result:
                    try:
                        factor = match_factor(self.summing_result, row["nuclide"], float(row["energy"]))
                        reason = ""
                    except Exception as exc:
                        reason = str(exc)
                nuc_item = _num_item(row["nuclide"], editable=False,
                                     bold=True, align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter, tooltip=reason)
                eng_item = _num_item(format(float(row["energy"]),
                                            ".2f"), editable=False, align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter, tooltip=reason)
                fac_str = format(factor, ".6f") if factor is not None else ""
                fac_item = _num_item(fac_str, editable=False,
                                     bold=(factor is not None), bg=theme.ACCENT_TINT if factor is not None else None, fg=theme.TEXT if factor is not None else None, align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter, tooltip=reason)
                u_value = (tcs_uncertainty.match_uncertainty(self.summing_result, row["nuclide"], float(row["energy"]),
                                                             self.tcs_settings)
                           if factor is not None and self.summing_result else None)
                u_item = _num_item(format(u_value, ".3g") if u_value is not None else "", editable=False,
                                   align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,
                                   tooltip="Relative standard uncertainty of C (k=1), decay data not included")
                ast_item = _num_item("*" if factor is None else "",
                                     editable=False, bold=True, fg=theme.WARNING if factor is None else None, align=Qt.AlignmentFlag.AlignCenter, tooltip=reason)
                table.setItem(i, 0, nuc_item)
                table.setItem(i, 1, eng_item)
                table.setItem(i, 2, fac_item)
                table.setItem(i, 3, u_item)
                table.setItem(i, 4, ast_item)
    def _ask_new_export_path(self, title, default_path, extension, description, allow_csv=False):
        """Ask where to save an export. Only the file's real format is offered.

        Returns the chosen path, or None when the user cancels. Existing files
        are refused (exports never overwrite a file).
        """
        filters = f"{description} (*{extension})"+(";;CSV (*.csv)" if allow_csv else "")
        # We check for existing files ourselves: Qt's "Replace?" question would
        # be misleading because the export never overwrites a file.
        filename, _ = QFileDialog.getSaveFileName(self, title, default_path, filters, options=QFileDialog.Option.DontConfirmOverwrite)
        if not filename:
            return None
        path = Path(filename)
        if path.suffix.lower() not in {extension.lower(), ".csv" if allow_csv else extension.lower()}:
            path = path.with_suffix(extension)
        if path.exists():
            self.error(f"{path.name} already exists. Choose a new file name; exports never overwrite a file.")
            return None
        return path
    def _copy_verified(self, result, kind, path):
        """Copy the corrected file that the calculation already exported and checked."""
        from .software import copy_verified_export
        try:
            copy_verified_export(result, kind, path)
        except (CoincidenceError, OSError) as exc:
            self.error(exc)
            return
        self.status.setText(f"Exported {path.name}")
        self.append_log(f"Exported {path}")
    def export_calibration(self, *unused):
        """Save the transferred sample calibration (.CAL, .EFT or .csv)."""
        if not self.transfer_result:
            self.error("Calculate efficiency transfer first.")
            return
        default_dir = documents("Export")
        default_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(self.calibration_template).stem if self.calibration_template else "sample_efficiency"
        verified = (self.transfer_result.get("genie_exports") or {}).get("cal")
        # The format follows the template file (.CAL = Genie 2000, .EFT = GammaVision).
        if verified:
            extension = Path(verified["file"]).suffix.upper()
        else:
            extension = ".EFT" if Path(self.calibration_template or "").suffix.lower()==".eft" else ".CAL"
        description = "GammaVision efficiency" if extension==".EFT" else "Genie 2000 calibration"
        path = self._ask_new_export_path(f"Export sample efficiency calibration ({description})",
                                         str(default_dir/(stem+"_sample"+extension)), extension, description, allow_csv=True)
        if path is None:
            return
        if path.suffix.lower()==".csv":
            import csv
            try:
                with open(path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["energy_keV", "efficiency", "u_rel_percent"])
                    for row in self.transfer_result["efficiency"]:
                        writer.writerow([row["energy_keV"], row["sample_efficiency"], row["sample_relative_uncertainty_percent_legacy"]])
            except OSError as exc:
                self.error(f"Could not write {path.name}: {exc}")
                return
            self.status.setText("Exported "+str(path))
            return
        if verified:
            self._copy_verified(self.transfer_result, "cal", path)
            return
        # No template was loaded before the calculation: export now from a template the user picks.
        source, _ = QFileDialog.getOpenFileName(self, "Choose a CAL/EFT template with the same point count",
                                                str(self.data_folder("Calibration")), f"{description} (*{extension})")
        if not source:
            return
        from .software import export_copy, label
        self.start_task(lambda log:export_copy(source, path,
                                               self.transfer_result, "cal"), lambda r:self.status.setText(f"{label(source)} calibration exported to {path.name}"))
    def export_genie(self, kind, *unused):
        """Save the corrected library or certificate (copy of the verified export)."""
        source = self.library_file if kind=="nlb" else self.certificate_file
        if not source or not self.summing_result:
            self.error("Open the source Genie/GammaVision file and calculate its nuclides first.")
            return
        verified = (self.summing_result.get("genie_exports") or {}).get(kind)
        if not verified:
            self.error("The calculation did not produce a corrected file. Check the warnings in the log, then calculate again.")
            return
        extension = Path(verified["file"]).suffix.upper()
        description = {".LIB":"GammaVision Library", ".NLB":"Genie 2000 Library",
                       ".CTF":"Genie 2000 Certificate"}.get(extension, "Corrected file")
        default_dir = documents("Export")
        default_dir.mkdir(parents=True, exist_ok=True)
        path = self._ask_new_export_path(f"Export corrected {description} ({extension})",
                                         str(default_dir/(Path(source).stem+"_corrected"+extension)), extension, description)
        if path is not None:
            self._copy_verified(self.summing_result, kind, path)
    # Software update. The check and the download run in daemon threads (not
    # self.thread, which means "calculation running") and report through
    # UpdateSignals, so the window never waits on the network.
    def _set_auto_update_check(self, enabled):
        from .paths import load_settings, save_settings
        settings = load_settings()
        settings[updater.SETTING_AUTO] = bool(enabled)
        try:
            save_settings(settings)
        except OSError as exc:
            self.append_log(f"[WARN] Could not save settings: {exc}")

    def auto_check_for_updates(self):
        """Check GitHub once a day at startup, unless turned off in the Help menu."""
        from .paths import load_settings
        if updater.should_check_automatically(load_settings()):
            self.check_for_updates(manual=False)

    def check_for_updates(self, manual=True):
        """Ask GitHub for the newest release in the background."""
        if self._update_busy:
            return
        self._update_busy = True
        if manual:
            self.status.setText("Checking GitHub for updates…")
        signals = self.update_signals
        def run():
            try:
                result, error = updater.check_for_update(), None
            except updater.UpdateError as exc:
                result, error = None, str(exc)
            except Exception as exc:
                result, error = None, f"Update check failed: {exc}"
            try:
                if error is None:
                    signals.checked.emit(result, manual)
                else:
                    signals.check_failed.emit(error, manual)
            except RuntimeError:
                pass   # window already closed
        threading.Thread(target=run, name="update-check", daemon=True).start()

    def _update_checked(self, release, manual):
        from .paths import load_settings, save_settings
        self._update_busy = False
        settings = load_settings()
        settings[updater.SETTING_LAST] = time.time()
        try:
            save_settings(settings)
        except OSError:
            pass
        if release is None:
            if manual:
                self.status.setText(f"EffSuite {VERSION} is the latest version")
                QMessageBox.information(self, "Software update", f"EffSuite {VERSION} is the latest version.")
            return
        if not manual and settings.get(updater.SETTING_SKIPPED) == release.version:
            return
        self.append_log(f"[INFO] EffSuite {release.version} is available (installed: {VERSION}). Help > Check for updates")
        if manual:
            self.status.setText(f"EffSuite {release.version} is available")
            self.show_update_dialog(release)
        else:
            self._pending_release = release
            self._offer_pending_update()

    def _offer_pending_update(self):
        """Show the startup update offer once no dialog is open and no calculation runs."""
        if self._pending_release is None:
            return
        if QApplication.activeModalWidget() is not None or self.thread is not None:
            QTimer.singleShot(5000, self._offer_pending_update)
            return
        release, self._pending_release = self._pending_release, None
        self.show_update_dialog(release)

    def _update_check_failed(self, message, manual):
        self._update_busy = False
        if manual:
            self.status.setText("Update check failed")
            QMessageBox.warning(self, "Software update", f"{message}\n\nReleases: {updater.RELEASES_PAGE}")

    def show_update_dialog(self, release):
        """Release notes of a newer version, with install / later / skip choices."""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        dialog = QDialog(self)
        dialog.setWindowTitle("Software update")
        dialog.setMinimumSize(600, 440)
        vl = QVBoxLayout(dialog)
        vl.setContentsMargins(18, 16, 18, 16)
        vl.setSpacing(10)
        title = QLabel(f"<b>EffSuite {release.version}</b> is available. Installed version: {VERSION}.")
        title.setStyleSheet("font-size:12pt;")
        title.setWordWrap(True)
        vl.addWidget(title)
        if not updater.can_install():
            note = QLabel("This copy runs from source: update it with git, or download the installer from the release page.")
            note.setWordWrap(True)
            set_role(note, "secondary")
            vl.addWidget(note)
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(release.notes.strip() or "No release notes.")
        vl.addWidget(notes, 1)
        row = QHBoxLayout()
        skip = QPushButton("Skip this version")
        later = QPushButton("Remind me later")
        main = set_role(QPushButton("Download and install" if updater.can_install() else "Open release page"), "primary")
        main.setDefault(True)
        row.addWidget(skip)
        row.addStretch(1)
        row.addWidget(later)
        row.addWidget(main)
        vl.addLayout(row)
        choice = []
        for button, name in ((skip, "skip"), (later, "later"), (main, "install")):
            button.clicked.connect(lambda checked=False, n=name: (choice.append(n), dialog.accept()))
        dialog.exec()
        if choice == ["skip"]:
            from .paths import load_settings, save_settings
            settings = load_settings()
            settings[updater.SETTING_SKIPPED] = release.version
            try:
                save_settings(settings)
            except OSError:
                pass
            self.append_log(f"[INFO] EffSuite {release.version} skipped; Help > Check for updates still offers it")
        elif choice == ["install"]:
            if updater.can_install():
                self.download_update(release)
            else:
                QDesktopServices.openUrl(QUrl(release.page_url))

    def download_update(self, release):
        """Download the installer with a progress dialog; install when it is verified."""
        if self.thread is not None:
            QMessageBox.information(self, "Software update", "A calculation is running. Install the update when it has finished.")
            return
        progress = QProgressDialog(f"Downloading {release.asset_name}…", "Cancel", 0, 100, self)
        progress.setWindowTitle("Software update")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumWidth(420)
        cancel = threading.Event()
        self._download_cancel = cancel
        progress.canceled.connect(cancel.set)
        self._download_dialog = progress
        progress.show()
        signals = self.update_signals
        def emit(signal, *values):
            try:
                signal.emit(*values)
            except RuntimeError:
                pass   # window already closed
        def run():
            try:
                path = updater.download_installer(release, progress=lambda done, total: emit(signals.progress, done, total), cancel=cancel)
                emit(signals.downloaded, path)
            except updater.UpdateError as exc:
                emit(signals.download_failed, str(exc))
            except Exception as exc:
                emit(signals.download_failed, f"Download failed: {exc}")
        threading.Thread(target=run, name="update-download", daemon=True).start()

    def _close_download_dialog(self):
        if self._download_dialog is not None:
            self._download_dialog.close()
            self._download_dialog.deleteLater()
            self._download_dialog = None

    def _update_progress(self, received, total):
        dialog = self._download_dialog
        if dialog is None or not total:
            return
        dialog.setValue(min(100, int(received * 100 / total)))
        dialog.setLabelText(f"Downloading… {received / 1e6:.1f} of {total / 1e6:.1f} MB")

    def _update_download_failed(self, message):
        self._close_download_dialog()
        if message != "Download cancelled.":
            QMessageBox.warning(self, "Software update", f"{message}\n\nReleases: {updater.RELEASES_PAGE}")

    def _update_downloaded(self, path):
        """Close EffSuite (unsaved-project prompt included), then start the installer."""
        self._close_download_dialog()
        if self._download_cancel is not None and self._download_cancel.is_set():
            return   # Cancel pressed while the last chunk arrived
        writable = updater.install_folder_writable()
        detail = ("EffSuite restarts when the installation is finished." if writable else
                  "The installation folder needs administrator rights: Windows will ask for permission.")
        if QMessageBox.question(self, "Software update",
                                f"EffSuite will close to install the update.\n{detail}\n\nContinue?") != QMessageBox.StandardButton.Yes:
            self.append_log(f"[INFO] Installer saved: {path}")
            return
        if self.thread is not None:
            QMessageBox.information(self, "Software update", f"A calculation is running. The installer is saved in:\n{path}")
            return
        # Close first: closeEvent may still be refused (unsaved project). Starting
        # the installer before that would let it close EffSuite under the user.
        if not self.close():
            self.append_log(f"[INFO] Installer saved: {path}")
            return
        try:
            updater.launch_installer(path, writable)
        except OSError as exc:
            QMessageBox.critical(None, "Software update", f"Could not start the installer: {exc}\n{path}")
        QApplication.quit()

    def open_results(self, *unused):
        """Open the results folder in Windows Explorer."""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        result = self.summing_result or self.transfer_result
        QDesktopServices.openUrl(QUrl.fromLocalFile(result["output_directory"] if result else str(documents("Results"))))
    def closeEvent(self, event):
        """Closing the window: stop a running task first; ask about unsaved changes."""
        if self.thread is not None:
            self.cancel_event.set()
            self.status.setText("Stopping the calculation before closing…")
            event.ignore()
            return
        if self.dirty and QMessageBox.question(self, "Close EffSuite",
                                               "Close without saving this project?")!=QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        self.material_editor.close()   # a separate window: it would keep the application running
        event.accept()


def main():
    """Start the graphical program."""
    import sys
    multiprocessing.freeze_support()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GL.EffSuite.GammaSuite.0.1")
        except Exception:
            pass
    app = QApplication.instance() or QApplication([])
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(get_app_icon())
    window = MainWindow()
    window.show()
    # Started from main(), not MainWindow.__init__, so tests never reach the network.
    QTimer.singleShot(3000, window.auto_check_for_updates)
    return app.exec()


if __name__=="__main__":
    raise SystemExit(main())
