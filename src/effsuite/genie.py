"""Genie CAM bridge through Windows PowerShell, including a 32-bit host.

The vendor CAM libraries remain responsible for proprietary file formats.
Writes use a private copy and are reopened before publication.
"""
from __future__ import annotations
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import base64

from .parallel_coincidence import CoincidenceError, _publish_new


def _call(action,path,updates=None):
    if os.name!="nt":raise CoincidenceError("Genie CAL/NLB/CTF access requires Windows and the original Genie CAM components; text calibration files work on other platforms")
    script=Path(__file__).parent/"assets/genie_cam.ps1"
    windir=Path(os.environ.get("WINDIR",r"C:\Windows"))
    hosts=[windir/"SysWOW64/WindowsPowerShell/v1.0/powershell.exe",windir/"System32/WindowsPowerShell/v1.0/powershell.exe"]
    request={"action":action,"path":str(Path(path).resolve()),"updates":updates or [],"progid":os.environ.get("EFFSUITE_CAM_PROGID","")}
    errors=[]
    script_argument=base64.b64encode(script.read_text(encoding="utf-8").encode("utf-16-le")).decode("ascii")
    initial_bytes=Path(path).read_bytes() if action.startswith("write_") else None
    for host in hosts:
        if not host.exists():continue
        try:
            if initial_bytes is not None:Path(path).write_bytes(initial_bytes)
            flags=getattr(subprocess,"CREATE_NO_WINDOW",0x08000000) if os.name=="nt" else 0
            done=subprocess.run([str(host),"-NoLogo","-NoProfile","-NonInteractive","-EncodedCommand",script_argument],
                                input=json.dumps(request).encode("utf-8"),capture_output=True,timeout=120,shell=False,creationflags=flags)
            obj=json.loads(done.stdout.decode("utf-8-sig"))
            if done.returncode==0 and obj.get("ok"):return obj
            errors.append(obj.get("error",done.stderr.decode(errors="replace")))
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:errors.append(str(exc))
    raise CoincidenceError("Genie CAM is unavailable or rejected the file: "+" | ".join(errors)[-3500:])


def read_cal(path):
    return [{"energy_keV":float(r["energy"]),"efficiency":float(r["efficiency"]),
             "u_rel_percent":100*float(r["uncertainty"])/float(r["efficiency"])} for r in _call("read_cal",path)["rows"]]


def read_library(path):return _call("read_nlb",path)["rows"]
def read_certificate(path):return _call("read_ctf",path)["rows"]


def match_factor(result,nuclide,energy):
    well=result.get("well_spatial_diagnostics")
    if well:
        if not well["convergence"]["passed"] or well["transport"]["probability_saturation_count"]:
            raise CoincidenceError("Well-model convergence/probability checks failed; Genie export is blocked")
        record=next((r for r in well["nuclides"] if r["nuclide"].upper()==nuclide.strip().upper()),None)
        if record and record["annihilation_pair_records"] and abs(energy-1022)<1:
            raise CoincidenceError("The 1022-keV pair sum-in channel is outside this backend's scope")
    nearby=[r for r in result["summing"] if r["nuclide"].upper()==nuclide.strip().upper() and abs(r["energy_keV"]-energy)<1.]
    if not nearby:raise CoincidenceError(f"No coincidence summing correction for {nuclide} at {energy:g} keV")
    distance=min(abs(r["energy_keV"]-energy) for r in nearby)
    closest=[r for r in nearby if abs(r["energy_keV"]-energy)==distance]
    if len(closest)!=1:
        if all(c["activity_multiplier"]==closest[0]["activity_multiplier"] for c in closest):
            row=closest[0]
        else:
            raise CoincidenceError(f"Ambiguous correction for {nuclide} at {energy:g} keV")
    else:
        row=closest[0]
    factor=row["activity_multiplier"]
    if row["status"]!="candidate" or factor is None or not math.isfinite(factor) or factor<=0:
        raise CoincidenceError(f"Unusable correction for {nuclide} at {energy:g} keV")
    return factor


def export_copy(source,destination,result,kind):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    if destination.exists() or source==destination:raise CoincidenceError("Choose a new output filename; source files are never overwritten")
    if kind not in {"cal","nlb","ctf"}:raise CoincidenceError("Unsupported Genie format")
    original=_call("read_"+kind,source)["rows"]
    updates=[]
    if kind=="cal":
        rows=result["efficiency"]
        if not rows or len(rows)!=len(original):raise CoincidenceError("CAL template must contain the same number of calibration points")
        for i,(old,new) in enumerate(zip(original,rows),1):
            updates.append({"entry":i,"energy":new["energy_keV"],"value":new["sample_efficiency"],
                            "uncertainty":new["sample_efficiency"]*new["sample_relative_uncertainty_percent_legacy"]/100})
    else:
        for old in original:
            key="abundance" if kind=="nlb" else "rate"
            try:
                factor=match_factor(result,str(old["nuclide"]),float(old["energy"]))
                value=float(old[key])/factor
            except CoincidenceError:
                value=float(old[key])
            if not math.isfinite(value) or value<0:raise CoincidenceError("Corrected Genie coefficient is nonfinite or negative")
            updates.append({"line":old.get("line"),"record":old["record"],"value":value})
    destination.parent.mkdir(parents=True,exist_ok=True)
    # The bridge never receives the source path for a write operation.
    with tempfile.TemporaryDirectory(prefix="effsuite-cam-",dir=destination.parent) as temporary:
        copy=Path(temporary)/source.name
        shutil.copyfile(source,copy)
        bridge_info=_call("write_"+kind,copy,updates)
        actual=_call("read_"+kind,copy)["rows"]
        if len(actual)!=len(original):raise CoincidenceError("Genie round-trip changed the line count")
        for i,(old,row,expected) in enumerate(zip(original,actual,updates)):
            quantity="efficiency" if kind=="cal" else "abundance" if kind=="nlb" else "rate"
            if not math.isclose(float(row[quantity]),expected["value"],rel_tol=2e-6,abs_tol=0.):
                raise CoincidenceError(f"Genie round-trip failed at line {i+1}")
            energy=expected["energy"] if kind=="cal" else old["energy"]
            if not math.isclose(float(row["energy"]),float(energy),rel_tol=2e-6,abs_tol=1e-6):raise CoincidenceError("Genie round-trip changed a line energy")
            if kind!="cal" and row["nuclide"]!=old["nuclide"]:raise CoincidenceError("Genie round-trip changed a nuclide")
            if kind=="cal" and not math.isclose(float(row["uncertainty"]),expected["uncertainty"],rel_tol=2e-6,abs_tol=0.):
                raise CoincidenceError("Genie round-trip changed efficiency uncertainty")
        _publish_new(destination,copy.read_bytes())
    return {"source_sha256":sha256(source.read_bytes()).hexdigest(),"output_sha256":sha256(destination.read_bytes()).hexdigest(),
            "roundtrip_verified":True,"format":kind,"lines":len(updates),
            "cam_host":{key:bridge_info.get(key) for key in ("progid","architecture","type_library","type_library_version")}}
