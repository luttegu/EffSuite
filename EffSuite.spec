from pathlib import Path
import sys
from importlib import metadata
root=Path(SPECPATH)

# Licence files of the bundled Python runtime and packages, collected into
# licenses/<package>/ so that the frozen build carries every notice.
BUNDLED_PACKAGES=['PySide6-Essentials','shiboken6','numpy','matplotlib','contourpy','cycler','fonttools',
                  'kiwisolver','pillow','pyparsing','python-dateutil','packaging','six','xlrd','pyinstaller']
def licence_datas():
    found=[]
    python_licence=Path(sys.base_prefix)/'LICENSE.txt'
    if python_licence.is_file():
        found.append((str(python_licence),'licenses/python'))
    for name in BUNDLED_PACKAGES:
        try:
            dist=metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        for file in dist.files or []:
            lower=file.name.lower()
            if lower.startswith(('licen','copying','notice','authors')) or 'license' in lower:
                path=Path(dist.locate_file(file))
                if path.is_file():
                    found.append((str(path),'licenses/'+name.lower()+'/'+str(Path(*file.parts[:-1])).replace('\\','/')))
    # The PySide6 and Shiboken6 wheels carry only Qt's commercial licence file:
    # add the LGPL-3.0 (with the GPL-3.0 it supplements) under which they are used.
    for name in ('pyside6-essentials','shiboken6'):
        found+=[(str(root/'third_party/LGPL-3.txt'),'licenses/'+name),
                (str(root/'third_party/GPL-3.txt'),'licenses/'+name)]
    return found

datas=[(str(root/'src/effsuite/assets'),'effsuite/assets'),
       (str(root/'third_party'),'third_party'),
       (str(root/'LICENSE'),'.'),
       *licence_datas(),
       (str(root/'THIRD_PARTY_NOTICES.md'),'.'),
       (str(root/'README.md'),'.'),(str(root/'RELEASE_NOTES.md'),'.'),
       *[(str(path),'docs') for path in sorted((root/'docs').glob('*.md'))],
       (str(root/'src/effsuite/assets/templates/Material_Composition.xlsx'),'.')]
common=dict(pathex=[str(root/'src')],binaries=[],datas=datas,hiddenimports=['effsuite.gui','matplotlib.backends.backend_qtagg','matplotlib.backends.backend_svg'],hookspath=[],runtime_hooks=[],excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtPdf'])
cli=Analysis([str(root/'tools/entry_cli.py')],**common)
gui=Analysis([str(root/'tools/entry_gui.py')],**common)
cli_pyz=PYZ(cli.pure)
gui_pyz=PYZ(gui.pure)
icon_file=str(root/'src/effsuite/assets/icon.ico')
cli_exe=EXE(cli_pyz,cli.scripts,[],exclude_binaries=True,name='EffSuite_CLI',console=True,icon=icon_file)
gui_exe=EXE(gui_pyz,gui.scripts,[],exclude_binaries=True,name='EffSuite_GUI',console=False,icon=icon_file)
collection=COLLECT(cli_exe,gui_exe,cli.binaries,cli.datas,gui.binaries,gui.datas,name='EffSuite')
