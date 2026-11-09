"""Original Material.xls composition contract and isolated XCOM generation."""
from __future__ import annotations
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
import zipfile

from .model_io import ASSETS,COMMON_DATA,mode_name
from .parallel_coincidence import CoincidenceError,CalculationCancelled,_publish_new,_terminate

XCOM=Path(__file__).parent/'assets/xcom'
TEMPLATE=Path(__file__).parent/'assets/templates/Material_Composition.xlsx'
ELEMENTS=set('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm'.split())


def finite(value,label):
    try:number=float(value)
    except (TypeError,ValueError) as exc:raise CoincidenceError(label+': enter a finite number') from exc
    if isinstance(value,bool) or not math.isfinite(number):raise CoincidenceError(label+': enter a finite number')
    return number


def validate_composition(definition):
    if not isinstance(definition,dict):raise CoincidenceError('Material definition must be a JSON object')
    if definition.get('schema_version',1)!=1:raise CoincidenceError('Unsupported material definition schema')
    name=str(definition.get('name','')).strip()
    if not name or len(name)>60 or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name.endswith(('.', ' ')) or name in {'.','..'}:
        raise CoincidenceError('Material name: use 1–60 filename-safe characters')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise CoincidenceError('Material name is reserved by Windows')
    try:name.encode('cp1252')
    except UnicodeEncodeError as exc:raise CoincidenceError('Material name must use characters supported by the original Windows text format') from exc
    density=finite(definition.get('density_g_cm3'),'Density [g/cm³]')
    if density<=0:raise CoincidenceError('Density [g/cm³] must be positive; it is an input, not calculated from the mixture')
    rows=definition.get('components')
    if not isinstance(rows,list) or not 1<=len(rows)<=10:raise CoincidenceError('Enter 1–10 compounds, as in the original Material workbook')
    result=[];seen=set()
    for row in rows:
        if not isinstance(row,dict):raise CoincidenceError('Each component must contain formula and weight fields')
        formula=str(row.get('formula','')).strip()
        tokens=list(re.finditer(r'([A-Z][a-z]?)([0-9]*)',formula))
        if not formula or len(formula)>70 or ''.join(t.group() for t in tokens)!=formula or any(t[1] not in ELEMENTS or (t[2] and not 1<=int(t[2])<=100000) for t in tokens):
            raise CoincidenceError(f'Invalid XCOM formula {formula!r}; use flat formulas such as H2O, NaCl, CaO, without parentheses or isotope labels')
        if formula in seen:raise CoincidenceError('Duplicate compound: '+formula)
        seen.add(formula);weight=finite(row.get('weight'),'Weight for '+formula)
        if weight<0:raise CoincidenceError('Compound weights must be nonnegative')
        result.append({'formula':formula,'weight':weight})
    try:total=math.fsum(r['weight'] for r in result)
    except OverflowError as exc:raise CoincidenceError('Total weight is too large; scale all relative weights by a common factor') from exc
    if not math.isfinite(total) or total<=0:raise CoincidenceError('At least one compound must have a positive weight')
    return {'schema_version':1,'name':name,'density_g_cm3':density,'components':result}


def composition_bytes(definition):
    d=validate_composition(definition)
    return ('\r\n'.join([format(d['density_g_cm3'],'.17g'),*[value for row in d['components'] for value in (row['formula'],format(row['weight'],'.17g'))]])+'\r\n').encode('cp1252')


def _xlsx_inputs(path):
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist())>20_000_000:raise CoincidenceError('Material workbook is too large')
        workbook=ET.fromstring(z.read('xl/workbook.xml'))
        sheet=next((s for s in workbook.findall('m:sheets/m:sheet',ns) if s.attrib['name']=='Material'),None)
        if sheet is None:raise CoincidenceError('The workbook needs a Material sheet in the supplied template layout')
        relid=sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target=next(r.attrib['Target'] for r in rels if r.attrib['Id']==relid)
        target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
        cells={}
        for c in ET.fromstring(z.read(target)).findall('.//m:sheetData/m:row/m:c',ns):
            address=c.attrib['r']
            if address not in {'D4','D20',*[f'{col}{r}' for col in 'CD' for r in range(9,19)]}:continue
            if c.find('m:f',ns) is not None:raise CoincidenceError(address+': composition inputs must be entered as values, not formulas; use Paste Values')
            value=c.find('m:v',ns);kind=c.attrib.get('t')
            if kind=='s':value=shared[int(value.text)]
            elif kind=='inlineStr':value=''.join(c.find('m:is',ns).itertext())
            else:value=value.text if value is not None else ''
            cells[address]=value
        return cells


