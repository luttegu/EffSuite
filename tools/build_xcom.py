"""Build the supplied XCOM 3.1 source, retaining its native arithmetic."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'src/effsuite/assets/xcom'


def build(compiler,target,extra=()):
    folder=ASSET/'bin'/target;folder.mkdir(parents=True,exist_ok=True)
    binary=folder/('xcom.exe' if target=='windows' else 'xcom')
    with tempfile.TemporaryDirectory() as temporary:
        source=Path(temporary)
        changes={}
        for original in [ASSET/'XCOM.FOR',*ASSET.glob('*.DAT')]:
            raw=original.read_bytes();compiled=raw.replace(b'\x1a',b'')
            (source/original.name).write_bytes(compiled)
            changes[original.name]={'original_sha256':sha256(raw).hexdigest(),'compiled_sha256':sha256(compiled).hexdigest()}
        command=[compiler,*extra,'-O2','-std=legacy','-fallow-argument-mismatch','-fno-fast-math','-ffp-contract=off','-fno-use-linker-plugin','-w']
        if target=='windows':command+=['-static']
        command+=['-I'+str(source),'-o',str(binary),str(source/'XCOM.FOR')]
        subprocess.run(command,check=True,capture_output=True,text=True)
    manifest={'platform':target,'command':command,'binary_sha256':sha256(binary.read_bytes()).hexdigest(),
              'source_changes':'DOS EOF control characters removed in temporary compiler inputs; numerical statements unchanged','input_hashes':changes}
    (folder/'build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',default='gfortran');p.add_argument('--target',choices=['windows','linux','macos'],required=True);p.add_argument('--compiler-arg',action='append',default=[]);a=p.parse_args();build(a.compiler,a.target,a.compiler_arg)
