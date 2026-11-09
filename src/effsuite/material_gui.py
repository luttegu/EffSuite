"""Original Material workbook form backed by the shared CLI material service."""
from pathlib import Path
import shutil

from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QDesktopServices,QFont,QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QFileDialog,QHeaderView,QMessageBox,QComboBox,QGroupBox

from .model_io import ASSETS, COMMON_DATA
from .materials import TEMPLATE,load_composition,validate_composition,save_definition,create_material,default_library


class MaterialEditor(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.loading=False
        layout=QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12,8,12,8)

        top_bar=QHBoxLayout()
        title=QLabel('Material & XCOM Attenuation Builder')
        title.setStyleSheet("font-size:13.5pt;font-weight:700;color:#0f172a;")
        top_bar.addWidget(title)
        top_bar.addStretch()
        self.return_button=QPushButton("◀ Return to Source")
        self.return_button.setVisible(False)
        self.return_button.setStyleSheet("font-weight:600;background:#eff6ff;color:#1d4ed8;border:1px solid #93c5fd;padding:5px 14px;border-radius:5px;")
        self.return_button.clicked.connect(self.return_to_caller)
        top_bar.addWidget(self.return_button)
        layout.addLayout(top_bar)

        id_group=QGroupBox("1. Material Name && Bulk Density")
        id_layout=QHBoxLayout(id_group);id_layout.setSpacing(16);id_layout.setContentsMargins(10,12,10,8)
        name_form=QFormLayout();name_form.setSpacing(8)
        self.name=QLineEdit();self.name.setPlaceholderText('e.g. Salt_water, Glucose')
        name_lbl=QLabel('Material name');name_lbl.setStyleSheet("font-weight:600;color:#1e293b;")
        name_form.addRow(name_lbl,self.name)
        id_layout.addLayout(name_form,2)

        dens_form=QFormLayout();dens_form.setSpacing(8)
        self.density=QLineEdit();self.density.setPlaceholderText('e.g. 1.346')
        self.density.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        dens_lbl=QLabel('Density <span style="color:#64748b;font-weight:normal;">[g/cm³]</span>');dens_lbl.setTextFormat(Qt.TextFormat.RichText);dens_lbl.setStyleSheet("font-weight:600;color:#1e293b;")
        dens_form.addRow(dens_lbl,self.density)
        id_layout.addLayout(dens_form,1)
        layout.addWidget(id_group)

        comp_group=QGroupBox("2. Chemical Composition (up to 10 compounds)")
        comp_layout=QVBoxLayout(comp_group);comp_layout.setSpacing(6);comp_layout.setContentsMargins(10,12,10,8)
        bar=QHBoxLayout();bar.setSpacing(8)
        for text,action in [('📂 Load Composition / Excel…',self.load),('💾 Store JSON…',self.save),('📋 Copy Excel Template…',self.copy_template),('🧹 Clear',self.clear)]:
            button=QPushButton(text);button.clicked.connect(action);bar.addWidget(button)
        bar.addStretch()
        comp_layout.addLayout(bar)

        self.table=QTableWidget(10,3)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(25)
        self.table.setHorizontalHeaderLabels(['Chemical Formula (e.g. H2O, NaCl, C6H12O6)','Relative Weight by Mass','Normalized Mass Fraction [%]'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.update_fractions)
        comp_layout.addWidget(self.table,1)

        self.summary=QLabel('Enter chemical formulas and relative weights.')
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;padding:4px 8px;color:#334155;font-weight:500;")
        comp_layout.addWidget(self.summary)
        layout.addWidget(comp_group,1)

        out_group=QGroupBox("3. Output Data Folder && XCOM Generation")
        out_layout=QHBoxLayout(out_group);out_layout.setSpacing(10);out_layout.setContentsMargins(10,12,10,8)
        out_lbl=QLabel('Data folder:');out_lbl.setStyleSheet("font-weight:600;color:#334155;")
        out_layout.addWidget(out_lbl)
        self.library=QLineEdit(str(default_library()));out_layout.addWidget(self.library,1)
        browse=QPushButton('Browse…');browse.clicked.connect(self.browse);out_layout.addWidget(browse)
        generate=QPushButton('⚡ Create Material and Attenuation Table')
        generate.setStyleSheet("font-weight:600;font-size:10pt;background:#16a34a;color:#ffffff;border:1px solid #15803d;padding:7px 18px;border-radius:5px;")
        generate.clicked.connect(self.generate)
        out_layout.addWidget(generate)
        layout.addWidget(out_group)

        self.name.textChanged.connect(self.update_fractions);self.density.textChanged.connect(self.update_fractions)

    def return_to_caller(self):
        ret_idx=getattr(self.owner,"_return_tab_index",None)
        if ret_idx is not None:self.owner.tabs.setCurrentIndex(ret_idx)
        else:self.owner.tabs.setCurrentIndex(2)

    def clear(self):
        self.loading=True;self.name.clear();self.density.clear();self.table.clearContents();self.loading=False;self.update_fractions()

    def collect(self):
        rows=[]
        for r in range(10):
            cells=[self.table.item(r,c).text().strip() if self.table.item(r,c) else '' for c in range(2)]
            if not any(cells):continue
            rows.append({'formula':cells[0],'weight':cells[1].replace(',','.')})
        return validate_composition({'name':self.name.text(),'density_g_cm3':self.density.text().replace(',','.'),'components':rows})

    def set_definition(self,d):
        self.loading=True;self.name.setText(d['name']);self.density.setText(str(d['density_g_cm3']));self.table.clearContents()
        for r,row in enumerate(d['components']):
            f_item=QTableWidgetItem(row['formula'])
            w_item=QTableWidgetItem(str(row['weight']))
            w_item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(r,0,f_item);self.table.setItem(r,1,w_item)
        self.loading=False;self.update_fractions()

    def update_fractions(self,*unused):
        if self.loading:return
        self.loading=True
        try:
            for r in range(10):
                w_it=self.table.item(r,1)
                if w_it:w_it.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
            d=self.collect();total=sum(r['weight'] for r in d['components']);j=0
            for r in range(10):
                if self.table.item(r,0) and self.table.item(r,0).text().strip():
                    item=QTableWidgetItem(format(100*d['components'][j]['weight']/total,'.9g'))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
                    item.setBackground(QColor("#f0f9ff"))
                    item.setForeground(QColor("#0f172a"))
                    self.table.setItem(r,2,item);j+=1
                else:self.table.takeItem(r,2)
            self.summary.setText(f'✔ {len(d["components"])} compound(s), density = {d["density_g_cm3"]:g} g/cm³, total weight = {total:g} (normalized to 100%).')
            self.summary.setStyleSheet("background:#f0fdf4;border:1px solid #bbf7d0;border-radius:4px;padding:4px 8px;color:#166534;font-weight:600;")
        except Exception as exc:
            for r in range(10):self.table.takeItem(r,2)
            self.summary.setText(str(exc))
            self.summary.setStyleSheet("background:#fef2f2;border:1px solid #fecaca;border-radius:4px;padding:4px 8px;color:#991b1b;font-weight:500;")
        finally:self.loading=False

    def load(self,*unused):
        start_dir=Path(self.library.text().strip()) if self.library.text().strip() else default_library()
        target=start_dir/'Composition' if (start_dir/'Composition').is_dir() else start_dir
        filename,_=QFileDialog.getOpenFileName(self,'Load material composition',str(target),'Material definition (*.txt *.json *.xlsx *.xlsm *.xls);;All files (*)')
        if filename:self.owner.start_task(lambda log:load_composition(filename),self.set_definition)

    def save(self,*unused):
        try:d=self.collect()
        except Exception as exc:self.owner.error(exc);return
        start_dir=Path(self.library.text().strip()) if self.library.text().strip() else default_library()
        target=start_dir/'Composition' if (start_dir/'Composition').is_dir() else start_dir
        target.mkdir(parents=True,exist_ok=True)
        filename,_=QFileDialog.getSaveFileName(self,'Store composition definition',str(target/(d['name']+'.material.json')),'Material JSON (*.json)')
        if filename:
            try:save_definition(filename,d);self.owner.status.setText('Saved '+filename)
            except Exception as exc:self.owner.error(exc)

    def copy_template(self,*unused):
        start_dir=Path(self.library.text().strip()) if self.library.text().strip() else default_library()
        start_dir.mkdir(parents=True,exist_ok=True)
        filename,_=QFileDialog.getSaveFileName(self,'Copy editable Excel template',str(start_dir/'Material_Composition.xlsx'),'Excel workbook (*.xlsx)')
        if filename:
            try:
                from .parallel_coincidence import _publish_new
                _publish_new(Path(filename),TEMPLATE.read_bytes());QDesktopServices.openUrl(QUrl.fromLocalFile(filename))
            except Exception as exc:self.owner.error(exc)

    def browse(self,*unused):
        filename=QFileDialog.getExistingDirectory(self,'Output data folder',self.library.text())
        if filename:self.library.setText(filename)

    def generate(self,*unused):
        try:d=self.collect();library=Path(self.library.text().strip());mode=self.owner.current_mode();base=self.owner.data_directory
        except Exception as exc:self.owner.error(exc);return
        if not self.library.text().strip():self.owner.error('Choose an output data folder');return
        exists_in_lib=library.exists() and any((library/p/(d['name']+'.txt')).exists() for p in ('Composition','Material'))
        base_dir=Path(base) if base else COMMON_DATA
        exists_in_base=not library.exists() and any((base_dir/p/(d['name']+'.txt')).exists() for p in ('Composition','Material'))
        overwrite=False
        if exists_in_lib or exists_in_base:
            ans=QMessageBox.question(self,"Material Already Exists",
                                     f"Material '{d['name']}' already exists.\n\nDo you want to overwrite it with this new composition and recalculate attenuation?\n(Select 'No' to go back and rename it to save as a new material).",
                                     QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if ans!=QMessageBox.StandardButton.Yes:return
            overwrite=True
        def accepted(result):
            self.owner.data_directory=result['data_directory'];self.owner.data_label.setText('Data library: '+result['data_directory']);self.owner.refresh_materials();self.owner.changed()
            self.owner.status.setText('Created '+d['name']+' — applied to selection.')
            self.owner.log.appendPlainText('Material saved: '+result['attenuation_file'])
            target_input=getattr(self.owner,"_target_material_input",None)
            if target_input is not None and isinstance(target_input,QComboBox):
                target_input.setCurrentText(d['name'])
            ret_idx=getattr(self.owner,"_return_tab_index",None)
            if ret_idx is not None:
                self.owner.tabs.setCurrentIndex(ret_idx)
        self.owner.start_task(lambda log:create_material(d,library,geometry=mode,base_directory=base,cancel=self.owner.cancel_event,progress=log,overwrite=overwrite),accepted,cancellable=True)
