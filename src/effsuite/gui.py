"""EFFTRAN-style desktop: original tabs and forms, shared executable workflows."""
from __future__ import annotations
from functools import partial
import json
import math
import multiprocessing
from pathlib import Path
import threading
import time

from PySide6.QtCore import QObject,QThread,Signal,Slot,Qt,QTimer,QRectF,QRect,QSize,QPointF
from PySide6.QtGui import QAction,QFont,QPainter,QPen,QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,
 QFormLayout,QGroupBox,QLabel,QLineEdit,QComboBox,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,
 QHeaderView,QFileDialog,QMessageBox,QPlainTextEdit,QSpinBox,QSplitter,QScrollArea,QCheckBox,QStyledItemDelegate,QFrame,QRadioButton,QButtonGroup,QDialog,QSizePolicy,QListView)

from .model_io import ASSETS,COMMON_DATA,MODES,fields,read_model,model_bytes,calibration_rows,normalize_nuclides
from .suite import VERSION,run_project,validate_project
from .parallel_coincidence import CoincidenceError

APP_STYLESHEET = """
QWidget {
    color: #172b4d;
    selection-background-color: #245c96;
    selection-color: #ffffff;
    font-family: "Segoe UI", -apple-system, system-ui, sans-serif;
    font-size: 10pt;
}
QWidget:disabled {
    color: #59677a;
}
QMainWindow, QDialog {
    background: #eef0f3;
    color: #172b4d;
}
QLabel, QCheckBox, QRadioButton, QGroupBox {
    color: #172b4d;
}
QMenuBar {
    background: #eef0f3;
    color: #172b4d;
}
QMenuBar::item:selected {
    background: #d8e8fc;
    color: #123a63;
}
QMenu {
    background: #ffffff;
    color: #172b4d;
    border: 1px solid #bac4d0;
}
QMenu::item:selected {
    background: #d8e8fc;
    color: #123a63;
}
QMenu::item:disabled {
    color: #59677a;
}
QToolBar {
    background: #f2f3f5;
    color: #172b4d;
    spacing: 7px;
    padding: 6px;
    border-bottom: 1px solid #bec5cf;
}
QToolButton {
    background: transparent;
    color: #172b4d;
    padding: 4px;
}
QToolButton:hover, QToolButton:pressed {
    background: #d8e8fc;
    color: #123a63;
}
QToolButton:disabled {
    color: #59677a;
}
QTabWidget::pane {
    border: 1px solid #b9c1cc;
    background: #ffffff;
    color: #172b4d;
}
QTabBar::tab {
    padding: 7px 18px;
    background: #e5e8ed;
    color: #172b4d;
    border: 1px solid #bbc3cd;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: 500;
}
QTabBar::tab:hover {
    background: #edf4fc;
    color: #163e6b;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #163e6b;
    border-bottom: 2px solid #245c96;
    font-weight: 600;
}
QTabBar::tab:disabled {
    color: #59677a;
}
QHeaderView::section {
    background: #e9edf2;
    color: #172b4d;
    padding: 6px;
    border: 1px solid #c9cfd7;
    font-weight: 600;
}
QAbstractItemView {
    background: #ffffff;
    color: #172b4d;
    alternate-background-color: #f4f7fb;
}
QAbstractItemView::item:selected {
    background: #245c96;
    color: #ffffff;
}
QTableWidget {
    background: #ffffff;
    color: #172b4d;
    alternate-background-color: #f4f7fb;
    gridline-color: #dbe1e8;
}
QScrollArea, QScrollArea > QWidget > QWidget {
    background: #ffffff;
    border: none;
}
QScrollBar:vertical {
    background: #f1f3f6;
    width: 10px;
    margin: 0px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #b8c2cf;
    border-radius: 5px;
    min-height: 28px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #8fa0b5;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: #f1f3f6;
    height: 10px;
    margin: 0px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #b8c2cf;
    border-radius: 5px;
    min-width: 28px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #8fa0b5;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QGroupBox {
    background-color: #ffffff;
    font-weight: 600;
    font-size: 10pt;
    color: #172b4d;
    border: 1px solid #c0c8d4;
    border-radius: 4px;
    margin-top: 10px;
    padding: 12px 12px 8px 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    background-color: #ffffff;
    color: #172b4d;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    color: #172b4d;
    border: 1px solid #aeb9c7;
    border-radius: 3px;
    padding: 3px 6px;
    selection-background-color: #245c96;
    selection-color: #ffffff;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {
    border-color: #7fa4cf;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1.5px solid #245c96;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: #e7ecf2;
    color: #59677a;
}
QComboBox QAbstractItemView, QListView {
    background-color: #ffffff;
    color: #172b4d;
    selection-background-color: #245c96;
    selection-color: #ffffff;
}
QListView::item {
    padding: 3px 6px;
    background-color: #ffffff;
    color: #172b4d;
}
QListView::item:hover {
    background-color: #dbeafe;
    color: #1e40af;
}
QListView::item:selected {
    background-color: #245c96;
    color: #ffffff;
}
QPushButton {
    background-color: #e9edf2;
    color: #172b4d;
    border: 1px solid #aeb9c7;
    border-radius: 3px;
    padding: 5px 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #d8e8fc;
    color: #123a63;
    border-color: #7fa4cf;
}
QPushButton:pressed {
    background-color: #c5d9f0;
    color: #123a63;
}
QPushButton:disabled {
    background-color: #e7ecf2;
    color: #59677a;
}
QPlainTextEdit {
    background-color: #0f172a;
    color: #38bdf8;
    border: 1px solid #334155;
    border-radius: 3px;
    padding: 6px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9.5pt;
}
QSplitter::handle:vertical {
    background-color: #c0c8d4;
    height: 5px;
    margin: 1px 0;
}
QSplitter::handle:vertical:hover {
    background-color: #245c96;
}
QStatusBar {
    background: #eef0f3;
    color: #172b4d;
}
QRadioButton {
    spacing: 10px;
    font-size: 9.75pt;
    font-weight: 600;
    background: transparent;
    color: #172b4d;
    min-height: 22px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 9px;
    border: 1.5px solid #8c9ba5;
    background: #ffffff;
}
QRadioButton::indicator:hover {
    border-color: #245c96;
}
QRadioButton::indicator:checked {
    border: 2px solid #245c96;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #245c96, stop:0.55 #245c96, stop:0.6 #ffffff, stop:1 #ffffff);
}
QCheckBox {
    spacing: 8px;
    background: transparent;
    color: #172b4d;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1.5px solid #8c9ba5;
    background: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #245c96;
}
"""


