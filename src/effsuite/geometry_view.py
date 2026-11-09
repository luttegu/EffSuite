"""Dimensioned axial cross-sections using the native total.f coordinates (mm) with live CAD-style quotes."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QLabel,QPushButton,QWidget,QGroupBox,QSizePolicy
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from matplotlib.patches import Rectangle


def draw_geometry(ax,mode,d,s=None,kind='Sample',compact=False):
    ax.clear();warnings=[]
    colors={
        'Housing':'#cbd5e1',
        'Crystal envelope':'#bae6fd',
        'Active crystal':'#3b82f6',
        'Dead layer / well absorber':'#94a3b8',
        'Absorber':'#a8a29e',
        'Container':'#fde68a',
        'Source':'#f97316',
    }
    used=set();bounds=[]
    def box(x,y,w,h,label,fill=True):
        if w<=0 or h<=0:return
        ax.add_patch(Rectangle(
            (x,y),w,h,
            facecolor=colors.get(label,'#ffffff') if fill else 'none',
            edgecolor='#1e293b',
            linewidth=1.0,
            label=label if label not in used else None,
            zorder=2,
        ))
        used.add(label);bounds.extend([(x,y),(x+w,y+h)])

    # 1. Draw physical geometry boxes
    if mode=='well':
        diameter,length,absorber,well_d,well_h=d[:5];r=diameter/2;wr=well_d/2;bottom=length-well_h
        cryst_mat,abs_mat=d[5],d[6]
        mantle_dead = d[7] if len(d) > 7 else absorber
        bottom_dead = d[8] if len(d) > 8 else absorber
        holder_th = d[9] if len(d) > 9 else 0.0
        det_offset = d[10] if len(d) > 10 else 0.0
        holder_mat = d[11] if len(d) > 11 else "copper"

        if holder_th > 0:
            box(-r-holder_th, -holder_th, 2*(r+holder_th), length+holder_th, 'Holder', False)
        box(-r, 0, 2*r, length, 'Crystal envelope')
        box(-r+mantle_dead, bottom_dead, 2*(r-mantle_dead), length-bottom_dead, 'Active crystal')
        box(-wr-absorber,bottom-absorber,2*(wr+absorber),well_h+absorber,'Dead layer / well absorber')
        box(-wr,bottom,2*wr,well_h,'Well cavity')
        top=length
        det_quotes=[
            f'Crystal: Ø {diameter:g} × {length:g} mm ({cryst_mat})',
            f'Well cavity: Ø {well_d:g} × {well_h:g} mm',
            f'Well absorber: {absorber:g} mm ({abs_mat})',
        ]
        if mantle_dead != absorber:
            det_quotes.append(f'Mantle dead layer: {mantle_dead:g} mm')
        if bottom_dead != absorber:
            det_quotes.append(f'Bottom dead layer: {bottom_dead:g} mm')
        if holder_th > 0:
            det_quotes.append(f'Holder: {holder_th:g} mm ({holder_mat})')
        if det_offset > 0:
            det_quotes.append(f'Detector bottom gap: {det_offset:g} mm')
        if s:
            diameter_s,height,base,wall,gap=s[:5];outer_s=diameter_s/2;inner=outer_s-wall;z=bottom+gap+det_offset+base;source_top=z+height
            box(-outer_s,z-base,2*outer_s,height+2*base,'Container')
            box(-inner,z,2*inner,height,'Source')
            if outer_s>wr:warnings.append('⚠ Container outer diameter exceeds well cavity diameter.')
            if source_top>length:warnings.append(f'⚠ Source extends {source_top-length:g} mm above crystal rim.')
    else:
        diameter,length=d[2:4];r=diameter/2;outer=d[0]/2;top=length+d[7]+d[6]
        if mode=='cylindrical':
            cryst_mat,win_mat,cap_mat,hold_mat,abs_mat=d[14],d[15],d[16],d[17],d[18]
        else:
            cryst_mat,win_mat,cap_mat,hold_mat=d[12],d[13],d[14],d[15]
            abs_mat=''
        box(-outer,0,2*outer,length+d[7],'Housing',False)
        for x in [-outer,outer-d[1]]:box(x,0,d[1],length+d[7],'Housing')
        box(-r-d[10],0,2*(r+d[10]),length,'Holder',False)
        box(-r,0,2*r,length,'Crystal envelope')
        box(-r+d[5],0,2*(r-d[5]),length-d[4],'Active crystal')
        box(-d[8]/2,0,d[8],d[9],'Crystal bore')
        box(-outer,length+d[7],2*outer,d[6],'Housing')
        if mode=='cylindrical' and d[12]>0 and d[13]>0:
            box(-d[12]/2,top,d[12],d[13],'Absorber');top+=d[13]
        det_quotes=[
            f'Crystal: Ø {diameter:g} × {length:g} mm ({cryst_mat})',
            f'End cap: Ø {d[0]:g} mm, wall {d[1]:g} mm ({cap_mat})',
            f'Window: {d[6]:g} mm ({win_mat}), gap {d[7]:g} mm',
            f'Dead layer (top / side): {d[4]:g} / {d[5]:g} mm',
            f'Bore: Ø {d[8]:g} × {d[9]:g} mm | Holder: {d[10]:g} mm ({hold_mat})',
        ]
        if d[11]:det_quotes.append(f'Bulletization radius: {d[11]:g} mm')
        if mode=='cylindrical' and d[13]>0:
            det_quotes.append(f'Absorber: Ø {d[12]:g} × {d[13]:g} mm ({abs_mat})')
        if s and mode=='cylindrical':
            diameter_s,height,base,wall,gap=s[:5];outer_s=diameter_s/2;inner=outer_s-wall;z=top+gap+base;source_top=z+height
            box(-outer_s,z-base,2*outer_s,height+base,'Container')
            box(-inner,z,2*inner,height,'Source')
        elif s:
            diameter_s,hole_d,height,hole_h,wall=s[:5];outer_s=diameter_s/2;inner=outer_s-wall;hole=hole_d/2
            z=top+wall-hole_h;source_top=z+height-wall;ceiling=z+hole_h
            lower=min(source_top,ceiling)-z
            for x in [-inner,hole+wall]:box(x,z,inner-hole-wall,lower,'Source')
            box(-inner,ceiling,2*inner,source_top-ceiling,'Source')
            for x in [-hole-wall,hole]:box(x,z,wall,hole_h,'Container')
            box(-hole-wall,ceiling-wall,2*(hole+wall),wall,'Container')
            if hole<outer:warnings.append('⚠ Marinelli cavity is narrower than detector housing.')
            if source_top<=z:warnings.append('⚠ Filling height does not exceed container thickness.')

    if not bounds:
        bounds=[(-30,0),(30,60)]
    geom_xs=[x for x,_ in bounds];geom_ys=[y for _,y in bounds]
    geom_left,geom_right=min(geom_xs),max(geom_xs)
    geom_bot,geom_top=min(geom_ys),max(geom_ys)
    span=max(geom_right-geom_left,geom_top-geom_bot,25.0)
    step=max(span*0.14,11.0)
    fs=7.5 if compact else 8.4

    # 2. CAD Dimension Quote & Leader Callout Helpers
    def quote_h(x1,x2,y_q,text,y_ref1=0.0,y_ref2=0.0,color='#1e3a8a'):
        if abs(x2-x1)<=0:return
        ax.plot([x1,x1],[y_ref1,y_q],linestyle=':',linewidth=0.75,color=color,alpha=0.75,zorder=3)
        ax.plot([x2,x2],[y_ref2,y_q],linestyle=':',linewidth=0.75,color=color,alpha=0.75,zorder=3)
        ax.annotate('',xy=(x2,y_q),xytext=(x1,y_q),
                    arrowprops={'arrowstyle':'<->','color':color,'lw':1.05,'shrinkA':0,'shrinkB':0},zorder=4)
        ax.text((x1+x2)/2,y_q,text,ha='center',va='center',fontsize=fs,fontweight='bold',color=color,
                bbox={'boxstyle':'round,pad=0.2','facecolor':'#ffffff','edgecolor':color,'alpha':0.96,'lw':0.75},zorder=5)
        hw=max(abs(x2-x1)/2,len(text)*step*0.095)
        mx=(x1+x2)/2
        bounds.extend([(mx-hw,y_q-step*0.4),(mx+hw,y_q+step*0.4)])

    def quote_v(x_q,y1,y2,text,x_ref1=0.0,x_ref2=0.0,color='#1e3a8a',y_text=None):
        if abs(y2-y1)<=0:return
        ax.plot([x_ref1,x_q],[y1,y1],linestyle=':',linewidth=0.75,color=color,alpha=0.75,zorder=3)
        ax.plot([x_ref2,x_q],[y2,y2],linestyle=':',linewidth=0.75,color=color,alpha=0.75,zorder=3)
        ax.annotate('',xy=(x_q,y2),xytext=(x_q,y1),
                    arrowprops={'arrowstyle':'<->','color':color,'lw':1.05,'shrinkA':0,'shrinkB':0},zorder=4)
        ym=(y1+y2)/2 if y_text is None else y_text
        ax.text(x_q,ym,text,ha='center',va='center',fontsize=fs,fontweight='bold',color=color,
                bbox={'boxstyle':'round,pad=0.2','facecolor':'#ffffff','edgecolor':color,'alpha':0.96,'lw':0.75},zorder=5)
        hw=max(step*1.2,len(text)*step*0.10)
        bounds.extend([(x_q-hw,min(y1,ym)-step*0.3),(x_q+hw,max(y2,ym)+step*0.3)])

    def callout(xy_target,xy_box,text,color='#334155',ha='center'):
        ax.annotate(
            text,xy=xy_target,xytext=xy_box,
            ha=ha,va='center',fontsize=fs-0.2,fontweight='bold',color=color,
            arrowprops={'arrowstyle':'->','color':color,'lw':0.85,'connectionstyle':'arc3,rad=0.08'},
            bbox={'boxstyle':'round,pad=0.22','facecolor':'#ffffff','edgecolor':color,'alpha':0.96,'lw':0.75},
            zorder=6,
        )
        hw=max(step*1.3,len(text)*step*0.105)
        bounds.extend([(xy_box[0]-hw,xy_box[1]-step*0.4),(xy_box[0]+hw,xy_box[1]+step*0.4)])

    # 3. Bottom Horizontal Quotes (Detector Radial)
    b_track=geom_bot-step*0.75
    if mode=='well' and well_d>0:
        quote_h(-wr,wr,b_track,f'Well Ø {well_d:g} mm',bottom,bottom,'#0f766e')
        b_track-=step*0.85
    elif mode!='well' and d[8]>0:
        quote_h(-d[8]/2,d[8]/2,b_track,f'Bore Ø {d[8]:g} mm',0,0,'#0f766e')
        b_track-=step*0.85
    quote_h(-r,r,b_track,f'Crystal Ø {diameter:g} mm',0,0,'#1e3a8a')
    b_track-=step*0.85
    if mode!='well' and d[0]>0:
        quote_h(-outer,outer,b_track,f'Cap Ø {d[0]:g} mm',0,0,'#334155')

    # 4. Top Horizontal Quotes (Source / Cavity Radial)
    t_track=geom_top+step*0.75
    if s:
        if mode=='marinelli' and hole_d>0:
            quote_h(-hole,hole,t_track,f'Hole Ø {hole_d:g} mm',ceiling,ceiling,'#b45309')
            t_track+=step*0.85
        elif mode!='marinelli' and wall>0 and inner>0:
            quote_h(-inner,inner,t_track,f'Source Ø {2*inner:g} mm',source_top,source_top,'#b45309')
            t_track+=step*0.85
        quote_h(-outer_s,outer_s,t_track,f'Container Ø {diameter_s:g} mm',source_top,source_top,'#9a3412')
    elif mode=='cylindrical' and d[12]>0 and d[13]>0:
        quote_h(-d[12]/2,d[12]/2,t_track,f'Absorber Ø {d[12]:g} mm',top,top,'#475569')

    # 5. Left Vertical Quotes (Detector Axial + Thin Layer Callouts)
    l_track=geom_left-step*1.35
    if mode=='well':
        if well_h>0:
            quote_v(l_track,bottom,length,f'Well H: {well_h:g} mm',-wr,-wr,'#0f766e')
            l_track-=step*1.9
        quote_v(l_track,0,length,f'Crystal L: {length:g} mm',-r,-r,'#1e3a8a')
        callout((-wr-absorber/2,bottom), (l_track,min(bottom*0.4,length*0.2)), f'Absorber: {absorber:g} mm', '#475569')
    else:
        used_l1=False
        if d[9]>0:
            quote_v(l_track,0,d[9],f'Bore H: {d[9]:g} mm',-d[8]/2,-d[8]/2,'#0f766e')
            used_l1=True
        if d[7]>0:
            y_win=length+d[7]/2
            if d[9]>0 and abs(y_win-d[9]/2)<step*0.75:
                y_win=length+d[7]+step*0.35
            quote_v(l_track,length,length+d[7],f'Gap: {d[7]:g} mm',-outer,-outer,'#475569',y_text=y_win)
            used_l1=True
        if used_l1:
            l_track-=step*1.95
        quote_v(l_track,0,length,f'Crystal L: {length:g} mm',-r,-r,'#1e3a8a')
        # Leader callouts for thin detector layers (Window, Dead layer, Cap wall / Holder)
        callout((-outer*0.5,length+d[7]+d[6]/2), (l_track,length+d[7]+step*0.7),
                f'Win: {d[6]:g} mm | DL: {d[4]:g}/{d[5]:g} mm', '#334155')
        callout((-outer+d[1]/2,length*0.15), (l_track,-step*0.85),
                f'Cap wall: {d[1]:g} mm | Holder: {d[10]:g} mm', '#475569')

    # 6. Right Vertical Quotes (Source Axial + Wall/Bottom Callouts)
    r_track=geom_right+step*1.35
    src_quotes=[]
    if s:
        if mode=='marinelli':
            if hole_h>0:
                quote_v(r_track,z,ceiling,f'Hole H: {hole_h:g} mm',hole,hole,'#b45309')
                r_track+=step*1.95
            quote_v(r_track,z,source_top,f'Fill H: {height:g} mm',outer_s,outer_s,'#9a3412')
            callout((hole+wall/2,z+hole_h*0.25), (r_track,z-step*0.85), f'Container wall: {wall:g} mm', '#7c2d12')
            src_quotes=[
                f'{kind}: Ø {diameter_s:g} mm, Fill H {height:g} mm ({s[5]})',
                f'Hole: Ø {hole_d:g} × {hole_h:g} mm | Wall: {wall:g} mm ({s[6]})',
            ]
        else:
            ref_top=bottom if mode=='well' else top
            r_track_inner=r_track
            if gap>0:
                quote_v(r_track,ref_top,ref_top+gap,f'Gap: {gap:g} mm',outer_s,outer_s,'#0369a1')
                r_track+=step*1.95
            quote_v(r_track,z,source_top,f'Source H: {height:g} mm',outer_s,outer_s,'#9a3412')
            y_callout=min(ref_top,z-base)-step*1.05
            callout((outer_s-wall/2,z-base/2), ((r_track_inner+r_track)/2,y_callout),
                    f'Wall: {wall:g} mm | Bot: {base:g} mm', '#7c2d12')
            src_quotes=[
                f'{kind}: Ø {diameter_s:g} × {height:g} mm ({s[5]})',
                f'Container bottom / wall: {base:g} / {wall:g} mm ({s[6]})',
                f'Positioning gap: {gap:g} mm | Active Ø: {2*inner:g} mm',
            ]
    else:
        src_quotes=[f'Load or complete the {kind.lower()} fields to display source quotes.']

    ax.axvline(0,color='#64748b',linestyle='-.',linewidth=0.7,zorder=1)
    ax.set_aspect('equal',adjustable='box')
    ax.set_xlabel('Radial coordinate r [mm]',fontsize=fs+0.5,fontweight='bold',color='#1e293b')
    ax.set_ylabel('Axial coordinate z [mm]',fontsize=fs+0.5,fontweight='bold',color='#1e293b')
    ax.tick_params(labelsize=fs)
    ax.grid(alpha=0.2,linestyle='--')

    xs=[x for x,_ in bounds];ys=[y for _,y in bounds]
    pad_x=max(6.0,(max(xs)-min(xs))*0.04)
    pad_y=max(6.0,(max(ys)-min(ys))*0.05)
    ax.set_xlim(min(xs)-pad_x,max(xs)+pad_x)
    ax.set_ylim(min(ys)-pad_y,max(ys)+pad_y)

    if not compact:
        ax.set_title(f'{kind} & Detector — Axial Cross-Section (mm)',fontsize=fs+1.8,fontweight='bold',color='#0f172a',pad=8)
        ax.legend(loc='upper left',bbox_to_anchor=(1.01,1.0),fontsize=8.5,frameon=True,facecolor='#f8fafc',edgecolor='#cbd5e1',title='Regions',title_fontsize=8.5)
        quotes_card="ALL QUOTES & MATERIALS\n"+"\n".join("• "+q for q in det_quotes+src_quotes)
        if warnings:
            quotes_card+="\n\n"+"\n".join(warnings)
        ax.text(1.01,0.48,quotes_card,transform=ax.transAxes,va='top',ha='left',fontsize=8.0,color='#0f172a',
                bbox={'boxstyle':'round,pad=0.5','facecolor':'#f8fafc','edgecolor':'#cbd5e1','lw':0.9})
        return '\n'.join(det_quotes+src_quotes+(['']+warnings if warnings else []))
    else:
        ax.legend(loc='lower center',bbox_to_anchor=(0.5,1.01),ncol=4,fontsize=7.2,frameon=True,facecolor='#f8fafc',edgecolor='#cbd5e1',handlelength=1.2,columnspacing=0.9)
        short=f"{det_quotes[0]}  |  {src_quotes[0]}"
        if warnings:
            short+="\n"+"  ".join(warnings)
        return short


def _partial_detector_values(owner):
    """Extract valid detector values or fall back to safe preview defaults while typing."""
    try:
        return owner.detector_form.values(), True
    except Exception:
        mode=owner.current_mode()
        defaults={
            'well':[65.0,70.0,0.5,20.0,45.0,'Ge','aluminium'],
            'marinelli':[85.0,1.5,65.0,65.0,0.5,0.5,1.0,4.0,10.0,45.0,1.0,0.0,'Ge','aluminium','aluminium','copper'],
            'cylindrical':[85.0,1.5,65.0,65.0,0.5,0.5,1.0,4.0,10.0,45.0,1.0,0.0,0.0,0.0,'Ge','aluminium','aluminium','copper','aluminium'],
        }[mode]
        out=list(defaults)
        for i,edit in owner.detector_form.inputs.items():
            if i>=len(out):continue
            if hasattr(edit,'currentText'):
                txt=edit.currentText().strip()
                if txt:out[i]=txt
            else:
                txt=edit.text().strip().replace(',','.')
                try:
                    val=float(txt)
                    if val>=0:out[i]=val
                except ValueError:
                    pass
        return out, False


def _partial_source_values(owner,kind):
    """Extract valid source values or fall back to partial values if enough dimensions are typed."""
    try:
        return owner.source_form.values(kind), True
    except Exception:
        mode=owner.current_mode()
        defaults={
            'well':[15.0,40.0,1.0,1.0,0.0,'water_liquid','polyethylene'],
            'marinelli':[130.0,90.0,100.0,70.0,2.0,'water_liquid','polyethylene'],
            'cylindrical':[70.0,40.0,1.0,1.0,0.0,'water_liquid','polyethylene'],
        }[mode]
        out=list(defaults)
        any_typed=False
        for i in range(len(out)):
            edit=owner.source_form.inputs.get((kind,i))
            if edit is None:continue
            if hasattr(edit,'currentText'):
                txt=edit.currentText().strip()
                if txt:out[i]=txt
            else:
                txt=edit.text().strip().replace(',','.')
                try:
                    val=float(txt)
                    if val>=0:
                        out[i]=val
                        any_typed=True
                except ValueError:
                    pass
        return (out if any_typed else None), False


class LiveGeometryWidget(QGroupBox):
    """Embedded live axial cross-section preview with readable CAD quotes."""
    def __init__(self,owner,default_kind='Sample'):
        super().__init__('Live Axial Cross-Section && Quotes (mm)')
        self.owner=owner
        layout=QVBoxLayout(self);layout.setSpacing(4);layout.setContentsMargins(8,10,8,6)
        bar=QHBoxLayout();bar.setSpacing(8)
        lbl=QLabel('Preview:');lbl.setStyleSheet('font-weight:600;color:#334155;background:transparent;')
        bar.addWidget(lbl)
        self.source=QComboBox();self.source.addItems(['Sample','Standard','Detector Only'])
        self.source.setCurrentText(default_kind)
        bar.addWidget(self.source)
        bar.addStretch()
        enlarge=QPushButton('🔍 Full-Screen / All Quotes…')
        enlarge.setStyleSheet('background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;padding:3px 10px;font-weight:600;font-size:9pt;')
        enlarge.clicked.connect(self.open)
        bar.addWidget(enlarge)
        layout.addLayout(bar)

        self.figure=Figure(figsize=(4.8,2.9))
        self.canvas=FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumSize(320,190)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        layout.addWidget(self.canvas,1)

        self.info=QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet('background:#f8fafc;border:1px solid #cbd5e1;border-radius:4px;padding:4px 8px;color:#1e293b;font-size:8.5pt;')
        layout.addWidget(self.info)
        self.source.currentIndexChanged.connect(self.refresh)

    def set_kind(self,kind):
        idx=self.source.findText(kind,Qt.MatchFlag.MatchFixedString)
        if idx>=0 and self.source.currentIndex()!=idx:
            self.source.blockSignals(True)
            self.source.setCurrentIndex(idx)
            self.source.blockSignals(False)
        self.refresh()

    def refresh(self,*unused):
        if getattr(self.owner,'_building',False):return
        try:
            d,det_complete=_partial_detector_values(self.owner)
            sel=self.source.currentText()
            if sel=='Detector Only':
                s=None;kind_label='Detector'
            else:
                s,_=_partial_source_values(self.owner,sel.lower())
                kind_label=sel
            self.figure.clear()
            ax=self.figure.add_subplot(111)
            self.figure.subplots_adjust(left=0.10,right=0.98,bottom=0.16,top=0.86)
            summary=draw_geometry(ax,self.owner.current_mode(),d,s,kind_label,compact=True)
            if not det_complete:
                summary='ℹ Previewing with default placeholders for blank fields  |  '+summary
            self.info.setText(summary)
            self.canvas.draw_idle()
        except Exception as exc:
            self.info.setText('Geometry preview: '+str(exc))

    def open(self,*unused):
        dialog=GeometryDialog(self.owner)
        sel=self.source.currentText()
        if sel in ('Sample','Standard'):
            dialog.source.setCurrentText(sel)
        dialog.exec()


class GeometryDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('Detector & Source Axial Cross-Section — Full Quotes View')
        self.resize(1160,780);self.setMinimumSize(860,580)
        layout=QVBoxLayout(self);layout.setSpacing(8);layout.setContentsMargins(12,10,12,10)
        row=QHBoxLayout();row.setSpacing(10)
        lbl=QLabel('Inspect Geometry:');lbl.setStyleSheet("font-weight:600;color:#1e293b;")
        row.addWidget(lbl)
        self.source=QComboBox();self.source.addItems(['Sample','Standard','Detector Only']);row.addWidget(self.source)
        refresh=QPushButton('↻ Refresh from inputs');row.addWidget(refresh);row.addStretch();layout.addLayout(row)
        self.figure=Figure(figsize=(10.2,6.0));self.canvas=FigureCanvasQTAgg(self.figure);layout.addWidget(NavigationToolbar2QT(self.canvas,self));layout.addWidget(self.canvas,1)
        self.info=QLabel();self.info.setWordWrap(True)
        self.info.setStyleSheet("background:#f8fafc;border:1px solid #cbd5e1;border-radius:6px;padding:8px 12px;color:#1e293b;font-size:9pt;")
        layout.addWidget(self.info)
        self.source.currentIndexChanged.connect(self.refresh)
        refresh.clicked.connect(self.refresh)
        if hasattr(owner,'detector_form'):owner.detector_form.changed.connect(self.refresh)
        if hasattr(owner,'source_form'):owner.source_form.changed.connect(self.refresh)
        self.refresh()

    def refresh(self,*args):
        try:
            d,_=_partial_detector_values(self.owner)
            sel=self.source.currentText()
            if sel=='Detector Only':
                s=None;kind_label='Detector'
            else:
                s,_=_partial_source_values(self.owner,sel.lower())
                kind_label=sel
            self.figure.clear();ax=self.figure.add_subplot(111);self.figure.subplots_adjust(left=.08,right=.66,bottom=.10,top=.92)
            self.info.setText(draw_geometry(ax,self.owner.current_mode(),d,s,kind_label,compact=False));self.canvas.draw_idle()
        except Exception as exc:
            self.info.setText('Complete the detector inputs: '+str(exc))