def load_composition(path,name=None):
    path=Path(path)
    try:
        if path.suffix.lower()=='.json':d=json.loads(path.read_text(encoding='utf-8-sig'))
        elif path.suffix.lower() in {'.xlsx','.xlsm','.xls'}:
            if path.suffix.lower()=='.xls':
                import xlrd
                sheet=xlrd.open_workbook(str(path)).sheet_by_name('Material')
                cells={f'{col}{r}':sheet.cell_value(r-1,ord(col)-65) if r<=sheet.nrows and ord(col)-65<sheet.ncols else '' for col in 'CD' for r in [4,20,*range(9,19)]}
            else:cells=_xlsx_inputs(path)
            rows=[]
            for r in range(9,19):
                formula=cells.get(f'C{r}','');weight=cells.get(f'D{r}','')
                if formula=='' and weight=='':continue
                rows.append({'formula':formula,'weight':weight})
            d={'name':cells.get('D4') or path.stem,'density_g_cm3':cells.get('D20'),'components':rows}
        else:
            lines=[v.strip() for v in path.read_bytes().decode('cp1252').splitlines() if v.strip()]
            if not lines or len(lines)%2!=1:raise CoincidenceError('Original composition format: density, then alternating formula and weight lines')
            d={'name':path.stem,'density_g_cm3':lines[0],'components':[{'formula':lines[i],'weight':lines[i+1]} for i in range(1,len(lines),2)]}
        if name:d['name']=name
        return validate_composition(d)
    except (OSError,ValueError,KeyError,zipfile.BadZipFile,ET.ParseError,StopIteration) as exc:raise CoincidenceError('Cannot read material definition: '+str(exc)) from exc


def save_definition(path,definition):
    _publish_new(Path(path),(json.dumps(validate_composition(definition),indent=2)+'\n').encode())


def attenuation_rows(raw):
    result=[]
    for line in raw.decode('cp1252').splitlines():
        # Native XCOM table uses a six-character absorption-edge prefix.
        tokens=line[6:].split()
        if len(tokens)!=8:continue
        try:row=[float(v.replace('D','E')) for v in tokens]
        except ValueError:continue
        if not all(math.isfinite(v) and v>=0 for v in row) or row[0]<=0:raise CoincidenceError('XCOM produced invalid attenuation coefficients')
        if result and row[0]<result[-1][0]:raise CoincidenceError('XCOM energy grid is not monotone')
        result.append(row)
    if len(result)<80 or result[0][0]>.00101 or result[-1][0]<100000:raise CoincidenceError('XCOM did not produce a complete standard-grid attenuation table')
    return result


def generate_attenuation(definition,*,cancel=None,timeout=60,progress=None):
    d=validate_composition(definition);stop=cancel if cancel is not None else threading.Event()
    if stop.is_set():raise CalculationCancelled('Material calculation cancelled')
    target='windows' if os.name=='nt' else 'macos' if sys.platform=='darwin' else 'linux'
    exe=XCOM/'bin'/target/('xcom.exe' if os.name=='nt' else 'xcom')
    if not exe.is_file():raise CoincidenceError('Build XCOM for this platform with tools/build_xcom.py')
    # Same input choices as the original Material.xls Save action.
    input_text='\n'.join([d['name'],'4',str(len(d['components'])),*[value for row in d['components'] for value in (row['formula'],format(row['weight'],'.17g'))],'1','1','material.txt','1'])+'\n'
    if progress:progress('XCOM: generating attenuation table')
    with tempfile.TemporaryDirectory(prefix='effsuite-xcom-') as temp:
        work=Path(temp)
        for path in XCOM.glob('MDATX3.*'):
            if stop.is_set():raise CalculationCancelled('Material calculation cancelled')
            shutil.copyfile(path,work/path.name)
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0x08000000) if os.name=='nt' else 0
        process=subprocess.Popen([str(exe.resolve())],cwd=work,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=False,creationflags=flags)
        began=time.monotonic()
        try:
            first=True
            while True:
                if stop.is_set():raise CalculationCancelled('Material calculation cancelled')
                if time.monotonic()-began>timeout:raise CoincidenceError('XCOM time limit exceeded')
                try:
                    log=process.communicate(input=input_text.encode('cp1252') if first else None,timeout=.1)[0];break
                except subprocess.TimeoutExpired:first=False
        finally:_terminate(process)
        if process.returncode or not (work/'material.txt').is_file():raise CoincidenceError('XCOM failed: '+log.decode('cp1252',errors='replace')[-2000:])
        raw=(work/'material.txt').read_bytes();rows=attenuation_rows(raw)
    metadata={'xcom_version':'3.1 supplied with original EFFTRAN','executable_sha256':sha256(exe.read_bytes()).hexdigest(),
              'data_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(XCOM.glob('MDATX3.*'))},
              'input_text':input_text,'row_count':len(rows),'output_sha256':sha256(raw).hexdigest()}
    return raw,metadata


