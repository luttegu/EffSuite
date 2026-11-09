"""Install into an app-local environment using precisely the invoking Python."""
from __future__ import annotations
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parents[1]


def main():
    print("Selected interpreter:",sys.executable,flush=True)
    print("Version:",sys.version,flush=True)
    if sys.version_info<(3,11) or struct.calcsize("P")!=8:
        raise SystemExit("Use your selected 64-bit Python 3.11 or later. No different interpreter will be selected automatically.")
    environment=ROOT/".venv";python=environment/("Scripts/python.exe" if sys.platform=="win32" else "bin/python")
    if python.exists():
        current=subprocess.check_output([str(python),"-c","import json,sys;print(json.dumps(list(sys.version_info[:3])))"],text=True)
        if json.loads(current)!=list(sys.version_info[:3]):
            raise SystemExit("The existing .venv uses a different Python version. Use a new extraction folder or explicitly remove that environment before setting up again.")
    else:venv.EnvBuilder(with_pip=True).create(environment)
    subprocess.run([str(python),"-m","pip","install","-e",str(ROOT)+"[desktop]"],check=True,cwd=ROOT)
    if sys.platform!="win32":
        for path in (ROOT/"src/effsuite/assets/engines").glob("*/bin/"+("macos" if sys.platform=="darwin" else "linux")+"/*"):
            if path.is_file() and not path.suffix:path.chmod(path.stat().st_mode|0o111)
        for path in (ROOT/"src/effsuite/assets/xcom/bin"/("macos" if sys.platform=="darwin" else "linux")).glob("*"):
            if path.is_file() and not path.suffix:path.chmod(path.stat().st_mode|0o111)
    subprocess.run([str(python),"-m","effsuite.app_cli","doctor"],check=True)
    print("Setup complete. Open Start_GUI.bat or use CLI.bat run your_project.json.")

if __name__=="__main__":main()