class PaintedRadio(QRadioButton):
    """Custom-painted radio button whose indicator dot is always visible regardless of OS theme or DPI."""
    INDICATOR_D = 16

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        f = self.font()
        f.setBold(True)
        self.setFont(f)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(self.INDICATOR_D + 10 + fm.horizontalAdvance(self.text()) + 8, max(self.INDICATOR_D + 6, fm.height() + 6))

    def minimumSizeHint(self):
        fm = self.fontMetrics()
        return QSize(self.INDICATOR_D + 60, max(self.INDICATOR_D + 6, fm.height() + 6))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        d = self.INDICATOR_D
        center = QPointF(2 + d / 2.0, h / 2.0)
        enabled = self.isEnabled()
        blue = QColor("#245c96") if enabled else QColor("#94a3b8")
        ring = blue if (self.isChecked() or (self.underMouse() and enabled)) else (QColor("#8c9ba5") if enabled else QColor("#cbd5e1"))
        p.setPen(QPen(ring, 1.6))
        p.setBrush(QColor("#ffffff") if enabled else QColor("#f1f5f9"))
        p.drawEllipse(center, d / 2.0 - 1.0, d / 2.0 - 1.0)
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(blue)
            p.drawEllipse(center, 4.2, 4.2)
        if self.hasFocus():
            p.setPen(QPen(QColor("#7fa4cf"), 1, Qt.PenStyle.DotLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRect(d + 8, 1, max(10, self.width() - d - 10), h - 2))
        p.setPen(QColor("#172b4d") if enabled else QColor("#94a3b8"))
        p.setFont(self.font())
        p.drawText(QRect(d + 10, 0, max(10, self.width() - d - 10), h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


def documents(folder=""):
    from .paths import get_effsuite_root
    path = get_effsuite_root() / folder if folder else get_effsuite_root()
    path.mkdir(parents=True, exist_ok=True)
    return path


def numeric(text):
    text=str(text).strip()
    if "," in text and "." not in text:text=text.replace(",",".")
    value=float(text)
    if not math.isfinite(value):raise ValueError("Enter a finite number")
    return value


class NumberEdit(QLineEdit):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
    def value(self):return numeric(self.text())


SHORT_LABELS={
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


def _field_label(label,unit):
    short=SHORT_LABELS.get(label,label)
    if unit=="mm":
        lbl=QLabel(f"{short} <span style='color:#64748b;font-size:9pt;'>[mm]</span>")
    else:
        lbl=QLabel(short)
    lbl.setToolTip(f"{label} ({unit})")
    lbl.setStyleSheet("background:transparent;color:#334155;")
    return lbl


def form_value(edit,label,unit):
    if unit=="material":
        value=edit.currentText().strip()
        if not value:raise ValueError(label+": choose a material")
        return value
    try:return edit.value()
    except ValueError as exc:raise ValueError(label+": enter a finite number in mm") from exc


class ModelForm(QWidget):
    changed=Signal()
    def __init__(self,mode,kind,owner=None,parent=None):
        super().__init__(parent);self.mode=mode;self.kind=kind;self.owner=owner;self.inputs={}
        grid=QGridLayout(self);grid.setHorizontalSpacing(14);grid.setVerticalSpacing(8);grid.setContentsMargins(2,2,2,2)
        materials=sorted(p.stem for p in (COMMON_DATA/"Composition").glob('*.txt'))
        def_fields = fields(mode, kind, extended=True)
        if kind=="detector":
            if mode=="well":
                groups=[("Crystal and well (Standard)",[0,1,3,4,2,5,6]),
                        ("Holder and dead layers (Optional)",[7,8,9,10,11])]
            elif mode=="marinelli":groups=[("Crystal",[2,3,11,4,5,9,8,12]),("Housing, window and holder",[0,1,14,6,7,13,10,15])]
            else:groups=[("Crystal",[2,3,11,4,5,9,8,14]),("Housing, window, holder and absorber",[0,1,16,6,7,15,10,17,12,13,18])]
        else:groups=[("Source",list(range(len(def_fields))))]
        for col,(title,indices) in enumerate(groups):
            box=QGroupBox(title);form=QFormLayout(box);form.setVerticalSpacing(5);form.setHorizontalSpacing(10);form.setContentsMargins(10,8,10,6)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for index in indices:
                label,unit=def_fields[index]
                if unit=="material":
                    edit=QComboBox();edit.setEditable(True);edit.setMinimumWidth(95);edit.setMaximumWidth(145)
                    edit_view=QListView(edit)
                    edit_view.setStyleSheet("QListView{background-color:#ffffff;color:#172b4d;border:1px solid #cbd5e1;outline:none;} QListView::item{padding:4px 8px;color:#172b4d;background:#ffffff;} QListView::item:hover{background-color:#dbeafe;color:#1e40af;} QListView::item:selected{background-color:#245c96;color:#ffffff;}")
                    edit.setView(edit_view)
                    edit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                    edit.addItem("");edit.addItems(materials);edit.currentTextChanged.connect(self.changed)
                    if mode=="well" and index==11:
                        edit.setCurrentText("copper")
                    btn=QPushButton("✏️ Edit");btn.setFixedWidth(58)
                    btn.setStyleSheet("background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;padding:2px 4px;font-size:8.5pt;")
                    btn.setToolTip(f"Modify density or chemical composition of {label.lower()} in Material Editor")
                    btn.clicked.connect(partial(self.modify_material,index))
                    cell=QWidget();cell.setStyleSheet("background:transparent;");cl=QHBoxLayout(cell);cl.setContentsMargins(0,0,0,0);cl.setSpacing(4)
                    cl.addWidget(edit,1);cl.addWidget(btn)
                    self.inputs[index]=edit
                    form.addRow(_field_label(label,unit),cell)
                else:
                    edit=NumberEdit();edit.setPlaceholderText("0.0 mm");edit.setMinimumWidth(85);edit.setMaximumWidth(115);edit.textEdited.connect(self.changed)
                    if mode=="well" and index in (7, 8):
                        edit.setPlaceholderText("Default: absorber")
                    self.inputs[index]=edit
                    form.addRow(_field_label(label,unit),edit)
            grid.addWidget(box,0,col,Qt.AlignmentFlag.AlignTop)
        grid.setRowStretch(1,1)
    def modify_material(self,index):
        if self.owner and hasattr(self.owner,"open_material_editor_for_input"):
            self.owner.open_material_editor_for_input(self.inputs[index],return_tab_index=1)
    def values(self):
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
                    res.append(float(text) if text else (None if i in (7, 8) else 0.0))
        if self.mode == "well" and self.kind == "detector":
            dd = res[2] if len(res) > 2 and res[2] is not None else 0.0
            if res[7] is None: res[7] = dd
            if res[8] is None: res[8] = dd
            if res[9] is None: res[9] = 0.0
            if res[10] is None: res[10] = 0.0
            if not res[11]: res[11] = "copper"
            if res[7] == dd and res[8] == dd and res[9] == 0.0 and res[10] == 0.0 and res[11] == "copper":
                return res[:7]
            return res
        return [form_value(self.inputs[i], label, unit) for i, (label, unit) in enumerate(def_fields)]
    def set_values(self,values):
        if self.kind == "detector":
            if self.mode == "marinelli" and len(values) == 19:
                values = list(values[:12]) + [values[14], values[15], values[16], values[17]]
            elif self.mode in ("cylindrical", "efftran") and len(values) == 16:
                values = list(values[:12]) + [0.0, 0.0, values[12], values[13], values[14], values[15], "copper"]
        for index in sorted(self.inputs):
            edit=self.inputs[index]
            if index < len(values):
                val = values[index]
                if isinstance(edit,QComboBox):edit.setCurrentText(str(val))
                else:
                    if val is not None and str(val).strip():
                        edit.setText(str(float(val)))
                    else:
                        edit.clear()
            else:
                if isinstance(edit,QComboBox):
                    edit.setCurrentText("copper" if index==11 else "")
                else:
                    edit.clear()
    def clear(self):
        for edit in self.inputs.values():
            if isinstance(edit,QComboBox):edit.setCurrentIndex(0)
            else:edit.clear()


class SourceForm(QWidget):
    changed=Signal()
    kind_edited=Signal(str)
    def __init__(self,mode,owner=None):
        super().__init__();self.mode=mode;self.owner=owner;self.inputs={}
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0)
        card=QGroupBox("Geometry Parameters && Materials");g=QGridLayout(card);g.setHorizontalSpacing(20);g.setVerticalSpacing(8)
        hdr_param=QLabel("Parameter");hdr_param.setStyleSheet("font-weight:600;color:#475569;padding:6px 4px;background:transparent;")
        g.addWidget(hdr_param,0,0)
        self._col_headers={}
        for column,(kind,subtitle) in enumerate([("standard","Standard (Reference)"),("sample","Sample (Measured)")],1):
            hdr=QLabel(f"<b>{subtitle}</b>")
            hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hdr.setStyleSheet("background:#f1f5f9;color:#0f172a;border:1px solid #cbd5e1;border-radius:4px;padding:5px 8px;")
            g.addWidget(hdr,0,column)
            self._col_headers[kind]=hdr
        order=[2,5,0,4,1,3,6] if mode=="marinelli" else [1,5,0,2,3,6,4]
        materials=sorted(p.stem for p in (COMMON_DATA/"Composition").glob('*.txt'))
        for row,index in enumerate(order,1):
            label,unit=fields(mode,"sample")[index]
            g.addWidget(_field_label(label,unit),row,0)
            for column,kind in enumerate(("standard","sample"),1):
                if unit=="material":
                    edit=QComboBox();edit.setEditable(True);edit.setMinimumContentsLength(10)
                    edit_view=QListView(edit)
                    edit_view.setStyleSheet("QListView{background-color:#ffffff;color:#172b4d;border:1px solid #cbd5e1;outline:none;} QListView::item{padding:4px 8px;color:#172b4d;background:#ffffff;} QListView::item:hover{background-color:#dbeafe;color:#1e40af;} QListView::item:selected{background-color:#245c96;color:#ffffff;}")
                    edit.setView(edit_view)
                    edit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                    edit.addItem("");edit.addItems(materials)
                    edit.currentTextChanged.connect(lambda _t,k=kind:(self.kind_edited.emit(k.title()),self.changed.emit()))
                    btn=QPushButton("✏️ Edit");btn.setFixedWidth(58)
                    btn.setStyleSheet("background:#f0f9ff;color:#0369a1;border:1px solid #bae6fd;padding:2px 4px;font-size:8.5pt;")
                    btn.setToolTip(f"Edit density [g/cm³] or composition of {kind.title()} {label.lower()}")
                    btn.clicked.connect(partial(self.modify_material,kind,index))
                    cell=QWidget();cell.setStyleSheet("background:transparent;");cl=QHBoxLayout(cell);cl.setContentsMargins(0,0,0,0);cl.setSpacing(4)
                    cl.addWidget(edit,1);cl.addWidget(btn)
                    self.inputs[kind,index]=edit;g.addWidget(cell,row,column)
                else:
                    edit=NumberEdit();edit.setPlaceholderText("0.0 mm")
                    edit.textEdited.connect(lambda _t,k=kind:(self.kind_edited.emit(k.title()),self.changed.emit()))
                    self.inputs[kind,index]=edit;g.addWidget(edit,row,column)
        row=len(order)+1
        self.load_buttons={};self.save_buttons={}
        for column,kind in enumerate(("standard","sample"),1):
            bar=QHBoxLayout();bar.setSpacing(6)
            load=QPushButton(f"📂 Load {kind.title()}…");load.setStyleSheet("font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;")
            save=QPushButton(f"💾 Store {kind.title()}…")
            bar.addWidget(load);bar.addWidget(save)
            g.addLayout(bar,row,column);self.load_buttons[kind]=load;self.save_buttons[kind]=save
        g.setColumnStretch(1,1);g.setColumnStretch(2,1)
        outer.addWidget(card)
        outer.addStretch(1)
    def set_standard_enabled(self,enabled:bool):
        for (kind,idx),widget in self.inputs.items():
            if kind=="standard":widget.setEnabled(enabled)
        if "standard" in self.load_buttons:self.load_buttons["standard"].setEnabled(enabled)
        if "standard" in self.save_buttons:self.save_buttons["standard"].setEnabled(enabled)
        if "standard" in self._col_headers:
            self._col_headers["standard"].setStyleSheet(
                "background:#f1f5f9;color:#0f172a;border:1px solid #cbd5e1;border-radius:4px;padding:6px 10px;" if enabled else
                "background:#f8fafc;color:#94a3b8;border:1px dashed #cbd5e1;border-radius:4px;padding:6px 10px;"
            )
    def modify_material(self,kind,index):
        if self.owner and hasattr(self.owner,"open_material_editor_for_input"):
            self.owner.open_material_editor_for_input(self.inputs[kind,index],return_tab_index=2)
    def values(self,kind):
        return [form_value(self.inputs[kind,i],kind.title()+" — "+label,unit) for i,(label,unit) in enumerate(fields(self.mode,kind))]
    def set_values(self,kind,values):
        for i,value in enumerate(values):
            edit=self.inputs[kind,i]
            if isinstance(edit,QComboBox):edit.setCurrentText(str(value))
            else:edit.setText(str(float(value)))
    def clear(self):
        for edit in self.inputs.values():
            if isinstance(edit,QComboBox):edit.setCurrentIndex(0)
            else:edit.clear()


class Schematic(QWidget):
    def __init__(self,owner,default_kind="Sample"):
        super().__init__();self.owner=owner;self.live_widget=None
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        try:
            from .geometry_view import LiveGeometryWidget
            self.live_widget=LiveGeometryWidget(owner,default_kind=default_kind)
            layout.addWidget(self.live_widget,1)
        except ImportError:
            button=QPushButton("📐 View Dimensioned Detector & Source Cross-Section…")
            button.clicked.connect(self.open);layout.addWidget(button)
    def set_kind(self,kind):
        if self.live_widget is not None:self.live_widget.set_kind(kind)
    def refresh(self,*unused):
        if self.live_widget is not None:self.live_widget.refresh()
    def update(self,*args):
        self.refresh()
        super().update(*args)
    def open(self,*unused):
        if self.live_widget is not None:
            self.live_widget.open();return
        from .geometry_view import GeometryDialog
        dialog=GeometryDialog(self.owner);dialog.exec()


def _num_item(text,*,editable=True,bold=False,bg=None,fg=None,align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,tooltip=""):
    item=QTableWidgetItem(str(text))
    item.setTextAlignment(align)
    if not editable:
        item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
    if bold:
        font=item.font();font.setBold(True);item.setFont(font)
    if bg:item.setBackground(QColor(bg))
    if fg:item.setForeground(QColor(fg))
    if tooltip:item.setToolTip(tooltip)
    return item


class CalibrationTable(QTableWidget):
    def keyPressEvent(self,event):
        if event.matches(__import__('PySide6.QtGui',fromlist=['QKeySequence']).QKeySequence.StandardKey.Paste):
            text=QApplication.clipboard().text();start=max(0,self.currentRow());column=max(0,self.currentColumn())
            for offset,line in enumerate(text.splitlines()):
                if start+offset>=self.rowCount():break
                if '\t' in line:cells=line.split('\t')
                elif ';' in line or ',' in line:
                    import csv
                    cells=next(csv.reader([line],delimiter=';' if ';' in line else ','))
                else:cells=line.split()
                for j,token in enumerate(cells):
                    if column+j<3:
                        self.setItem(start+offset,column+j,_num_item(token.strip(),editable=True))
            return
        super().keyPressEvent(event)


class CalibrationDelegate(QStyledItemDelegate):
    def createEditor(self,parent,option,index):
        editor=super().createEditor(parent,option,index) if index.column()<3 else None
        if isinstance(editor,QLineEdit):
            editor.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        return editor


class TaskWorker(QObject):
    succeeded=Signal(object);failed=Signal(str);finished=Signal();progress=Signal(str)
    def __init__(self,operation):super().__init__();self.operation=operation
    @Slot()
    def run(self):
        try:self.succeeded.emit(self.operation(self.progress.emit))
        except Exception as exc:self.failed.emit(str(exc))
        finally:self.finished.emit()


class LicenseDialog(QDialog):
    """Offline licence import and status UI."""

    def __init__(self, parent=None, store=None):
        super().__init__(parent)
        from .licensing.storage import default_store
        self.store = store or default_store(VERSION)
        self.setWindowTitle("EffSuite Licence & Activation")
        self.resize(680, 480)
        vl = QVBoxLayout(self)
        vl.setContentsMargins(16, 14, 16, 14)
        vl.setSpacing(10)

        header = QLabel("<h3>EffSuite Licence & Activation</h3>")
        vl.addWidget(header)

        intro = QLabel(
            "Activate your official build of EffSuite with an authorized .efflic licence file. "
            "Activation is completely offline; calculation models and spectrum data are never transmitted."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#475569;margin-bottom:4px;")
        vl.addWidget(intro)

        self.status_view = QPlainTextEdit()
        self.status_view.setReadOnly(True)
        self.status_view.setStyleSheet("background:#ffffff;border:1px solid #cbd5e1;border-radius:4px;padding:8px;font-family:Consolas,monospace;font-size:9.5pt;")
        vl.addWidget(self.status_view, 1)

        row = QHBoxLayout()
        self.btn_import = QPushButton("📥 Import Licence File (.efflic)…")
        self.btn_import.clicked.connect(self.import_file)
        self.btn_import.setStyleSheet("font-weight:600;background:#2563eb;color:#ffffff;padding:7px 14px;border-radius:4px;")
        row.addWidget(self.btn_import)

        self.btn_request = QPushButton("📤 Save Activation Request…")
        self.btn_request.clicked.connect(self.save_request)
        row.addWidget(self.btn_request)

        self.btn_copy_id = QPushButton("📋 Copy Workstation ID")
        self.btn_copy_id.clicked.connect(self.copy_installation_id)
        row.addWidget(self.btn_copy_id)

        vl.addLayout(row)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setStyleSheet("padding:6px 18px;")
        bottom.addWidget(self.btn_close)
        vl.addLayout(bottom)

        self.refresh()

    def refresh(self):
        from .licensing.config import BUILD_MODE
        from .licensing.verification import LicenseError
        from .licensing.dates import readable_day, readable_utc, whole_last_day
        lines = []
        lines.append(f"Application:      EffSuite v{VERSION} ({BUILD_MODE} build)")
        lines.append(f"Installation ID:  {self.store.installation_id()}")
        lines.append(f"Licence store:    {self.store.directory}")
        lines.append("-" * 60)
        try:
            lic = self.store.current()
            lines.append("LICENCE STATUS:   ACTIVE & QUALIFIED")
            lines.append(f"Licensee:         {lic.licensee}")
            lines.append(f"Edition:          {lic.edition.title()} Edition")
            if lic.expires_at:
                lines.append(f"Expires:          {readable_utc(lic.expires_at)} (UTC)")
                last_day = whole_last_day(lic.expires_at)
                if last_day:
                    lines.append(f"                  Valid through {readable_day(last_day)}")
            else:
                lines.append("Expires:          Permanent (No expiration date)")
            lines.append(f"Covered versions: {('Through ' + lic.max_version) if lic.max_version else 'All versions'}")
            lines.append(f"Workstation lock: {'Locked to this workstation' if lic.installation_id else 'Site / Lab licence (Any workstation)'}")
            lines.append(f"Licence ID:       {lic.license_id}")
            lines.append(f"Issued at:        {readable_utc(lic.issued_at)} (UTC)")
        except LicenseError as exc:
            lines.append("LICENCE STATUS:   UNLICENSED / ACTIVATION REQUIRED")
            lines.append(f"Reason:           {exc}")
            lines.append("")
            lines.append("To activate:")
            lines.append("  1. Click 'Save Activation Request…' and send the file to your publisher.")
            lines.append("  2. When you receive your .efflic licence file, click 'Import Licence File…'.")
        self.status_view.setPlainText("\n".join(lines))

    def import_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import EffSuite Licence", "", "EffSuite Licence (*.efflic);;All Files (*)"
        )
        if not filename:
            return
        try:
            data = Path(filename).read_bytes()
            lic = self.store.import_license(data)
            self.refresh()
            QMessageBox.information(
                self,
                "Licence Activated",
                f"EffSuite has been successfully activated for:\n\n{lic.licensee}\nEdition: {lic.edition.title()}",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Activation Failed", f"Could not import licence:\n\n{exc}")

    def save_request(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Activation Request",
            str(documents() / "activation_request.req"),
            "Activation Request (*.req);;JSON (*.json);;All Files (*)",
        )
        if not filename:
            return
        try:
            req = self.store.request_document()
            dest = Path(filename)
            dest.write_text(json.dumps(req, indent=2) + "\n", encoding="utf-8")
            QMessageBox.information(
                self,
                "Request Saved",
                f"Activation request saved to:\n\n{dest}\n\nSend this file to your publisher to receive an authorized licence.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save request:\n\n{exc}")

    def copy_installation_id(self):
        try:
            uid = self.store.installation_id()
            QApplication.clipboard().setText(uid)
            QMessageBox.information(self, "Copied", f"Workstation ID copied to clipboard:\n\n{uid}")
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self._loading=True;self.dirty=False;self.thread=None;self.worker=None;self.cancel_event=threading.Event();self.project_path=None
        from .paths import get_data_dir
        default_data = get_data_dir()
        self.data_directory = str(default_data) if default_data else None
        self.transfer_result=None;self.summing_result=None;self.library_file=None;self.certificate_file=None;self.library_rows=[];self.certificate_rows=[];self.calibration_template=None;self.last_task=None;self._target_material_input=None;self._return_tab_index=None
        self.btn_export_cal_on_sum={};self.btn_export_sum_on_eff=None
        self.setWindowTitle("EffSuite — EFFTRAN / MEFFTRAN / WEFFTRAN")
        screen=QApplication.primaryScreen()
        avail=screen.availableGeometry() if screen else None
        init_w=min(1920,int(avail.width()*0.96)) if avail else 1680
        init_h=min(1040,int(avail.height()*0.94)) if avail else 920
        self.setMinimumSize(1024,650)
        self.resize(init_w,init_h)
        body=QWidget();outer=QVBoxLayout(body);outer.setContentsMargins(10,8,10,8);outer.setSpacing(6);self.setCentralWidget(body)
        # Top control bar
        top_frame=QFrame();top_frame.setStyleSheet("QFrame{background:#ffffff;border:1px solid #cbd5e1;border-radius:4px;padding:3px 6px;}")
        top=QHBoxLayout(top_frame);top.setContentsMargins(8,3,8,3);top.setSpacing(8)
        app_lbl=QLabel("<b>Geometry:</b>");app_lbl.setStyleSheet("border:none;background:transparent;")
        top.addWidget(app_lbl);self.mode=QComboBox();self.mode.setMinimumWidth(185)
        for key,name in MODES.items():self.mode.addItem(name+{"cylindrical":" — Cylindrical","marinelli":" — Marinelli","well":" — Well"}[key],key)
        top.addWidget(self.mode)
        sep_v=QFrame();sep_v.setFrameShape(QFrame.Shape.VLine);sep_v.setStyleSheet("color:#cbd5e1;");top.addWidget(sep_v)
        self.data_button=QPushButton("📁 Data Folder…");self.data_button.setToolTip("Select the folder containing Composition, Material, Detector, Standard, and NuclideLibrary");self.data_button.clicked.connect(self.choose_data);top.addWidget(self.data_button)
        self.data_label=QLabel("Data library: "+(self.data_directory if self.data_directory else "bundled original files"))
        self.data_label.setToolTip(self.data_directory if self.data_directory else "Bundled original files")
        self.data_label.setStyleSheet("color:#59677a;font-size:9pt;border:none;background:transparent;")
        top.addWidget(self.data_label,1)
        sep_v2=QFrame();sep_v2.setFrameShape(QFrame.Shape.VLine);sep_v2.setStyleSheet("color:#cbd5e1;");top.addWidget(sep_v2)
        wrk_lbl=QLabel("Workers:");wrk_lbl.setStyleSheet("border:none;background:transparent;");top.addWidget(wrk_lbl)
        self.workers=QSpinBox();self.workers.setRange(0,64);self.workers.setSpecialValueText("Auto");self.workers.setAlignment(Qt.AlignmentFlag.AlignCenter);self.workers.setMinimumWidth(96);top.addWidget(self.workers)
        sep_v3=QFrame();sep_v3.setFrameShape(QFrame.Shape.VLine);sep_v3.setStyleSheet("color:#cbd5e1;");top.addWidget(sep_v3)
        help_btn=QPushButton("❓ Help");help_btn.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;padding:4px 10px;")
        help_btn.clicked.connect(lambda:self.show_help_dialog("workflow"));top.addWidget(help_btn)
        self.license_btn=QPushButton("🔑 Licence…");self.license_btn.clicked.connect(self.show_license_dialog);top.addWidget(self.license_btn)
        outer.addWidget(top_frame)
        self.workflow="both";self.summing_source="nlb";self._building=False
        self.stepper=QFrame();self.stepper_layout=QHBoxLayout(self.stepper)
        self.splitter=QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.tabs=QTabWidget();self.tabs.setDocumentMode(True);self.tabs.setMinimumHeight(360)
        self.splitter.addWidget(self.tabs)
        self._build_tabs();self.tabs.currentChanged.connect(self.update_stepper)
        log_panel=QWidget();log_panel.setStyleSheet("background:transparent;");log_panel.setMinimumHeight(65)
        log_layout=QVBoxLayout(log_panel);log_layout.setContentsMargins(0,2,0,0);log_layout.setSpacing(4)
        footer=QHBoxLayout();footer.setContentsMargins(2,0,2,0);footer.setSpacing(8)
        self.status=QLabel("Ready — select a step above or load an example.");self.status.setStyleSheet("font-weight:600;color:#172b4d;background:transparent;")
        footer.addWidget(self.status,1)
        self.license_status=QLabel();self.license_status.setStyleSheet("font-size:9pt;padding:2px 8px;color:#245c96;")
        self.footer_license_label=self.license_status
        footer.addWidget(self.license_status)
        self.statusBar().addPermanentWidget(self.license_status)
        self.copy_btn=QPushButton("📋 Copy Log");self.copy_btn.setToolTip("Copy entire calculation log to clipboard")
        self.copy_btn.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;font-weight:500;padding:3px 10px;font-size:9pt;")
        self.copy_btn.clicked.connect(self.copy_log);footer.addWidget(self.copy_btn)
        self.clear_btn=QPushButton("🗑 Clear");self.clear_btn.setToolTip("Clear activity log")
        self.clear_btn.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;font-weight:500;padding:3px 10px;font-size:9pt;")
        self.clear_btn.clicked.connect(self.clear_log);footer.addWidget(self.clear_btn)
        self.cancel_button=QPushButton("⏹ Cancel Calculation");self.cancel_button.setStyleSheet("background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;font-weight:600;padding:3px 12px;")
        self.cancel_button.setEnabled(False);self.cancel_button.clicked.connect(lambda:self.cancel_event.set());footer.addWidget(self.cancel_button)
        log_layout.addLayout(footer)
        self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMinimumHeight(45);self.log.setMaximumBlockCount(10000)
        self.log.setStyleSheet("background-color:#0f172a;color:#38bdf8;border:1px solid #334155;border-radius:3px;padding:6px;font-family:'Cascadia Mono','Consolas',monospace;font-size:9.5pt;")
        self.log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.log.setPlaceholderText("Calculation progress & activity log…")
        log_layout.addWidget(self.log,1)
        self.splitter.addWidget(log_panel)
        self.splitter.setStretchFactor(0,6);self.splitter.setStretchFactor(1,1)
        self.splitter.setSizes([760,110])
        outer.addWidget(self.splitter,1)
        menu=self.menuBar().addMenu("File")
        for label,slot in [("New project",self.new_project),("Open project…",self.open_project),("Save project",self.save_project),("Save project as…",partial(self.save_project,True)),("Open result folder",self.open_results),("Licence & Activation…",self.show_license_dialog),("Exit",self.close)]:
            action=QAction(label,self);action.triggered.connect(slot);menu.addAction(action)
        help_menu=self.menuBar().addMenu("Help")
        for label,topic in [
            ("📖 Workflow & Step-by-Step Guide",partial(self.show_help_dialog,"workflow")),
            ("🧪 Material & Bulk Density Guide (XCOM)",partial(self.show_help_dialog,"materials")),
            ("💻 CLI & Batch Calculation Guide",partial(self.show_help_dialog,"cli")),
            ("🔑 Licence & Activation…",self.show_license_dialog),
            ("⚠️ Disclaimer & Terms of Use…",lambda:self.show_disclaimer_dialog(is_first_run=False)),
            ("ℹ️ About & Qualification Notice",partial(self.show_help_dialog,"about")),
        ]:
            action=QAction(label,self);action.triggered.connect(topic);help_menu.addAction(action)
        self.mode.currentIndexChanged.connect(self.change_mode);self.workers.valueChanged.connect(self.changed)
        self.setStyleSheet(APP_STYLESHEET)
        self.refresh_license_status()
        self.append_log(f"EffSuite v{VERSION} — Efficiency Transfer & Coincidence Summing ready.")
        self.append_log("EffSuite built by ChatGPT & Gemini under the supervision of G. Lutter.")
        self.append_log(f"Data directory: {self.data_directory or 'bundled assets'}")
        self._loading=False
        QTimer.singleShot(100, self.check_first_run_disclaimer)

    def check_first_run_disclaimer(self):
        from .paths import get_effsuite_root
        marker = get_effsuite_root() / ".disclaimer_accepted"
        if not marker.exists():
            self.show_disclaimer_dialog(is_first_run=True)

    def show_disclaimer_dialog(self, is_first_run=False):
        from .paths import get_effsuite_root
        dialog = QDialog(self)
        dialog.setWindowTitle("EffSuite — Disclaimer & Terms of Use")
        dialog.setMinimumWidth(540)
        vl = QVBoxLayout(dialog)
        vl.setContentsMargins(18, 16, 18, 16)
        vl.setSpacing(12)

        banner = QFrame()
        banner.setStyleSheet("QFrame{background:#fef2f2;border:1px solid #fecaca;border-left:5px solid #dc2626;border-radius:6px;padding:12px;}")
        bl = QVBoxLayout(banner)
        bl.setSpacing(6)
        t = QLabel("<b>⚠️ Important Notice & Disclaimer</b>")
        t.setStyleSheet("font-size:11.5pt;color:#991b1b;border:none;background:transparent;")
        bl.addWidget(t)

        msg = QLabel(
            "<p style='color:#7f1d1d;font-size:10pt;line-height:1.45;margin:0;'>"
            "Provided strictly on an <b>AS-IS</b> basis. <b>G. Lutter accepts NO responsibility or liability</b> "
            "under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. "
            "Users must independently verify all results."
            "</p>"
        )
        msg.setWordWrap(True)
        msg.setStyleSheet("border:none;background:transparent;")
        bl.addWidget(msg)
        vl.addWidget(banner)

        note = QLabel(
            f"<p style='font-size:9.5pt;color:#475569;margin:0;line-height:1.4;'>"
            f"<b>EffSuite v{VERSION}</b> — Built by ChatGPT &amp; Gemini under the supervision of G. Lutter.<br>"
            f"Physics engines based on EFFTRAN / MEFFTRAN / WEFFTRAN by Tim Vidmar and NIST XCOM."
            f"</p>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("background:#f8fafc;border:1px solid #cbd5e1;border-radius:4px;padding:8px;")
        vl.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("I Understand and Accept" if is_first_run else "Close")
        btn_ok.setStyleSheet("font-weight:600;background:#2563eb;color:#ffffff;padding:7px 22px;border-radius:4px;border:1px solid #1d4ed8;")
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

        dialog.exec()

    def current_mode(self):return self.mode.currentData()
    def _page(self, title, scrollable=True):
        outer = QWidget()
        outer.setStyleSheet("background:#ffffff;")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        body = QWidget()
        body.setStyleSheet("background:#ffffff;")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setStyleSheet("font-size:13pt;font-weight:600;color:#172b4d;background:transparent;padding-bottom:1px;")
        layout.addWidget(heading)
        if scrollable:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: #ffffff; border: none; }")
            scroll.setWidget(body)
            outer_layout.addWidget(scroll, 1)
        else:
            outer_layout.addWidget(body, 1)
        return outer, layout
    def _attach_footer(self, page, row_layout):
        foot = QFrame()
        foot.setObjectName("PageFooter")
        foot.setStyleSheet("QFrame#PageFooter{background:#f4f6f9;border-top:1px solid #cbd5e1;}")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(14, 7, 14, 7)
        fl.setSpacing(8)
        fl.addLayout(row_layout)
        page.layout().addWidget(foot, 0)
    # ---------------------------------------------------------------- guided workflow
    STEP_KEYS=("welcome","detector","source","efficiency","ctf","nlb")
    STEP_TITLES={"welcome":"Choose calculation","detector":"Detector","source":"Source (Standard / Sample)",
                 "efficiency":"Efficiency (.CAL)","ctf":"Certificate (.CTF)","nlb":"Nuclide library (.NLB)"}
    RUN_LABELS={"transfer":"▶ Run Efficiency Transfer","summing":"▶ Run Coincidence Summing","both":"🚀 Run Complete Analysis"}
    def tab_index(self,key):return self.STEP_KEYS.index(key)
    def visible_steps(self):
        keys=["welcome","detector","source"]
        if self.workflow in ("transfer","both"):keys.append("efficiency")
        if self.workflow in ("summing","both"):keys.append(self.summing_source)
        return keys
    def _step_banner(self,key,title_text,description="",input_req=None,extra_widgets=None):
        frame=QFrame()
        frame.setStyleSheet("QFrame{background:#f8fafc;border:1px solid #cbd5e1;border-left:4px solid #2563eb;border-radius:5px;padding:3px 10px;}")
        fl=QHBoxLayout(frame);fl.setContentsMargins(6,2,6,2);fl.setSpacing(10)
        h=QLabel(f"<b>{title_text}</b>");h.setStyleSheet("color:#0f172a;font-size:10.5pt;border:none;background:transparent;");fl.addWidget(h)
        self._banners[key]=(h,title_text)
        if input_req:
            req=QLabel(f"Input: <b>{input_req}</b>")
            req.setStyleSheet("color:#1e40af;font-size:9pt;background:#eff6ff;border:1px solid #bfdbfe;border-radius:4px;padding:2px 8px;")
            fl.addWidget(req)
        fl.addStretch()
        if extra_widgets:
            for w in extra_widgets:
                fl.addWidget(w)
        return frame
    def _nav_row(self,key,extra_btn=None):
        row=QHBoxLayout();row.setContentsMargins(0,0,0,0)
        back=QPushButton("◀ Previous Step");back.clicked.connect(lambda:self.go_step(-1));row.addWidget(back)
        row.addStretch()
        if extra_btn is not None:row.addWidget(extra_btn)
        nxt=QPushButton("Next ▶");nxt.clicked.connect(lambda:self.go_step(1));row.addWidget(nxt)
        self._nav_next[key]=nxt
        return row
    def go_step(self,delta):
        keys=self.visible_steps();cur=self.tabs.currentIndex()
        key=self.STEP_KEYS[cur] if cur<len(self.STEP_KEYS) else "welcome"
        pos=(keys.index(key) if key in keys else 0)+delta
        if pos>=len(keys):self.run_workflow();return
        if pos<0:return
        self.tabs.setCurrentIndex(self.tab_index(keys[pos]))
    def set_workflow(self,workflow=None,summing_source=None):
        if workflow:self.workflow=workflow
        if summing_source:self.summing_source=summing_source
        self.apply_workflow()
    def apply_workflow(self):
        if not hasattr(self,"efficiency"):return
        keys=self.visible_steps()
        for key in ("efficiency","ctf","nlb"):self.tabs.setTabVisible(self.tab_index(key),key in keys)
        total=len(keys)-1
        for i,key in enumerate(keys[1:],1):
            if key in self._banners:
                label,title=self._banners[key];label.setText(f"<b>STEP {i} of {total}: {title}</b>")
        for key,button in self._nav_next.items():
            if key not in keys:continue
            pos=keys.index(key)
            if pos==len(keys)-1:
                button.setText(self.RUN_LABELS[self.workflow]);button.setStyleSheet("font-weight:600;background:#16a34a;color:#ffffff;border:1px solid #15803d;padding:7px 18px;border-radius:5px;")
            else:
                button.setText(f"Next: {self.STEP_TITLES[keys[pos+1]]} ▶");button.setStyleSheet("font-weight:600;background:#2563eb;color:#ffffff;border:1px solid #1d4ed8;padding:7px 16px;border-radius:5px;")
        for value,radio in self._workflow_radios.items():
            radio.blockSignals(True);radio.setChecked(value==self.workflow);radio.blockSignals(False)
        for value,radio in self._source_radios.items():
            radio.blockSignals(True);radio.setChecked(value==self.summing_source);radio.setEnabled(self.workflow!="transfer");radio.blockSignals(False)
        self._source_box.setEnabled(self.workflow!="transfer")
        self.needs_label.setText(self.needs_text())
        self.source_hint.setVisible(self.workflow=="summing")
        if hasattr(self,"source_form"):
            self.source_form.set_standard_enabled(self.workflow!="summing")
        if getattr(self,"btn_export_sum_on_eff",None) is not None:
            self.btn_export_sum_on_eff.setVisible(self.workflow=="both")
            self.btn_export_sum_on_eff.setText("💾 Export Corrected "+("Library (.NLB)…" if self.summing_source=="nlb" else "Certificate (.CTF)…"))
        if hasattr(self,"btn_export_cal_on_sum"):
            for btn in self.btn_export_cal_on_sum.values():
                btn.setVisible(self.workflow=="both")
        self.update_stepper()
    def needs_text(self):
        items=["<b>Detector (.txt)</b> — from <code>Data/Detector</code>",
               "<b>Sample (.txt)</b> — geometry, matrix & density from <code>Data/Standard</code> or <code>Data/Sample</code>"]
        if self.workflow in ("transfer","both"):
            items+=["<b>Standard (.txt)</b> — calibration source geometry from <code>Data/Standard</code>",
                    "<b>Reference Calibration (.CAL)</b> — from <code>Data/Calibration</code> → <i>exports Sample .CAL</i>"]
        if self.workflow in ("summing","both"):
            items.append("<b>Certificate (.CTF)</b> → <i>exports corrected .CTF</i>"
                         if self.summing_source=="ctf" else
                         "<b>Nuclide Library (.NLB)</b> — from <code>Data/NuclideLibrary</code> → <i>exports corrected .NLB</i>")
        return "<ol style='margin:0px;line-height:1.35;'>"+"".join(f"<li>{i}</li>" for i in items)+"</ol>"
    def step_done(self,key):
        try:
            if key=="welcome":return True
            if key=="detector":self.detector_form.values();return True
            if key=="source":
                self.source_form.values("sample")
                if self.workflow in ("transfer","both"):self.source_form.values("standard")
                return True
            if key=="efficiency":return bool(self.calibration())
            if key=="ctf":return bool(self.certificate_rows)
            if key=="nlb":return bool(self.library_rows) or bool(self.nuclides.text().strip())
        except Exception:return False
        return False
    def missing_items(self):
        out=[]
        try:self.detector_form.values()
        except Exception as exc:out.append(("detector","Detector — "+str(exc)))
        try:self.source_form.values("sample")
        except Exception as exc:out.append(("source",str(exc)))
        if self.workflow in ("transfer","both"):
            try:self.source_form.values("standard")
            except Exception as exc:out.append(("source",str(exc)))
            try:
                if not self.calibration():out.append(("efficiency","Efficiency — import the reference calibration (.CAL)"))
            except Exception as exc:out.append(("efficiency","Efficiency — "+str(exc)))
        if self.workflow in ("summing","both"):
            if self.summing_source=="ctf" and not self.certificate_rows:out.append(("ctf","Certificate — open the Genie certificate (.CTF)"))
            if self.summing_source=="nlb" and not self.library_rows and not self.nuclides.text().strip():
                out.append(("nlb","Nuclide library — open the Genie library (.NLB) or type a nuclide list"))
        return out
    def sync_nuclides(self):
        rows=self.certificate_rows if self.summing_source=="ctf" else self.library_rows
        if rows:self.nuclides.setText(", ".join(dict.fromkeys(str(r["nuclide"]) for r in rows)))
    def run_workflow(self,*unused):
        missing=self.missing_items()
        if missing:
            self.error("Please complete these items before running:\n\n"+"\n".join("• "+text for _,text in missing))
            self.tabs.setCurrentIndex(self.tab_index(missing[0][0]));return
        if self.workflow in ("summing","both"):self.sync_nuclides()
        self.calculate(self.workflow)
    def update_stepper(self,*unused):
        if getattr(self,"_building",False) or not hasattr(self,"efficiency"):return
        while self.stepper_layout.count():
            item=self.stepper_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        keys=self.visible_steps();cur=self.tabs.currentIndex()
        for i,key in enumerate(keys):
            done=self.step_done(key);current=self.tab_index(key)==cur
            text=("Start" if key=="welcome" else f"{i}. {self.STEP_TITLES[key]}")+("  ✔" if done and key!="welcome" else "")
            button=QPushButton(text);button.setFlat(False)
            if current:style="font-weight:600;background:#2563eb;color:#ffffff;border:1px solid #1d4ed8;"
            elif done:style="font-weight:500;background:#dcfce7;border:1px solid #86efac;color:#14532d;"
            else:style="background:#f8fafc;border:1px solid #cbd5e1;color:#475569;"
            button.setStyleSheet(style+"padding:5px 12px;border-radius:13px;")
            button.clicked.connect(partial(self.tabs.setCurrentIndex,self.tab_index(key)))
            self.stepper_layout.addWidget(button)
            arrow=QLabel("→");arrow.setStyleSheet("color:#94a3b8;border:none;background:transparent;font-weight:bold;");self.stepper_layout.addWidget(arrow)
        run=QPushButton(self.RUN_LABELS[self.workflow])
        ready=not self.missing_items()
        if ready:
            run.setStyleSheet("font-weight:600;background:#16a34a;color:#ffffff;border:1px solid #15803d;padding:5px 14px;border-radius:13px;")
        else:
            run.setStyleSheet("font-weight:600;background:#dcfce7;color:#166534;border:1px solid #22c55e;padding:5px 14px;border-radius:13px;")
        run.clicked.connect(self.run_workflow);self.stepper_layout.addWidget(run);self.stepper_layout.addStretch()
    def _build_tabs(self):
        self._building=True
        while self.tabs.count():
            old=self.tabs.widget(0);self.tabs.removeTab(0);old.deleteLater()
        self._banners={};self._nav_next={};self._workflow_radios={};self._source_radios={}
        mode=self.current_mode()
        # ---- Welcome: choose calculation and summing input
        page,l=self._page("Welcome — Select Calculation Workflow")
        self.welcome_license_card=QFrame()
        l.addWidget(self.welcome_license_card)
        box=QGroupBox("A. Calculation Mode");bl=QVBoxLayout(box);bl.setSpacing(1);bl.setContentsMargins(12,10,12,8);group=QButtonGroup(box)
        for value,title,desc in [("both","Complete Analysis — Efficiency Transfer + Coincidence Summing (Recommended)","Outputs transferred Sample .CAL and summing-corrected .NLB or .CTF."),
                                 ("transfer","Efficiency Transfer Only","Computes F_ε(E) = ε_sample / ε_standard and exports transferred Sample .CAL."),
                                 ("summing","True Coincidence Summing Only","Computes cascade summing factors C and exports corrected .NLB or .CTF.")]:
            radio=PaintedRadio(title)
            group.addButton(radio);bl.addWidget(radio);self._workflow_radios[value]=radio
            radio.toggled.connect(lambda checked,v=value:checked and self.set_workflow(workflow=v))
            note=QLabel(desc);note.setWordWrap(True)
            note.setStyleSheet("color:#59677a;font-size:9pt;background:transparent;margin-left:26px;margin-bottom:5px;");bl.addWidget(note)
        bl.addStretch(1)
        self._source_box=QGroupBox("B. Coincidence Summing Target File");sl=QVBoxLayout(self._source_box);sl.setSpacing(1);sl.setContentsMargins(12,10,12,8);group2=QButtonGroup(self._source_box)
        for value,title,desc in [("nlb","Nuclide Library (.NLB) — Default for Sample Analysis","Updates gamma abundances (P_corr = P / C). Uncomputed lines (*) are preserved unchanged."),
                                 ("ctf","Certificate File (.CTF) — For Calibration Certificates","Updates certificate emission rates (R_corr = R / C).")]:
            radio=PaintedRadio(title)
            group2.addButton(radio);sl.addWidget(radio);self._source_radios[value]=radio
            radio.toggled.connect(lambda checked,v=value:checked and self.set_workflow(summing_source=v))
            note=QLabel(desc);note.setWordWrap(True)
            note.setStyleSheet("color:#59677a;font-size:9pt;background:transparent;margin-left:26px;margin-bottom:5px;");sl.addWidget(note)
        sl.addStretch(1)
        ab_row=QHBoxLayout();ab_row.setSpacing(10)
        ab_row.addWidget(box,3);ab_row.addWidget(self._source_box,2)
        l.addLayout(ab_row)
        need=QGroupBox("C. Required Files Checklist");nl=QVBoxLayout(need);nl.setContentsMargins(12,10,12,8);self.needs_label=QLabel();self.needs_label.setWordWrap(True);self.needs_label.setStyleSheet("color:#172b4d;font-size:9.5pt;background:transparent;");nl.addWidget(self.needs_label);l.addWidget(need)
        l.addStretch(1)
        row=QHBoxLayout();row.setContentsMargins(0,0,0,0)
        start=QPushButton("Start Guided Setup: Step 1 — Detector ▶");start.setStyleSheet("font-weight:600;background:#245c96;color:#ffffff;border:1px solid #1a4470;padding:7px 18px;border-radius:4px;");start.clicked.connect(lambda:self.go_step(1))
        example=QPushButton("📋 Load Built-in Example");example.clicked.connect(self.load_example)
        open_project=QPushButton("📂 Open Project…");open_project.clicked.connect(self.open_project)
        row.addWidget(start);row.addWidget(example);row.addWidget(open_project);row.addStretch()
        self._attach_footer(page,row)
        self.tabs.addTab(page,"Welcome")
        # ---- Detector
        page,l=self._page("Detector Geometry & Materials")
        if mode=="well":
            untested_banner=QFrame()
            untested_banner.setStyleSheet("QFrame{background:#fffbeb;border:1px solid #fde68a;border-left:5px solid #d97706;border-radius:5px;padding:8px 12px;}")
            ub_l=QHBoxLayout(untested_banner);ub_l.setContentsMargins(4,2,4,2);ub_l.setSpacing(8)
            ub_icon=QLabel("⚠️");ub_icon.setStyleSheet("font-size:14pt;border:none;background:transparent;");ub_l.addWidget(ub_icon)
            ub_text=QLabel("<b>WEFFTRAN Qualification Status:</b> The WEFFTRAN (Well-type detector) engine has been updated with the 3D spatial summing and ray-tracing boundary patch, but <b>is not fully laboratory tested/qualified yet</b>. Results must be independently verified by the analyst.")
            ub_text.setWordWrap(True);ub_text.setStyleSheet("color:#92400e;font-size:9.5pt;border:none;background:transparent;");ub_l.addWidget(ub_text,1)
            l.addWidget(untested_banner)
        load=QPushButton("📂 Load Detector…");load.setStyleSheet("font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;padding:4px 10px;");save=QPushButton("💾 Store Detector…");save.setStyleSheet("padding:4px 10px;");load.clicked.connect(partial(self.load_model,"detector"));save.clicked.connect(partial(self.store_model,"detector"))
        l.addWidget(self._step_banner("detector","Detector geometry & materials",input_req="Data\\Detector\\*.txt",extra_widgets=[load,save]))
        det_split=QHBoxLayout();det_split.setSpacing(10)
        self.detector_form=ModelForm(mode,"detector",owner=self);self.detector_form.changed.connect(self.changed)
        det_split.addWidget(self.detector_form,6)
        self.diagram=Schematic(self,default_kind="Detector Only");det_split.addWidget(self.diagram,5)
        l.addLayout(det_split,1)
        self._attach_footer(page,self._nav_row("detector"))
        self.tabs.addTab(page,"Detector")
        # ---- Source
        page,l=self._page("Source Geometries — Standard & Sample")
        l.addWidget(self._step_banner("source","Source geometries (Standard & Sample)",input_req="Data\\Standard\\*.txt"))
        self.source_hint=QLabel("ℹ Coincidence summing only: Standard column disabled.");self.source_hint.setStyleSheet("color:#1e40af;background:#eff6ff;border:1px solid #bfdbfe;border-radius:4px;padding:4px 8px;");l.addWidget(self.source_hint)
        src_split=QHBoxLayout();src_split.setSpacing(12)
        self.source_form=SourceForm(mode,owner=self);self.source_form.changed.connect(self.changed);src_split.addWidget(self.source_form,3)
        self.source_diagram=Schematic(self,default_kind="Sample");src_split.addWidget(self.source_diagram,2)
        self.source_form.kind_edited.connect(self.source_diagram.set_kind)
        l.addLayout(src_split,1)
        for kind in ("standard","sample"):
            self.source_form.load_buttons[kind].clicked.connect(partial(self.load_model,kind));self.source_form.save_buttons[kind].clicked.connect(partial(self.store_model,kind))
        self._attach_footer(page,self._nav_row("source"))
        self.tabs.addTab(page,"Source")
        # ---- Efficiency
        page,l=self._page("Efficiency Transfer")
        l.addWidget(self._step_banner("efficiency","Reference efficiency calibration (.CAL)",input_req="Data\\Calibration\\*.CAL (0 &lt; ε &le; 1)"))
        controls=QHBoxLayout()
        load=QPushButton("① Import Standard Efficiency (.CAL)…");load.setStyleSheet("font-weight:600;background:#2563eb;color:#ffffff;border:1px solid #1d4ed8;padding:6px 14px;")
        load.clicked.connect(self.import_calibration)
        transfer=QPushButton("▶ Check Transfer Only");transfer.clicked.connect(partial(self.calculate,"transfer"))
        export=QPushButton("💾 Export Sample Efficiency (.CAL)…");export.setStyleSheet("font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;");export.clicked.connect(self.export_calibration)
        self.btn_export_sum_on_eff=QPushButton("💾 Export Corrected Library (.NLB)…");self.btn_export_sum_on_eff.setStyleSheet("font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;");self.btn_export_sum_on_eff.clicked.connect(lambda:self.export_genie(self.summing_source))
        for b in (load,transfer,export,self.btn_export_sum_on_eff):controls.addWidget(b)
        controls.addStretch()
        l.addLayout(controls)
        self.efficiency=CalibrationTable(93,6)
        self.efficiency.setAlternatingRowColors(True)
        self.efficiency.setMinimumHeight(170)
        self.efficiency.setHorizontalHeaderLabels(["E [keV]","Standard ε","Standard u [%]","Sample ε (Transferred)","Sample u [%]","Transfer Factor F_ε"])
        self.efficiency.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.efficiency.horizontalHeader().setStretchLastSection(True)
        self.efficiency.itemChanged.connect(self.changed)
        l.addWidget(self.efficiency,3)
        self.efficiency.setItemDelegate(CalibrationDelegate(self.efficiency))
        for column,width in enumerate((110,190,150,200,150,180)):self.efficiency.setColumnWidth(column,width)
        self.efficiency.verticalHeader().setDefaultSectionSize(25)
        self.chart=None
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            self.figure=Figure(figsize=(7,1.8),tight_layout=True);self.chart=FigureCanvasQTAgg(self.figure);self.chart.setMinimumHeight(145);self.chart.setMaximumHeight(220);l.addWidget(self.chart,2)
        except ImportError:l.addWidget(QLabel("Install the desktop dependencies to display efficiency graphs."))
        self._attach_footer(page,self._nav_row("efficiency"))
        self.tabs.addTab(page,"Efficiency")
        # ---- Coincidence summing: Certificate or Library (only the chosen one is shown)
        for kind,title in [("ctf","Certificate"),("nlb","Library")]:
            page,l=self._page("True Coincidence Summing — "+("Certificate (.CTF)" if kind=="ctf" else "Nuclide Library (.NLB)"))
            need="Data\\Certificates\\*.CTF" if kind=="ctf" else "Data\\NuclideLibrary\\*.NLB"
            l.addWidget(self._step_banner(kind,"Coincidence summing — "+("Certificate (.CTF)" if kind=="ctf" else "Nuclide library (.NLB)"),input_req=need))
            bar=QHBoxLayout()
            load=QPushButton("① Open Genie "+("Certificate (.CTF)…" if kind=="ctf" else "Library (.NLB)…"))
            load.setStyleSheet("font-weight:600;background:#2563eb;color:#ffffff;border:1px solid #1d4ed8;padding:6px 14px;")
            load.clicked.connect(partial(self.import_genie,kind))
            process=QPushButton("▶ Check Summing Only");process.clicked.connect(partial(self.process_genie,kind))
            export=QPushButton("💾 Export Corrected "+("Certificate (.CTF)…" if kind=="ctf" else "Library (.NLB)…"))
            export.setStyleSheet("font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;")
            export.clicked.connect(partial(self.export_genie,kind))
            export_cal=QPushButton("💾 Export Sample Efficiency (.CAL)…")
            export_cal.setStyleSheet("font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;")
            export_cal.clicked.connect(self.export_calibration);self.btn_export_cal_on_sum[kind]=export_cal
            switch=QPushButton("⇄ Switch to "+("Nuclide Library (.NLB)" if kind=="ctf" else "Certificate (.CTF)"))
            other="nlb" if kind=="ctf" else "ctf"
            switch.clicked.connect(lambda checked=False,o=other:(self.set_workflow(summing_source=o),self.tabs.setCurrentIndex(self.tab_index(o))))
            for b in (load,process,export,export_cal):bar.addWidget(b)
            bar.addStretch();bar.addWidget(switch)
            l.addLayout(bar)
            if kind=="nlb":
                self.nuclides=QLineEdit();self.nuclides.setPlaceholderText("e.g. Co-60, Cs-134, Eu-152, Ba-133, Y-88 (auto-populated from .NLB)");self.nuclides.textEdited.connect(self.changed)
                nbar=QHBoxLayout();nlbl=QLabel("<b>Nuclides:</b>");nlbl.setStyleSheet("background:transparent;");nbar.addWidget(nlbl);nbar.addWidget(self.nuclides,1);l.addLayout(nbar)
            table=QTableWidget(0,4)
            table.setAlternatingRowColors(True)
            table.setHorizontalHeaderLabels(["Nuclide","Energy E [keV]","Summing Factor C","Not Computed"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            table.horizontalHeader().setStretchLastSection(True)
            table.setColumnWidth(0,140);table.setColumnWidth(1,160);table.setColumnWidth(2,190)
            table.verticalHeader().setDefaultSectionSize(25)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            l.addWidget(table,1)
            if kind=="nlb":self.library_table=table
            else:self.certificate_table=table
            foot_note=QLabel("ℹ A_corr = C · A.  * = no EFFTRAN decay data (original yield preserved unchanged).")
            foot_note.setStyleSheet("color:#475569;font-size:9pt;background:transparent;")
            l.addWidget(foot_note)
            self._attach_footer(page,self._nav_row(kind))
            self.tabs.addTab(page,title)
        from .material_gui import MaterialEditor
        self.material_editor=MaterialEditor(self);self.tabs.addTab(self.material_editor,"Material")
        self._building=False
        self.apply_workflow()
        self.refresh_geometry()
    def refresh_geometry(self):
        if hasattr(self,"diagram"):self.diagram.update()
        if hasattr(self,"source_diagram"):self.source_diagram.update()
    def changed(self,*unused):
        if self._loading:return
        self.dirty=True;self.transfer_result=None;self.summing_result=None
        self.efficiency.blockSignals(True)
        for row in range(self.efficiency.rowCount()):
            for col in range(3,6):self.efficiency.takeItem(row,col)
        self.efficiency.blockSignals(False)
        self.populate_summing();self.draw_chart()
        self.refresh_geometry()
        self.update_stepper()
    def change_mode(self,*unused):
        if self.thread is not None:return
        saved_detector=None
        try:
            saved_detector=self.detector_form.values()
        except Exception:
            pass
        data_dir=self.data_directory
        self._loading=True;self._build_tabs();self._loading=False;self.dirty=True;self.transfer_result=None;self.summing_result=None;self.library_rows=[];self.certificate_rows=[];self.library_file=None;self.certificate_file=None;self.calibration_template=None;self.last_task=None
        self.data_directory=data_dir
        self.data_label.setText("Data library: "+(self.data_directory or "bundled original files"))
        self.refresh_materials()
        self.refresh_license_status()
        if saved_detector is not None:
            try:
                self.detector_form.set_values(saved_detector)
            except Exception:
                pass
        self.refresh_geometry()
        if self.current_mode() == "well":
            self.status.setText("⚠️ WEFFTRAN (Well detector): The physics and spatial summing model is currently experimental / not fully tested. Verify results.")
            self.log.appendPlainText("[NOTICE] WEFFTRAN geometry selected. Note: WEFFTRAN spatial summing & ray-tracing updates are not fully laboratory qualified yet. Users must independently verify all results.")
    def choose_data(self,*unused):
        default_dir=documents("Data") if (documents("Data")).is_dir() else documents()
        filename=QFileDialog.getExistingDirectory(self,"EFFTRAN / MEFFTRAN / WEFFTRAN data folder",str(default_dir))
        if not filename:return
        if not any((Path(filename)/folder).is_dir() for folder in ("Material","Composition")):
            self.error("Choose the folder containing Material and Composition.");return
        self.data_directory=filename;self.data_label.setText("Data library: "+filename);self.refresh_materials();self.changed()
    def refresh_materials(self):
        folder=Path(self.data_directory) if self.data_directory else COMMON_DATA
        comp_dir=folder/"Composition"
        names=set(p.stem for p in comp_dir.glob("*.txt")) if comp_dir.is_dir() else set()
        names|=set(p.stem for p in (COMMON_DATA/"Composition").glob("*.txt"))
        sorted_names=sorted(names)
        for edit in list(self.detector_form.inputs.values())+list(self.source_form.inputs.values()):
            if isinstance(edit,QComboBox):
                current=edit.currentText();edit.blockSignals(True);edit.clear();edit.addItem("");edit.addItems(sorted_names);edit.setCurrentText(current);edit.blockSignals(False)
        if self.data_directory:self.material_editor.library.setText(str(folder))
    def open_material_editor_for_input(self,target_input,return_tab_index=None):
        from .materials import load_composition
        self._target_material_input=target_input;self._return_tab_index=return_tab_index
        mat_name=target_input.currentText().strip() if target_input else ""
        comp_file=None;search_dirs=[]
        if self.data_directory:search_dirs.append(Path(self.data_directory)/"Composition")
        search_dirs.append(COMMON_DATA/"Composition")
        if mat_name:
            for sdir in search_dirs:
                candidate=sdir/f"{mat_name}.txt"
                if candidate.is_file():comp_file=candidate;break
        if comp_file is not None:
            try:
                d=load_composition(comp_file)
                self.material_editor.set_definition(d)
                self.status.setText(f"Loaded '{mat_name}' into Material Editor. Adjust density [g/cm³] or formula, then click 'Create Material'.")
            except Exception as exc:self.error(f"Could not load composition for '{mat_name}': {exc}")
        else:
            self.material_editor.clear()
            if mat_name:self.material_editor.name.setText(mat_name)
            self.status.setText(f"Define composition for '{mat_name or 'new material'}', then click 'Create Material'.")
        if hasattr(self.material_editor,"return_button"):
            target_name="Detector" if return_tab_index==1 else "Source" if return_tab_index==2 else "Previous Step"
            self.material_editor.return_button.setText(f"◀ Return to {target_name}")
            self.material_editor.return_button.setVisible(return_tab_index is not None)
        self.tabs.setCurrentWidget(self.material_editor)
    def new_project(self,*unused):
        if self.dirty and QMessageBox.question(self,"New project","Discard the current unsaved project?")!=QMessageBox.StandardButton.Yes:return
        self.project_path=None;self.change_mode();self.dirty=False;self.tabs.setCurrentIndex(0)
    def error(self,message):QMessageBox.warning(self,"EffSuite",str(message))
    def show_license_dialog(self,*unused):
        dlg = LicenseDialog(self)
        dlg.exec()
        self.refresh_license_status()

    def import_license_directly(self):
        from .licensing.storage import default_store
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import EffSuite Licence", "", "EffSuite Licence (*.efflic);;All Files (*)"
        )
        if not filename:
            return
        try:
            store = default_store(VERSION)
            data = Path(filename).read_bytes()
            lic = store.import_license(data)
            self.refresh_license_status()
            QMessageBox.information(
                self,
                "Licence Activated",
                f"EffSuite has been successfully activated for:\n\n{lic.licensee}\nEdition: {lic.edition.title()} Edition",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Activation Failed", f"Could not import licence:\n\n{exc}")

    def refresh_license_status(self):
        from .licensing.config import LICENSE_REQUIRED
        if not LICENSE_REQUIRED:
            self.setWindowTitle(f"EffSuite v{VERSION} — EFFTRAN / MEFFTRAN / WEFFTRAN")
            if hasattr(self, "license_btn"):
                self.license_btn.setText("🔑 Licence…")
                self.license_btn.setToolTip("Licence enforcement is currently disabled (Community / Unrestricted mode). Click to manage licences…")
                self.license_btn.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;padding:4px 10px;font-size:9pt;")
            if hasattr(self, "footer_license_label"):
                self.footer_license_label.setText("Community build (Unrestricted)")
                self.footer_license_label.setStyleSheet("color:#245c96;font-size:9pt;padding:2px 6px;")
            card = getattr(self, "welcome_license_card", None)
            if card is not None:
                if card.layout() is None:
                    QVBoxLayout(card)
                while card.layout().count():
                    child = card.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                cl = card.layout()
                cl.setContentsMargins(12, 6, 12, 6)
                card.setStyleSheet("QFrame{background:#f8f9fa;border:1px solid #cbd5e1;border-radius:4px;}")
                h = QHBoxLayout()
                h.addWidget(QLabel("<span style='font-size:9.5pt;color:#59677a;'><b>Community Edition</b> — Licence enforcement is inactive. All calculations are unrestricted.</span>"))
                h.addStretch()
                btn = QPushButton("Licence Manager…")
                btn.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;font-size:8.5pt;padding:2px 8px;")
                btn.clicked.connect(self.show_license_dialog)
                h.addWidget(btn)
                cl.addLayout(h)
            return

        from .licensing.storage import default_store
        from .licensing.verification import LicenseError
        from .licensing.dates import readable_day, whole_last_day
        store = default_store(VERSION)
        try:
            lic = store.current()
            is_active = True
            licensee = lic.licensee
            edition = lic.edition.title()
            if lic.expires_at:
                exp_day = whole_last_day(lic.expires_at)
                exp_text = f"Valid through {readable_day(exp_day)}" if exp_day else f"Expires {lic.expires_at.strftime('%Y-%m-%d')}"
            else:
                exp_text = "Permanent"
            err_msg = ""
        except LicenseError as exc:
            is_active = False
            licensee = ""
            edition = ""
            exp_text = ""
            err_msg = str(exc)
        except Exception as exc:
            is_active = False
            licensee = ""
            edition = ""
            exp_text = ""
            err_msg = str(exc)

        # 1. Window Title
        if is_active:
            self.setWindowTitle(f"EffSuite v{VERSION} — Licensed: {licensee} ({exp_text})")
        else:
            self.setWindowTitle(f"EffSuite v{VERSION} — EFFTRAN / MEFFTRAN / WEFFTRAN")

        # 2. Top Header Pill Button
        if hasattr(self, "license_btn"):
            if is_active:
                self.license_btn.setText(f"🔑 Licence: {licensee}")
                self.license_btn.setToolTip(
                    f"EffSuite is activated (Beta Edition).\n\n"
                    f"Licensee: {licensee}\n"
                    f"Edition: {edition} Edition\n"
                    f"Status: {exp_text}\n"
                    f"Store: {store.directory}\n\n"
                    f"Click to manage licence…"
                )
            else:
                self.license_btn.setText("🔑 Licence…")
                self.license_btn.setToolTip(
                    f"EffSuite is unactivated.\n\n"
                    f"Status: {err_msg}\n\n"
                    f"A valid licence is required to run calculations.\n"
                    f"Click here to import your licence (.efflic) or copy your Workstation ID."
                )
            self.license_btn.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;padding:4px 10px;font-size:9pt;")

        # 3. Status Bar Footer Label
        if hasattr(self, "footer_license_label"):
            if is_active:
                self.footer_license_label.setText(f"Licence valid ({exp_text})")
                self.footer_license_label.setStyleSheet("color:#245c96;font-size:9pt;padding:2px 6px;")
            else:
                self.footer_license_label.setText("Licence unavailable — activate via Help")
                self.footer_license_label.setStyleSheet("color:#59677a;font-size:9pt;padding:2px 6px;")

        # 4. Welcome Tab Card
        card = getattr(self, "welcome_license_card", None)
        if card is not None:
            if card.layout() is not None:
                while card.layout().count():
                    child = card.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            else:
                QVBoxLayout(card)

            cl = card.layout()
            cl.setContentsMargins(12, 8, 12, 8)
            cl.setSpacing(4)

            if is_active:
                card.setStyleSheet("QFrame{background:#f4f8fb;border:1px solid #bcd0e6;border-left:4px solid #245c96;border-radius:4px;}")
                h = QHBoxLayout()
                h.addWidget(QLabel(f"<span style='font-size:10pt;font-weight:600;color:#172b4d;'>EffSuite v{VERSION} is Activated (Beta Version)</span>"))
                h.addStretch()
                btn = QPushButton("Licence Details…")
                btn.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;padding:3px 10px;font-size:9pt;")
                btn.clicked.connect(self.show_license_dialog)
                h.addWidget(btn)
                cl.addLayout(h)
                details = QLabel(f"<span style='color:#59677a;font-size:9pt;'><b>Licensed to:</b> {licensee} &nbsp;|&nbsp; <b>Edition:</b> {edition} Edition &nbsp;|&nbsp; <b>Status:</b> {exp_text} &nbsp;|&nbsp; <b>Workstation ID:</b> <code>{store.installation_id()}</code></span>")
                cl.addWidget(details)
            else:
                card.setStyleSheet("QFrame{background:#fbfbfd;border:1px solid #c9cfd7;border-left:4px solid #59677a;border-radius:4px;}")
                h = QHBoxLayout()
                h.addWidget(QLabel(f"<span style='font-size:10pt;font-weight:600;color:#172b4d;'>EffSuite is Running in Unactivated Mode</span>"))
                h.addStretch()
                btn_lic = QPushButton("📥 Activate Licence (.efflic)…")
                btn_lic.setStyleSheet("background:#245c96;color:#ffffff;border:1px solid #1a4470;font-weight:600;padding:4px 12px;border-radius:3px;font-size:9pt;")
                btn_lic.clicked.connect(self.import_license_directly)
                h.addWidget(btn_lic)
                cl.addLayout(h)

                msg = QLabel(
                    f"<span style='color:#59677a;font-size:9pt;'>"
                    f"A valid licence is required to run calculations. &nbsp;&nbsp;"
                    f"<b>Workstation ID:</b> <code>{store.installation_id()}</code>"
                    f"</span>"
                )

                row_act = QHBoxLayout()
                row_act.addWidget(msg)
                btn_copy = QPushButton("📋 Copy Workstation ID")
                btn_copy.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;font-size:9pt;padding:2px 8px;")
                btn_copy.clicked.connect(lambda: (QApplication.clipboard().setText(store.installation_id()), QMessageBox.information(self, "Copied", f"Workstation ID copied to clipboard:\n\n{store.installation_id()}")))
                row_act.addWidget(btn_copy)
                btn_req = QPushButton("Licence Manager…")
                btn_req.setStyleSheet("background:#e9edf2;color:#172b4d;border:1px solid #aeb9c7;font-size:9pt;padding:2px 8px;")
                btn_req.clicked.connect(self.show_license_dialog)
                row_act.addWidget(btn_req)
                row_act.addStretch()
                cl.addLayout(row_act)

    def _get_license_about_snippet(self):
        try:
            from .licensing.storage import default_store
            store = default_store(VERSION)
            lic = store.current()
            exp = lic.expires_at.strftime('%Y-%m-%d') if lic.expires_at else 'Permanent'
            return f"<hr><p><b>Licence Status:</b> <span style='color:#16a34a;font-weight:600;'>Active &amp; Qualified</span><br><b>Licensed to:</b> {lic.licensee}<br><b>Edition:</b> {lic.edition.title()} Edition<br><b>Expires:</b> {exp}</p>"
        except Exception as exc:
            return f"<hr><p><b>Licence Status:</b> <span style='color:#dc2626;font-weight:600;'>Activation required</span> ({exc})<br>Use <i>Help → 🔑 Licence &amp; Activation…</i> to activate.</p>"

    def show_help_dialog(self,topic="workflow",*unused):
        dialog=QDialog(self)
        dialog.setWindowTitle("EffSuite — User Guide & Reference")
        dialog.resize(820,620)
        vl=QVBoxLayout(dialog);vl.setContentsMargins(14,12,14,12);vl.setSpacing(10)
        tabs=QTabWidget()
        topics=[
            ("workflow","📖 Workflow Guide",
             "<h3>Step-by-Step Calculation Guide</h3>"
             "<p><b>1. Welcome Tab — Choose Calculation Mode:</b></p>"
             "<ul>"
             "<li><b>Complete Analysis (Recommended):</b> Performs both Efficiency Transfer (<i>Standard → Sample</i>) and True Coincidence Summing corrections in one run. Produces the transferred Sample <code>.CAL</code> and the summing-corrected Genie Nuclide Library (<code>.NLB</code>) or Certificate (<code>.CTF</code>).</li>"
             "<li><b>Efficiency Transfer Only:</b> Computes transfer factors <i>F<sub>ε</sub>(E) = ε<sub>sample</sub>(E) / ε<sub>standard</sub>(E)</i> and exports the Sample <code>.CAL</code>.</li>"
             "<li><b>True Coincidence Summing Only:</b> Computes cascade summing factors <i>C</i> (where <i>A<sub>corr</sub> = C · A</i>) for the Sample geometry without requiring a reference calibration curve.</li>"
             "</ul>"
             "<p><b>2. Detector Tab:</b> Load your detector model (<code>Data/Detector/*.txt</code>) or enter crystal, dead-layer, window, and housing dimensions in mm. The live axial cross-section updates in real time with all quotes.</p>"
             "<p><b>3. Source Tab:</b> Load or edit the <b>Standard</b> (reference calibration geometry) and <b>Sample</b> (measured sample geometry). Click <b>✏️ Edit</b> next to any material to verify or update its bulk density [g/cm³].</p>"
             "<p><b>4. Efficiency (.CAL) &amp; Library (.NLB) / Certificate (.CTF) Tabs:</b> Import your Genie 2000 reference files, run the calculation, and export the corrected Genie files.</p>"),
            ("materials","🧪 Materials & Density (XCOM)",
             "<h3>Material Composition &amp; Bulk Density Guide</h3>"
             "<p>Self-attenuation in gamma-ray spectrometry depends on both the <b>chemical composition</b> (mass attenuation coefficient <i>μ/ρ</i>) and the <b>bulk density</b> <i>ρ</i> [g/cm³] of the sample matrix (<i>μ = (μ/ρ) · ρ</i>).</p>"
             "<ul>"
             "<li><b>Automatic XCOM Generation:</b> If a material exists in <code>Composition/</code> but is missing in <code>Material/</code>, EffSuite automatically runs NIST XCOM to generate its photon attenuation table before calculation.</li>"
             "<li><b>Adjusting Sample Density:</b> When your sample filling height or mass changes (for example, <code>Glucose</code> compressed to <code>1.346 g/cm³</code>), click <b>✏️ Edit</b> next to the Sample material, enter the exact bulk density in <code>g/cm³</code>, and click <b>⚡ Create Material and Attenuation Table</b>.</li>"
             "<li><b>Formula Entry:</b> Up to 10 chemical compounds (e.g. <code>H2O</code>, <code>C6H12O6</code>, <code>SiO2</code>, <code>CaCO3</code>) with relative weights by mass (automatically normalized to 100%).</li>"
             "</ul>"),
            ("cli","💻 CLI & Batch Calculations",
             "<h3>Command-Line Interface (CLI) &amp; Batch Runner</h3>"
             "<p>Every operation available in the GUI can be executed directly from the command line or automated in batch scripts:</p>"
             "<p><b>1. Single Calculation with Inline Overrides (Height, Material, Density, Direct Outputs):</b></p>"
             "<pre style='background:#f1f5f9;padding:8px;border-radius:4px;'>"
             "effsuite cylinder --detector DET002 --standard PET70_40 --sample PET70_40 \\\n"
             "  --sample-height 33.4 --sample-material Glucose --sample-density 1.346 \\\n"
             "  --calibration TF400_268_2025.CAL --library NUTECH.NLB \\\n"
             "  --output-cal Sample_207724.CAL --output-nlb Sample_207724.NLB --plot-geometry"
             "</pre>"
             "<p><b>2. Batch Processing from a CSV or JSON Table:</b></p>"
             "<pre style='background:#f1f5f9;padding:8px;border-radius:4px;'>"
             "# Generate a ready-to-fill CSV template:\n"
             "effsuite batch --template my_samples.csv\n\n"
             "# Run all samples in the CSV and export batch_summary.csv + all .CAL/.NLB files:\n"
             "effsuite batch my_samples.csv --out BatchResults_2026 --plot-geometry"
             "</pre>"
             "<p><b>3. Standalone Geometry Diagram Export (PNG / PDF / SVG):</b></p>"
             "<pre style='background:#f1f5f9;padding:8px;border-radius:4px;'>"
             "effsuite plot-geometry --geometry cylinder --detector DET002 --sample PET70_40 --out geom.png"
             "</pre>"),
            ("about","ℹ️ About & Qualification",
             "<h3>EffSuite — EFFTRAN • MEFFTRAN • WEFFTRAN</h3>"
             f"<p><b>Version:</b> {VERSION} (Beta Version)</p>"
             "<p><i>EffSuite built by ChatGPT &amp; Gemini under the supervision of G. Lutter.</i></p>"
             "<div style='background:#fef2f2;border:1px solid #fecaca;border-left:4px solid #dc2626;border-radius:4px;padding:8px;margin:8px 0;'>"
             "<b style='color:#991b1b;'>Disclaimer:</b><br>"
             "<span style='color:#7f1d1d;font-size:9pt;'>Provided strictly on an AS-IS basis. G. Lutter accepts NO responsibility or liability under any circumstances for incorrect calculations, inaccurate analytical results, or damages resulting from software use. Users must independently verify all results.</span>"
             "</div>"
             "<p><b>Underlying Physics Engines:</b> Built on <b>EFFTRAN (v4.8, 2026)</b>, <b>MEFFTRAN (v1.7, 2026)</b>, and <b>WEFFTRAN (2018)</b> by Tim Vidmar (<a href='https://efftran.github.io/'>https://efftran.github.io/</a>), integrated with NIST XCOM photon cross-sections.</p>"
             "<p><b>Features:</b> Simultaneous true coincidence summing calculation in one pass across all nuclides in the library, multi-process parallel orchestration, and spatial quadrature integration for well detectors.</p>"
             "<p><b>Default Installation:</b> <code>C:\\GENIE2K\\EffSuite</code></p>"
             "<p><b>Notice & Qualification:</b> Beta version (evaluation & qualification release). Whenever evaluating or changing detector or sample characterizations, verify all models and transfer factors against reference standards.</p>"
             "<p style='color:#64748b;font-size:8.5pt;'>EFFTRAN copyright &copy; 2005–2026 Tim Vidmar. Permission to use, copy, modify, distribute and sell this software and its documentation for any purpose is hereby granted without fee, provided that copyright and permission notices appear in supporting documentation.</p>"
             + self._get_license_about_snippet()),
        ]
        target_idx=0
        for idx,(key,title,html) in enumerate(topics):
            if key==topic:target_idx=idx
            w=QScrollArea();w.setWidgetResizable(True)
            lbl=QLabel(html);lbl.setWordWrap(True);lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft)
            lbl.setStyleSheet("background:#ffffff;color:#1e293b;padding:12px;font-size:10pt;line-height:1.45;")
            w.setWidget(lbl)
            tabs.addTab(w,title)
        tabs.setCurrentIndex(target_idx)
        vl.addWidget(tabs,1)
        close_row=QHBoxLayout();close_row.addStretch()
        btn=QPushButton("Close");btn.setStyleSheet("font-weight:600;background:#2563eb;color:#ffffff;padding:6px 20px;border-radius:4px;")
        btn.clicked.connect(dialog.accept);close_row.addWidget(btn)
        vl.addLayout(close_row)
        dialog.exec()
    def load_model(self,kind,*unused):
        folder={"detector":"Detector","sample":"Sample","standard":"Standard"}[kind]
        default_dir=documents("Data/"+folder)
        filename,_=QFileDialog.getOpenFileName(self,"Load "+kind,str(default_dir),"EFFTRAN models (*.txt);;All files (*)")
        if not filename:return
        try:
            values=read_model(self.current_mode(),kind,filename)
            if kind=="detector":self.detector_form.set_values(values)
            else:
                self.source_form.set_values(kind,values)
                if hasattr(self,"source_diagram"):self.source_diagram.set_kind(kind.title())
            self.changed();self.refresh_geometry()
            self.append_log(f"Loaded {kind.title()} model from {Path(filename).name}")
        except Exception as exc:self.error(exc)
    def store_model(self,kind,*unused):
        folder={"detector":"Detector","sample":"Sample","standard":"Standard"}[kind]
        target_dir=documents("Data/"+folder)
        filename,_=QFileDialog.getSaveFileName(self,"Store "+kind,str(target_dir/(kind+".txt")),"EFFTRAN models (*.txt)")
        if not filename:return
        try:
            values=self.detector_form.values() if kind=="detector" else self.source_form.values(kind)
            Path(filename).write_bytes(model_bytes(self.current_mode(),kind,values))
            self.append_log(f"Saved {kind.title()} model to {Path(filename).name}")
        except Exception as exc:self.error(exc)
    def calibration(self):
        rows=[]
        for row in range(self.efficiency.rowCount()):
            cells=[self.efficiency.item(row,col).text().strip() if self.efficiency.item(row,col) else "" for col in range(3)]
            if not any(cells):continue
            if not cells[0] or not cells[1]:raise CoincidenceError(f"Calibration row {row+1} needs energy and efficiency")
            rows.append(dict(zip(("energy_keV","efficiency","u_rel_percent"),(numeric(cells[0]),numeric(cells[1]),numeric(cells[2]) if cells[2] else 0.))))
        return rows
    def collect(self,task="both"):
        project={"schema_version":1,"geometry":self.current_mode(),"task":task,"detector":self.detector_form.values(),"sample":self.source_form.values("sample"),"nuclides":normalize_nuclides([self.nuclides.text()]),"workers":self.workers.value()}
        if task in {"transfer","both"}:project.update(standard=self.source_form.values("standard"),calibration=self.calibration())
        if self.calibration_template:project["calibration_template"]=str(self.calibration_template)
        if self.data_directory:project["data_directory"]=self.data_directory
        exports={}
        if task in {"transfer","both"} and self.calibration_template and Path(self.calibration_template).is_file():
            exports["cal"]=str(self.calibration_template)
        if task in {"summing","both"}:
            if self.summing_source=="nlb" and self.library_file and Path(self.library_file).is_file():
                exports["nlb"]=str(self.library_file)
                if self.library_rows:
                    project["library_rows"]=[{"nuclide":str(r["nuclide"]),"energy_keV":float(r["energy"])} for r in self.library_rows]
            elif self.summing_source=="ctf" and self.certificate_file and Path(self.certificate_file).is_file():
                exports["ctf"]=str(self.certificate_file)
                if self.certificate_rows:
                    project["library_rows"]=[{"nuclide":str(r["nuclide"]),"energy_keV":float(r["energy"])} for r in self.certificate_rows]
        if exports:project["genie_exports"]=exports
        return validate_project(project)
    def draft(self):
        task=self.last_task or ("both" if self.calibration() and self.nuclides.text().strip() else "transfer" if self.calibration() else "summing")
        project={"schema_version":1,"geometry":self.current_mode(),"task":task,"detector":self.detector_form.values(),"sample":self.source_form.values("sample"),"nuclides":normalize_nuclides([self.nuclides.text()]),"workers":self.workers.value(),"calibration":self.calibration()}
        try:project["standard"]=self.source_form.values("standard")
        except ValueError:pass
        if self.calibration_template:project["calibration_template"]=str(self.calibration_template)
        if self.data_directory:project["data_directory"]=self.data_directory
        return project
    def apply_project(self,project):
        self._loading=True
        if project.get("task") in ("transfer","summing","both"):self.workflow=project["task"]
        index=list(MODES).index(project["geometry"]);self.mode.blockSignals(True);self.mode.setCurrentIndex(index);self.mode.blockSignals(False);self._build_tabs()
        self.detector_form.set_values(project["detector"]);self.source_form.set_values("sample",project["sample"])
        if project.get("standard"):self.source_form.set_values("standard",project["standard"])
        self.nuclides.setText(", ".join(project.get("nuclides",[])));self.workers.setValue(project.get("workers",0));self.set_calibration(project.get("calibration",[]));self.calibration_template=project.get("calibration_template")
        self.data_directory=project.get("data_directory");self.data_label.setText("Data library: "+(self.data_directory or "bundled original files"));self.refresh_materials();self.last_task=project.get("task")
        self._loading=False;self.dirty=False;self.transfer_result=None;self.summing_result=None;self.library_rows=[];self.certificate_rows=[];self.library_file=None;self.certificate_file=None;self.refresh_geometry();self.draw_chart();self.update_stepper()
    def load_example(self,*unused):
        from .app_cli import example_path
        name="cylinder" if self.current_mode()=="cylindrical" else self.current_mode()
        self.apply_project(json.loads(example_path(name).read_text()));self.project_path=None;self.status.setText("Original example loaded. Replace the example models with your laboratory models.");self.tabs.setCurrentIndex(1)
        self.append_log(f"Loaded built-in example: {name}")
    def open_project(self,*unused):
        filename,_=QFileDialog.getOpenFileName(self,"Open project",str(documents("Projects")),"EffSuite projects (*.json)")
        if filename:
            try:
                self.apply_project(json.loads(Path(filename).read_text()));self.project_path=Path(filename);self.tabs.setCurrentIndex(1)
                self.append_log(f"Opened project: {Path(filename).name}")
            except Exception as exc:self.error(exc)
    def save_project(self,save_as=False,*unused):
        try:project=self.draft()
        except Exception as exc:self.error("Load/enter detector and sample models before saving: "+str(exc));return
        if save_as or self.project_path is None:
            filename,_=QFileDialog.getSaveFileName(self,"Save project",str(documents("Projects")/"project.effsuite.json"),"EffSuite projects (*.json)")
            if not filename:return
            self.project_path=Path(filename)
        self.project_path.write_text(json.dumps(project,indent=2)+"\n");self.dirty=False;self.status.setText("Saved "+str(self.project_path))
        self.append_log(f"Saved project: {self.project_path.name}")
    def set_calibration(self,rows):
        self.efficiency.blockSignals(True);self.efficiency.clearContents()
        for index,row in enumerate(rows):
            for col,key in enumerate(("energy_keV","efficiency","u_rel_percent")):
                self.efficiency.setItem(index,col,_num_item(str(float(row[key])),editable=True))
        self.efficiency.blockSignals(False)
    def import_calibration(self,*unused):
        filename,_=QFileDialog.getOpenFileName(self,"Import standard efficiency",str(documents("Data/Calibration")),"Calibration (*.CAL *.cal *.txt *.csv);;Genie calibration (*.CAL *.cal);;Text calibration (*.txt *.csv);;All files (*)")
        if not filename:return
        def accepted(rows):
            self.set_calibration(rows);self.calibration_template=filename if Path(filename).suffix.lower()==".cal" else None;self.changed();self.draw_chart()
            self.append_log(f"Imported calibration from {Path(filename).name} ({len(rows)} energy points)")
        self.start_task(lambda log:calibration_rows(filename),accepted)
    def start_task(self,operation,callback,cancellable=False):
        if self.thread is not None:return
        self._callback=callback;self.cancel_event=threading.Event();self.thread=QThread(self);self.worker=TaskWorker(operation);self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run);self.worker.progress.connect(self.show_progress);self.worker.succeeded.connect(self.task_result);self.worker.failed.connect(self.task_error)
        self.worker.finished.connect(self.thread.quit);self.worker.finished.connect(self.worker.deleteLater);self.thread.finished.connect(self.thread.deleteLater);self.thread.finished.connect(self.task_finished)
        self.tabs.setEnabled(False);self.mode.setEnabled(False);self.workers.setEnabled(False);self.data_button.setEnabled(False);self.menuBar().setEnabled(False);self.cancel_button.setEnabled(cancellable);self.status.setText("Working…");self.thread.start()
    def copy_log(self):
        text=self.log.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status.setText("Log copied to clipboard.")
    def clear_log(self):
        self.log.clear()
        self.status.setText("Log cleared.")
    def append_log(self,message):
        t=time.strftime("%H:%M:%S")
        sb=self.log.verticalScrollBar()
        at_bottom=(sb.value()>=sb.maximum()-35) if sb else True
        self.log.appendPlainText(f"[{t}] {message}")
        if at_bottom and sb:sb.setValue(sb.maximum())
        self.log.ensureCursorVisible()
    @Slot(str)
    def show_progress(self,message):self.status.setText(message);self.append_log(message)
    @Slot(object)
    def task_result(self,value):
        try:self._callback(value)
        except Exception as exc:self.error(exc)
    @Slot(str)
    def task_error(self,message):self.status.setText("Calculation stopped: "+message);self.append_log("Error: "+message);self.error(message)
    @Slot()
    def task_finished(self):self.thread=None;self.worker=None;self.tabs.setEnabled(True);self.mode.setEnabled(True);self.workers.setEnabled(True);self.data_button.setEnabled(True);self.menuBar().setEnabled(True);self.cancel_button.setEnabled(False)
    def calculate(self,task,*unused):
        from .licensing.config import LICENSE_REQUIRED
        if LICENSE_REQUIRED:
            from .licensing.storage import default_store
            from .licensing.verification import LicenseError
            try:
                default_store(VERSION).current()
            except LicenseError as exc:
                QMessageBox.warning(
                    self,
                    "Licence Required",
                    f"A valid licence is required to run calculations:\n\n{exc}\n\nPlease activate EffSuite via Help → 🔑 Licence & Activation…",
                )
                self.show_license_dialog()
                return
        try:project=self.collect(task)
        except Exception as exc:self.error(exc);return
        self.last_task=task
        task_label = "Complete Analysis (Transfer + Summing)" if task == "both" else ("Efficiency Transfer" if task == "transfer" else "Coincidence Summing")
        self.append_log(f"Starting {task_label} calculation ({self.current_mode().title()} mode)...")
        try:
            recovery=documents("Recovery")/"last_project.json";temporary=recovery.with_suffix(".tmp");temporary.write_text(json.dumps(project,indent=2));temporary.replace(recovery)
        except OSError as exc:self.append_log("Could not save the recovery snapshot: "+str(exc))
        from .app_cli import default_output
        output=default_output();stop=self.cancel_event=threading.Event()
        # start_task creates the active event before the worker closure is called.
        self.start_task(lambda log:run_project(project,output,cancel=self.cancel_event,progress=log),self.accept_result,cancellable=True)
    def accept_result(self,result):
        self._loading=True
        if result["efficiency"]:
            self.transfer_result=result
            for i,row in enumerate(result["efficiency"]):
                for col,key,bold in [(3,"sample_efficiency",True),(4,"sample_relative_uncertainty_percent_legacy",False),(5,"transfer_factor",True)]:
                    item=_num_item(format(row[key],".6g"),editable=False,bold=bold,bg="#f0f9ff",fg="#0f172a")
                    self.efficiency.setItem(i,col,item)
            self.draw_chart()
        if result["summing"]:
            self.summing_result=result;self.populate_summing()
        if result["efficiency"] and not result["summing"]:
            self.tabs.setCurrentIndex(3)
        elif result["summing"]:
            self.tabs.setCurrentIndex(self.tab_index(self.summing_source))
        self._loading=False;self.status.setText("Completed — "+result["output_directory"]);self.append_log("Saved "+result["output_directory"])
        for warning in result["warnings"]:self.append_log(warning)
        try:(documents("Recovery")/"last_project.json").write_text(json.dumps(result["project"],indent=2))
        except OSError:pass
        if result.get("efficiency") and result.get("summing"):
            self.show_complete_analysis_summary(result)
    def show_complete_analysis_summary(self,result):
        if QApplication.platformName()=="offscreen":return
        dialog=QDialog(self)
        self._summary_dialog=dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle("Complete Analysis — Outputs Ready")
        dialog.setMinimumWidth(560)
        vl=QVBoxLayout(dialog);vl.setSpacing(12);vl.setContentsMargins(16,16,16,16)
        banner=QFrame()
        banner.setStyleSheet("QFrame{background:#ecfdf5;border:1px solid #10b981;border-left:5px solid #059669;border-radius:6px;padding:10px;}")
        bl=QVBoxLayout(banner);bl.setSpacing(4)
        t=QLabel("<b>✔ Complete Analysis Finished Successfully</b>")
        t.setStyleSheet("font-size:12pt;color:#065f46;border:none;background:transparent;")
        d=QLabel("Both required Genie 2000 output files have been calculated and are ready for export:")
        d.setStyleSheet("color:#047857;font-size:9.5pt;border:none;background:transparent;")
        bl.addWidget(t);bl.addWidget(d)
        vl.addWidget(banner)
        box=QGroupBox("Available Genie 2000 Exports")
        fl=QVBoxLayout(box);fl.setSpacing(10)
        row1=QHBoxLayout()
        info1=QLabel("<b>1. Corrected Sample Efficiency (.CAL)</b><br><span style='color:#475569;font-size:9pt;'>Transferred efficiency calibration for the sample geometry</span>")
        info1.setStyleSheet("background:transparent;")
        btn1=QPushButton("💾 Export Sample .CAL…")
        btn1.setStyleSheet("font-weight:600;background:#2563eb;color:#ffffff;border:1px solid #1d4ed8;padding:6px 14px;border-radius:4px;")
        btn1.clicked.connect(self.export_calibration)
        row1.addWidget(info1,1);row1.addWidget(btn1)
        fl.addLayout(row1)
        sep=QFrame();sep.setFrameShape(QFrame.Shape.HLine);sep.setStyleSheet("color:#e2e8f0;");fl.addWidget(sep)
        row2=QHBoxLayout()
        kind_name="Nuclide Library (.NLB)" if self.summing_source=="nlb" else "Certificate (.CTF)"
        desc_sum="Yields P / C corrected for cascade coincidence summing" if self.summing_source=="nlb" else "Emission rates R / C corrected for cascade coincidence summing"
        info2=QLabel(f"<b>2. Corrected {kind_name}</b><br><span style='color:#475569;font-size:9pt;'>{desc_sum}</span>")
        info2.setStyleSheet("background:transparent;")
        btn2=QPushButton(f"💾 Export Corrected {self.summing_source.upper()}…")
        btn2.setStyleSheet("font-weight:600;background:#2563eb;color:#ffffff;border:1px solid #1d4ed8;padding:6px 14px;border-radius:4px;")
        btn2.clicked.connect(lambda:self.export_genie(self.summing_source))
        row2.addWidget(info2,1);row2.addWidget(btn2)
        fl.addLayout(row2)
        vl.addWidget(box)
        dest=result.get("output_directory","")
        if dest:
            note=QLabel(f"<b>Results directory:</b> <span style='font-family:Consolas,monospace;font-size:9pt;'>{dest}</span>")
            note.setWordWrap(True);note.setStyleSheet("color:#334155;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;padding:8px;")
            vl.addWidget(note)
        actions=QHBoxLayout()
        btn_open=QPushButton("📂 Open Results Folder")
        btn_open.clicked.connect(self.open_results)
        btn_close=QPushButton("Done / View Tabs")
        btn_close.setStyleSheet("background:#16a34a;color:#ffffff;font-weight:600;padding:6px 20px;border-radius:4px;border:1px solid #15803d;")
        btn_close.clicked.connect(dialog.accept)
        actions.addWidget(btn_open);actions.addStretch();actions.addWidget(btn_close)
        vl.addLayout(actions)
        dialog.show()
    def draw_chart(self):
        if self.chart is None:return
        self.figure.clear();axes=self.figure.add_subplot(111)
        try:rows=self.calibration()
        except Exception:rows=[]
        if rows:axes.loglog([r["energy_keV"] for r in rows],[r["efficiency"] for r in rows],"o-",label="Standard (Reference)",color="#2563eb",markersize=4,linewidth=1.4)
        if self.transfer_result:
            rows=self.transfer_result["efficiency"];axes.loglog([r["energy_keV"] for r in rows],[r["sample_efficiency"] for r in rows],"s-",label="Sample (Transferred)",color="#dc2626",markersize=4,linewidth=1.4)
        axes.set_xlabel("Energy [keV]",fontsize=9.5);axes.set_ylabel("Full-energy efficiency ε",fontsize=9.5);axes.grid(True,which="both",alpha=.25)
        if axes.lines:axes.legend(fontsize=9,frameon=True,facecolor="#ffffff",edgecolor="#cbd5e1")
        self.chart.draw_idle()
    def import_genie(self,kind,*unused):
        folder="NuclideLibrary" if kind=="nlb" else "Certificates"
        camfiles = Path("C:/GENIE2K/CAMFILES")
        default_dir = camfiles if (kind == "nlb" and camfiles.is_dir()) else documents("Data/" + folder)
        filename,_=QFileDialog.getOpenFileName(self,"Open Genie file",str(default_dir),"Genie files (*."+kind.upper()+" *."+kind+")")
        if not filename:return
        from .genie import read_library,read_certificate
        def accepted(rows):
            if kind=="nlb":self.library_file=filename;self.library_rows=rows
            else:self.certificate_file=filename;self.certificate_rows=rows
            self.nuclides.setText(", ".join(dict.fromkeys(str(r["nuclide"]) for r in rows)));self.summing_source=kind;self.populate_summing();self.apply_workflow();self.status.setText("Loaded "+filename+" — next: "+("click "+self.RUN_LABELS[self.workflow] if self.workflow!="transfer" else "continue"))
        self.start_task(lambda log:(read_library if kind=="nlb" else read_certificate)(filename),accepted)
    def process_genie(self,kind,*unused):
        rows=self.library_rows if kind=="nlb" else self.certificate_rows
        if rows:self.nuclides.setText(", ".join(dict.fromkeys(str(r["nuclide"]) for r in rows)))
        self.calculate("summing")
    def populate_summing(self):
        from .genie import match_factor
        for table,records in [(self.library_table,self.library_rows),(self.certificate_table,self.certificate_rows)]:
            rows=records if records else ([dict(nuclide=r["nuclide"],energy=r["energy_keV"]) for r in self.summing_result["summing"]] if self.summing_result else [])
            table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                factor=None;reason="Not calculated"
                if self.summing_result:
                    try:factor=match_factor(self.summing_result,row["nuclide"],float(row["energy"]));reason=""
                    except Exception as exc:reason=str(exc)
                nuc_item=_num_item(row["nuclide"],editable=False,bold=True,align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,tooltip=reason)
                eng_item=_num_item(format(float(row["energy"]),".2f"),editable=False,align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,tooltip=reason)
                fac_str=format(factor,".6f") if factor is not None else ""
                fac_item=_num_item(fac_str,editable=False,bold=(factor is not None),bg="#f0f9ff" if factor is not None else None,fg="#0f172a" if factor is not None else None,align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,tooltip=reason)
                ast_item=_num_item("*" if factor is None else "",editable=False,bold=True,fg="#d97706" if factor is None else None,align=Qt.AlignmentFlag.AlignCenter,tooltip=reason)
                table.setItem(i,0,nuc_item)
                table.setItem(i,1,eng_item)
                table.setItem(i,2,fac_item)
                table.setItem(i,3,ast_item)
    def export_calibration(self,*unused):
        if not self.transfer_result:self.error("Calculate efficiency transfer first.");return
        default_dir=documents("Export");default_dir.mkdir(parents=True,exist_ok=True)
        stem=Path(self.calibration_template).stem if self.calibration_template else "sample_efficiency"
        default_path=str(default_dir/(stem+"_sample.CAL"))
        filename,selected=QFileDialog.getSaveFileName(self,"Export sample efficiency calibration",default_path,"Genie calibration (*.CAL);;CSV (*.csv);;All files (*.*)")
        if not filename:return
        if Path(filename).suffix.lower()==".cal":
            source=self.calibration_template
            if not source:
                source,_=QFileDialog.getOpenFileName(self,"Choose a CAL template with the same point count",str(documents("Data/Calibration")),"Genie calibration (*.CAL *.cal)")
            if not source:return
            from .genie import export_copy
            self.start_task(lambda log:export_copy(source,filename,self.transfer_result,"cal"),lambda r:self.status.setText(f"Genie CAL exported to {Path(filename).name} successfully"))
        else:
            import csv
            with open(filename,"w",newline="") as f:
                writer=csv.writer(f);writer.writerow(["energy_keV","efficiency","u_rel_percent"])
                for row in self.transfer_result["efficiency"]:writer.writerow([row["energy_keV"],row["sample_efficiency"],row["sample_relative_uncertainty_percent_legacy"]])
            self.status.setText("Exported "+filename)
    def export_genie(self,kind,*unused):
        source=self.library_file if kind=="nlb" else self.certificate_file
        if not source or not self.summing_result:self.error("Open the source Genie file and calculate its nuclides first.");return
        default_dir=documents("Export");default_dir.mkdir(parents=True,exist_ok=True)
        stem=Path(source).stem
        default_path=str(default_dir/(stem+"_corrected."+kind.upper()))
        filename,_=QFileDialog.getSaveFileName(self,f"Export corrected Genie {kind.upper()}",default_path,f"Genie (*.{kind.upper()});;All files (*.*)")
        if filename:
            from .genie import export_copy
            self.start_task(lambda log:export_copy(source,filename,self.summing_result,kind),lambda r:self.status.setText(f"Genie {kind.upper()} exported to {Path(filename).name} successfully"))
    def open_results(self,*unused):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        result=self.summing_result or self.transfer_result
        QDesktopServices.openUrl(QUrl.fromLocalFile(result["output_directory"] if result else str(documents("Results"))))
    def closeEvent(self,event):
        if self.thread is not None:self.cancel_event.set();self.status.setText("Stopping the calculation before closing…");event.ignore();return
        if self.dirty and QMessageBox.question(self,"Close EffSuite","Close without saving this project?")!=QMessageBox.StandardButton.Yes:event.ignore();return
        event.accept()


def main():
    multiprocessing.freeze_support();app=QApplication.instance() or QApplication([]);app.setFont(QFont("Segoe UI",10));window=MainWindow();window.show();return app.exec()


if __name__=="__main__":raise SystemExit(main())