def default_library(geometry=None):return Path.home()/'Documents/EffSuite/Data'


def create_material(definition,library=None,*,geometry='cylindrical',base_directory=None,cancel=None,progress=None,overwrite=False):
    d=validate_composition(definition)
    if library is None:library=default_library(geometry)
    library=Path(library).expanduser().resolve()
    if library.exists() and not all((library/p).is_dir() for p in ('Composition','Material')):raise CoincidenceError('The data folder must contain Composition and Material directories')
    if not overwrite and library.exists() and any((library/p/(d['name']+'.txt')).exists() for p in ('Composition','Material')):raise CoincidenceError('Material name already exists; save under a new name to preserve the original')
    raw,metadata=generate_attenuation(d,cancel=cancel,progress=progress)
    try:
        library.parent.mkdir(parents=True,exist_ok=True)
    except (OSError, PermissionError):
        pass
    with tempfile.TemporaryDirectory(prefix='effsuite-material-') as temp:
        staged=Path(temp)/'library'
        if not library.exists():
            base=Path(base_directory) if base_directory else COMMON_DATA;staged.mkdir()
            for folder in ('Composition','Material','Decay_Data','Material_Metadata'):
                if (base/folder).is_dir():shutil.copytree(base/folder,staged/folder)
            for name in ('param.txt','zzaa.txt','kordaten.txt'):
                if (base/name).is_file():shutil.copyfile(base/name,staged/name)
            (staged/'Composition').mkdir(parents=True,exist_ok=True)
            (staged/'Material').mkdir(parents=True,exist_ok=True)
            if not all((staged/p).is_dir() for p in ('Composition','Material')):raise CoincidenceError('Base data folder is incomplete')
            target=staged
        else:target=library
        if not overwrite and any((target/p/(d['name']+'.txt')).exists() for p in ('Composition','Material')):raise CoincidenceError('This name already exists in the base library; choose a new material name')
        paths={p:target/p/(d['name']+suffix) for p,suffix in [('Material','.txt'),('Composition','.txt'),('Material_Metadata','.json')]}
        try:
            paths['Material_Metadata'].parent.mkdir(exist_ok=True)
        except (OSError, PermissionError):
            pass
        published=[]
        try:
            if cancel is not None and cancel.is_set():raise CalculationCancelled('Material calculation cancelled')
            for key,data in [('Material',raw),('Composition',composition_bytes(d)),('Material_Metadata',(json.dumps({'definition':d,'generation':metadata},indent=2)+'\n').encode())]:
                if overwrite and paths[key].exists():
                    paths[key].write_bytes(data)
                else:
                    _publish_new(paths[key],data)
                published.append(paths[key])
            if target==staged:
                try:
                    shutil.copytree(staged,library,dirs_exist_ok=True)
                    shutil.rmtree(staged,ignore_errors=True)
                except (OSError, PermissionError):
                    # Destination library is read-only; keep files staged in user cache or temp
                    pass
        except Exception:
            for path in published:
                if not overwrite:path.unlink(missing_ok=True)
            raise
    weights=[r['weight'] for r in d['components']];total=math.fsum(weights)
    return {'definition':d,'normalized_mass_fractions':[w/total for w in weights],'data_directory':str(library),
            'composition_file':str(library/'Composition'/(d['name']+'.txt')),'attenuation_file':str(library/'Material'/(d['name']+'.txt')),'generation':metadata}
