from pathlib import Path
root=Path(SPECPATH)
datas=[(str(root/'src/effsuite/assets'),'effsuite/assets'),
       (str(root/'third_party'),'third_party'),
       (str(root/'THIRD_PARTY_NOTICES.md'),'.'),
       (str(root/'README.md'),'.'),(str(root/'USER_GUIDE.md'),'.'),
       (str(root/'MATERIALS.md'),'.'),
       (str(root/'src/effsuite/assets/templates/Material_Composition.xlsx'),'.')]
common=dict(pathex=[str(root/'src')],binaries=[],datas=datas,hiddenimports=['effsuite.gui','matplotlib.backends.backend_qtagg'],hookspath=[],runtime_hooks=[],excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtPdf'])
cli=Analysis([str(root/'tools/entry_cli.py')],**common)
gui=Analysis([str(root/'tools/entry_gui.py')],**common)
cli_pyz=PYZ(cli.pure)
gui_pyz=PYZ(gui.pure)
cli_exe=EXE(cli_pyz,cli.scripts,[],exclude_binaries=True,name='EffSuite_CLI',console=True)
gui_exe=EXE(gui_pyz,gui.scripts,[],exclude_binaries=True,name='EffSuite_GUI',console=False)
collection=COLLECT(cli_exe,gui_exe,cli.binaries,cli.datas,gui.binaries,gui.datas,name='EffSuite')
