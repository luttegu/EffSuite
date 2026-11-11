"""Complete calculation workflows shared by the original-style GUI and easy CLI."""
from __future__ import annotations
import csv
from datetime import datetime
from hashlib import sha256
import html
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

from .model_io import ASSETS, COMMON_DATA, MODES, mode_name, model_bytes, validate_model, validate_calibration, normalize_nuclides
from .parallel_coincidence import CoincidenceError, CalculationCancelled, SharedInputs, calculate_parallel, split_library, _terminate
from . import __version__ as VERSION
PREP=("mine","energy","total","scatter","buildup","eta","ptt","efficiency")


def validate_project(project):
    if project.get("schema_version")!=1:raise CoincidenceError("Unsupported project file version")
    out=json.loads(json.dumps(project,allow_nan=False))
    mode=mode_name(out.get("geometry","cylindrical"));out["geometry"]=mode
    data_dir=out.get("data_directory")
    out["detector"]=validate_model(mode,"detector",out.get("detector",[]),data_directory=data_dir)
    out["sample"]=validate_model(mode,"sample",out.get("sample",[]),data_directory=data_dir)
    task=out.get("task","both")
    if task not in {"transfer","summing","both"}:raise CoincidenceError("Choose efficiency transfer, summing, or both")
    if task in {"transfer","both"}:
        out["standard"]=validate_model(mode,"standard",out.get("standard",[]),data_directory=data_dir)
        out["calibration"]=validate_calibration(out.get("calibration",[]))
    if mode=="well":
        for kind in ("sample","standard"):
            if kind in out and out[kind][0]>out["detector"][3]:
                raise CoincidenceError(f"The {kind} container diameter ({out[kind][0]:g} mm) must fit into the well diameter ({out['detector'][3]:g} mm)")
    names=out.get("nuclides",[])
    if not isinstance(names,list) or not all(isinstance(n,str) for n in names):raise CoincidenceError("Nuclides must be a list")
    out["nuclides"]=normalize_nuclides(names)
    if task in {"summing","both"} and not out["nuclides"]:raise CoincidenceError("Select at least one nuclide")
    workers=out.get("workers",0)
    if type(workers)is not int or not 0<=workers<=64:raise CoincidenceError("Workers: enter 0 (automatic) or 1 to 64")
    out["workers"]=workers
    timeout=out.get("timeout_seconds",300.)
    if isinstance(timeout,bool) or not math.isfinite(float(timeout)) or float(timeout)<=0:raise CoincidenceError("Timeout must be positive")
    out["timeout_seconds"]=float(timeout)
    return out


def _safe_py_sha256(filename: str) -> str:
    path = Path(__file__).parent / filename
    try:
        if path.is_file():
            return sha256(path.read_bytes()).hexdigest()
        pyc = path.with_suffix(".pyc")
        if pyc.is_file():
            return sha256(pyc.read_bytes()).hexdigest()
    except Exception:
        pass
    return sha256(filename.encode()).hexdigest()


def engine_folder(mode):
    target="windows" if os.name=="nt" else "macos" if sys.platform=="darwin" else "linux"
    return ASSETS/mode/"bin"/target


def _stage(stage,mode,work,stop,timeout,progress,provenance):
    if stop.is_set():raise CalculationCancelled("Calculation cancelled")
    exe=engine_folder(mode)/(stage+(".exe" if os.name=="nt" else ""))
    if not exe.is_file():raise CoincidenceError(f"Missing {MODES[mode]} engine '{stage}'. Run tools/build_engines.py for this platform.")
    if progress:progress(f"{MODES[mode]}: {stage}")
    provenance[stage]=sha256(exe.read_bytes()).hexdigest()
    with (work/(stage+".log")).open("wb") as log:
        flags=getattr(subprocess,"CREATE_NO_WINDOW",0x08000000) if os.name=="nt" else 0
        process=subprocess.Popen([str(exe.resolve())],cwd=work,stdin=subprocess.DEVNULL,stdout=log,stderr=log,shell=False,creationflags=flags)
        started=time.monotonic()
        try:
            while process.poll() is None:
                if stop.is_set():raise CalculationCancelled("Calculation cancelled")
                if time.monotonic()-started>timeout:raise CoincidenceError(f"{stage}: time limit exceeded")
                try:process.wait(timeout=.05)
                except subprocess.TimeoutExpired:pass
        finally:_terminate(process)
    if process.returncode:
        diagnostic=(work/(stage+".log")).read_bytes()[-4000:].decode("utf-8",errors="replace")
        raise CoincidenceError(f"{stage} failed (exit {process.returncode}): {diagnostic}")


def _prepare_folder(mode,project,destination,source_kind):
    destination.mkdir()
    asset=Path(project["data_directory"]).expanduser().resolve() if project.get("data_directory") else None
    from .paths import get_data_dir
    user_default=get_data_dir()
    if not asset and user_default and (user_default/"Composition").is_dir():
        asset=user_default
    engine_dir=asset if (asset and (asset/"Detector").is_dir()) else ASSETS/mode
    for name in ("Material","Composition"):
        shutil.copytree(COMMON_DATA/name,destination/name)
    if asset:
        for name in ("Material","Composition"):
            if (asset/name).is_dir():
                shutil.copytree(asset/name,destination/name,dirs_exist_ok=True)
    for name in ("zzaa.txt","param.txt","kordaten.txt"):
        if (engine_dir/name).is_file():shutil.copyfile(engine_dir/name,destination/name)
        elif (ASSETS/mode/name).is_file():shutil.copyfile(ASSETS/mode/name,destination/name)
    if not (destination/"param.txt").exists():(destination/"param.txt").write_text("10.\n")
    det_bytes=model_bytes(mode,"detector",project["detector"])
    src_bytes=model_bytes(mode,source_kind,project[source_kind])
    (destination/"detector.txt").write_bytes(det_bytes)
    (destination/"det.txt").write_bytes(det_bytes)
    (destination/"source.txt").write_bytes(src_bytes)
    (destination/"src.txt").write_bytes(src_bytes)
    for name in ("sample","standard"):
        if project.get(name):(destination/(name+".txt")).write_bytes(model_bytes(mode,name,project[name]))
    # Validate every named material before invoking any numerical executable.
    models=[project["detector"],project[source_kind]]
    if source_kind=="sample" and project.get("standard"):models.append(project["standard"])
    materials=[str(value) for definition in models for value in definition if isinstance(value,str)]
    for material in materials:
        comp_file = destination/"Composition"/(material+".txt")
        mat_file = destination/"Material"/(material+".txt")
        if not comp_file.is_file():
            raise CoincidenceError(f"Material '{material}' is missing from {MODES[mode]} Composition")
        if not mat_file.is_file():
            # Automatically generate the attenuation table with XCOM from Composition
            try:
                from .materials import load_composition, generate_attenuation
                comp_def = load_composition(comp_file, name=material)
                raw_mat, _ = generate_attenuation(comp_def)
                mat_file.write_bytes(raw_mat)
                # Persist to data library if configured, or common assets
                persist_target = asset if asset and (asset/"Material").is_dir() else COMMON_DATA
                if (persist_target/"Material").is_dir():
                    try:
                        (persist_target/"Material"/(material+".txt")).write_bytes(raw_mat)
                    except Exception:
                        pass
            except Exception as exc:
                raise CoincidenceError(f"Material '{material}' is missing from Material and automatic generation failed: {exc}")


def _table(path,columns):
    rows=[]
    for line in path.read_text().splitlines():
        vals=[float(token.replace("D","E")) for token in line.split()]
        if len(vals)!=columns or not all(math.isfinite(v) for v in vals):raise CoincidenceError(f"Invalid result table: {path.name}")
        rows.append(vals)
    if not rows:raise CoincidenceError(f"Empty result: {path.name}")
    return rows


def _write_outputs(root,result):
    (root/"results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    with (root/"efficiency.csv").open("w",newline="",encoding="utf-8") as f:
        fields=["energy_keV","standard_efficiency","sample_efficiency","transfer_factor","sample_relative_uncertainty_percent_legacy"]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in result["efficiency"]:writer.writerow({k:row[k] for k in fields})
    with (root/"summing.csv").open("w",newline="",encoding="utf-8") as f:
        fields=["nuclide","energy_keV","activity_multiplier","status"]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:row[k] for k in fields} for row in result["summing"])
    (root/"report.html").write_text(render_report(result),encoding="utf-8")


def render_report(result):
    esc=html.escape
    rows="".join("<tr>"+"".join(f"<td>{esc(str(row[k]))}</td>" for k in ["energy_keV","standard_efficiency","sample_efficiency","transfer_factor"])+"</tr>" for row in result["efficiency"])
    sums="".join("<tr>"+"".join(f"<td>{esc(str(row[k]))}</td>" for k in ["nuclide","energy_keV","activity_multiplier","status"])+"</tr>" for row in result["summing"])
    exports_html=""
    if result.get("genie_exports"):
        exp_rows="".join(
            f"<tr><td style='text-align:left'><b>{esc(str(info.get('software','Genie')))}</b></td>"
            f"<td style='text-align:left'><code>{esc(str(info.get('file','')))}</code></td>"
            f"<td><code>.{esc(str(info.get('format',k)).upper())}</code></td>"
            f"<td>{esc(str(info.get('lines','')))}</td>"
            f"<td>{'Yes' if info.get('roundtrip_verified') else 'No'}</td></tr>"
            for k,info in result["genie_exports"].items() if isinstance(info,dict)
        )
        if exp_rows:
            exports_html=(
                "<h2>Exported Spectrometry Files (Genie 2000 / GammaVision)</h2>"
                "<table><tr><th style='text-align:left'>Target Software</th><th style='text-align:left'>Exported File</th><th>Format</th><th>Lines / Points</th><th>Round-Trip Verified</th></tr>"
                f"{exp_rows}</table>"
            )
    graphic=""
    try:
        from matplotlib.figure import Figure
        figure=Figure(figsize=(9,3.5),tight_layout=True);axis=figure.add_subplot(111)
        if result["efficiency"]:
            points=result["efficiency"]
            for key,label in [("standard_efficiency","Standard"),("sample_efficiency","Sample")]:
                axis.loglog([r["energy_keV"] for r in points],[r[key] for r in points],"o-",label=label,markersize=3)
            axis.set_ylabel("Full-energy efficiency");axis.legend()
        else:
            for name in dict.fromkeys(r["nuclide"] for r in result["summing"]):
                points=[r for r in result["summing"] if r["nuclide"]==name and r["activity_multiplier"] is not None]
                if points:axis.scatter([r["energy_keV"] for r in points],[r["activity_multiplier"] for r in points],s=12,label=name)
            axis.set_yscale("log");axis.axhline(1,color="gray",linewidth=.8);axis.set_ylabel("Activity multiplier");axis.legend()
        axis.set_xlabel("Energy [keV]");axis.grid(True,which="both",alpha=.2)
        stream=io.StringIO();figure.savefig(stream,format="svg");text=stream.getvalue();graphic=text[text.index("<svg"):]
    except ImportError:pass
    return f'''<!doctype html><html><meta charset="utf-8"><title>EffSuite result</title><style>body{{font:16px Georgia,serif;max-width:1100px;margin:40px auto;color:#182532}}table{{border-collapse:collapse;width:100%;margin:20px 0}}td,th{{border:1px solid #ccd3d9;padding:7px;text-align:right}}th{{background:#edf2f6}}.notice{{background:#e8f4fd;border-left:4px solid #2563eb;padding:14px}}svg{{max-width:100%;height:auto}}</style><h1>{esc(result['engine_name'])} — calculation result</h1><p class="notice">Beta build v{VERSION}. Experimental gamma spectrometry efficiency transfer and coincidence summing engine. Factors multiply activity; correction below one is permitted for summing-in.</p><p>Job: {esc(result['job_id'])}<br>Created: {esc(result['created'])}</p>{graphic}{exports_html}<h2>Efficiency transfer</h2><table><tr><th>E / keV</th><th>Standard efficiency</th><th>Sample efficiency</th><th>Transfer factor</th></tr>{rows}</table><h2>True coincidence summing</h2><table><tr><th>Nuclide</th><th>E / keV</th><th>Activity multiplier</th><th>Status</th></tr>{sums}</table><p>Original inputs, intermediate files and engine hashes are included with results.json. Legacy uncertainty percentages preserve the original transfer routine's assumptions; they are not a complete uncertainty budget.</p></html>'''


def run_project(project,output:Path,*,cancel=None,progress=None):
    project=validate_project(project);mode=project["geometry"]
    output=Path(output).expanduser().resolve()
    if output.exists():raise CoincidenceError("Output folder already exists; choose a new name")
    output.parent.mkdir(parents=True,exist_ok=True)
    stop=cancel if cancel is not None else threading.Event()
    work=Path(tempfile.mkdtemp(prefix=".effsuite-job-",dir=output.parent))
    try:
        (work/"project.effsuite.json").write_text(json.dumps(project,indent=2)+"\n")
        result={"schema_version":1,"application_version":VERSION,"job_id":uuid4().hex[:12],
                "created":datetime.now().astimezone().isoformat(),"geometry":mode,"engine_name":MODES[mode],
                "qualification":"beta_build","project":project,
                "efficiency":[],"summing":[],"engine_sha256":{},"warnings":[],"output_directory":str(output)}
        dataset=Path(project["data_directory"]).expanduser().resolve() if project.get("data_directory") else None
        common_dir=dataset if (dataset and (dataset/"Composition").is_dir()) else COMMON_DATA
        engine_dir=dataset if (dataset and (dataset/"Detector").is_dir()) else ASSETS/mode
        result["scientific_data_directory"]=str(dataset or common_dir)
        result["scientific_data_sha256"]={str(path.relative_to(common_dir)):sha256(path.read_bytes()).hexdigest()
                                         for directory in ("Material","Composition") for path in sorted((common_dir/directory).glob("*.txt"))}
        result["scientific_data_sha256"].update({name:sha256((engine_dir/name).read_bytes()).hexdigest()
                                               for name in ("zzaa.txt","param.txt","kordaten.txt") if (engine_dir/name).is_file()})
        if project["task"] in {"transfer","both"}:
            folder=work/"transfer";_prepare_folder(mode,project,folder,"sample")
            raw="".join(f"{row['energy_keV']:.17g} {row['efficiency']:.17g} {row['u_rel_percent']:.17g}\n" for row in project["calibration"])
            (folder/"reference.txt").write_text(raw)
            if mode=="well":
                import numpy as np
                from .spatial_summing import well_peak_efficiencies, _crystal_zz_aa
                energies=np.asarray([row["energy_keV"] for row in project["calibration"]],dtype=float)
                zz_aa=_crystal_zz_aa(folder,folder,project["detector"][5])
                if progress:progress("WEFFTRAN: ray-traced efficiency transfer (standard)")
                standard=well_peak_efficiencies(folder,project["detector"],project["standard"],energies,cancel=stop,zz_aa=zz_aa,workers=project["workers"])
                if progress:progress("WEFFTRAN: ray-traced efficiency transfer (sample)")
                sample=well_peak_efficiencies(folder,project["detector"],project["sample"],energies,cancel=stop,zz_aa=zz_aa,workers=project["workers"])
                if np.any(standard<=0) or np.any(~np.isfinite(sample/standard)):raise CoincidenceError("Standard well efficiency is zero")
                transferred=[[row["energy_keV"],row["efficiency"]*float(ratio),math.sqrt(row["u_rel_percent"]**2+.5**2+.5**2)]
                             for row,ratio in zip(project["calibration"],sample/standard)]
                (folder/"efficiency.txt").write_text("".join(f"{e:.5e} {v:.5e} {u:.5e}\n" for e,v,u in transferred))
                result["engine_sha256"]["well_transfer"] = _safe_py_sha256("spatial_summing.py")
            else:
                for kind in ("sample","standard"):
                    src_bytes=model_bytes(mode,kind,project[kind])
                    (folder/"source.txt").write_bytes(src_bytes)
                    (folder/"src.txt").write_bytes(src_bytes)
                    (folder/"total.txt").unlink(missing_ok=True)
                    _stage("total",mode,folder,stop,project["timeout_seconds"],progress,result["engine_sha256"])
                    shutil.copyfile(folder/"total.txt",folder/(kind+"-efficiency.txt"))
                _stage("transfer",mode,folder,stop,project["timeout_seconds"],progress,result["engine_sha256"])
                transferred=_table(folder/"efficiency.txt",3)
            if len(transferred)!=len(project["calibration"]):raise CoincidenceError("Transferred calibration line count changed")
            for ref,new in zip(project["calibration"],transferred):
                if new[1]<=0 or new[1]>1:raise CoincidenceError("Transferred efficiency is outside zero to one")
                if new[2]<0:raise CoincidenceError("Transferred relative uncertainty is negative")
                if not math.isclose(ref["energy_keV"],new[0],rel_tol=1e-4,abs_tol=0.05):
                    raise CoincidenceError("Transferred calibration energies changed beyond native single-precision print resolution")
                result["efficiency"].append({"energy_keV":ref["energy_keV"],"standard_efficiency":ref["efficiency"],
                    "sample_efficiency":new[1],"transfer_factor":new[1]/ref["efficiency"],
                    "sample_relative_uncertainty_percent_legacy":new[2]})

            result["warnings"].append("Transfer uncertainties retain the original hard-coded 0.5% standard/sample contributions; no complete uncertainty budget is claimed")
        if project["task"] in {"summing","both"}:
            folder=work/"summing";_prepare_folder(mode,project,folder,"sample")
            if mode!="well":
                for stage in PREP:_stage(stage,mode,folder,stop,project["timeout_seconds"],progress,result["engine_sha256"])
            raw_summing=[]
            if mode=="well":
                from .well_spatial import calculate_spatial
                report=calculate_spatial(common_dir,folder,tuple(project["nuclides"]),workers=project["workers"],
                                         verify_serial=project.get("verify_serial",False),
                                         check_convergence=project.get("check_convergence",True),
                                         rtol=project.get("numerical_rtol",.01),progress=progress,cancel=stop)
                result["well_spatial_diagnostics"]=report
                for item in report["nuclides"]:
                    for row in item["corrections"]:
                        raw_summing.append({"nuclide":item["nuclide"],"energy_keV":row["energy_kev"],
                            "activity_multiplier":row["factor"],"status":row["status"]})
                if not report["convergence"]["passed"]:result["warnings"].append("Some well correction factors failed numerical refinement; do not export them to Genie or GammaVision")
                if report.get("missing_nuclides"):result["warnings"].append("Decay data not available for: "+", ".join(report["missing_nuclides"])+". These nuclides remain uncorrected (* in table).")
            else:
                binary=engine_folder(mode)/("coincidence.exe" if os.name=="nt" else "coincidence")
                report=calculate_parallel(SharedInputs.from_directory(folder),(str(binary.resolve()),),workers=project["workers"],
                                          nuclides=tuple(project["nuclides"]),cancel=stop,verify_serial=project.get("verify_serial",False),
                                          timeout_seconds=project["timeout_seconds"],
                                          progress=(lambda done,total,name:progress(f"Nuclides {done}/{total}: {name}")) if progress else None)
                (folder/"coin.txt").write_bytes(report.coin_bytes)
                result["parallel_diagnostics"]=report.report
                if report.report.get("missing_nuclides"):result["warnings"].append("Decay data not available in EFFTRAN for: "+", ".join(report.report["missing_nuclides"])+". These nuclides remain uncorrected (* in table).")
                for line in report.coin_bytes.splitlines():
                    name=line[:10].decode().strip();energy=int(line[10:20]);factor=float(line[20:])
                    raw_summing.append({"nuclide":name,"energy_keV":energy,"activity_multiplier":factor if factor>0 else None,
                                        "status":"candidate" if factor>0 else "invalid"})

            lib_rows = project.get("library_rows")
            if not lib_rows and project.get("genie_exports"):
                nlb = project["genie_exports"].get("nlb")
                ctf = project["genie_exports"].get("ctf")
                if nlb and Path(nlb).is_file():
                    try:
                        from .software import read_library
                        lib_rows = [{"nuclide": str(r["nuclide"]), "energy_keV": float(r["energy"])} for r in read_library(nlb)]
                    except Exception:
                        pass
                elif ctf and Path(ctf).is_file():
                    try:
                        from .software import read_certificate
                        lib_rows = [{"nuclide": str(r["nuclide"]), "energy_keV": float(r["energy"])} for r in read_certificate(ctf)]
                    except Exception:
                        pass

            result["raw_coin"] = raw_summing
            if lib_rows:
                missing_nucs = set()
                if "parallel_diagnostics" in result:
                    missing_nucs.update(m.strip().upper() for m in result["parallel_diagnostics"].get("missing_nuclides", []))
                if "well_spatial_diagnostics" in result:
                    missing_nucs.update(m.strip().upper() for m in result["well_spatial_diagnostics"].get("missing_nuclides", []))

                projected = []
                for item in lib_rows:
                    nuc = str(item["nuclide"]).strip().upper()
                    en = float(item["energy_keV"])
                    candidates = [c for c in raw_summing if c["nuclide"].strip().upper() == nuc and abs(c["energy_keV"] - en) < 1.0]
                    if candidates:
                        closest = min(candidates, key=lambda c: abs(c["energy_keV"] - en))
                        factor = closest["activity_multiplier"]
                        if factor is not None and factor > 0 and math.isfinite(factor) and closest.get("status") == "candidate":
                            projected.append({"nuclide": str(item["nuclide"]).strip(), "energy_keV": en, "activity_multiplier": factor, "status": "candidate"})
                        else:
                            projected.append({"nuclide": str(item["nuclide"]).strip(), "energy_keV": en, "activity_multiplier": 1.0, "status": "uncorrected"})
                    else:
                        has_nuc_in_coin = any(c["nuclide"].strip().upper() == nuc for c in raw_summing)
                        if has_nuc_in_coin or nuc in missing_nucs or (nuc == "I-129" and en < 35):
                            status = "uncorrected"
                        else:
                            status = "candidate"
                        projected.append({"nuclide": str(item["nuclide"]).strip(), "energy_keV": en, "activity_multiplier": 1.0, "status": status})
                result["summing"] = projected
            else:
                result["summing"] = raw_summing
        if stop.is_set():raise CalculationCancelled("Calculation cancelled")
        result["all_reported_factors_valid"]=all(r["status"]=="candidate" and r["activity_multiplier"] is not None for r in result["summing"])
        if "well_spatial_diagnostics" in result:
            diagnostic=result["well_spatial_diagnostics"]
            if not diagnostic["convergence"]["passed"] or diagnostic["transport"]["probability_saturation_count"]:
                result["all_reported_factors_valid"]=False
                if diagnostic["transport"]["probability_saturation_count"]:result["warnings"].append("Local response required probability saturation; review the well-model assumptions before use")
        if project.get("genie_exports"):
            from .software import detect, export_copy, label
            result["genie_exports"]={}
            for kind,source in project["genie_exports"].items():
                ext={"cal":"EFT","nlb":"LIB"}.get(kind,kind.upper()) if detect(source)=="gammavision" else kind.upper()
                if progress:progress(label(source)+": exporting and reopening "+ext)
                target=work/(Path(source).stem+"_corrected."+ext)
                try:
                    result["genie_exports"][kind]=export_copy(source,target,result,kind)
                    result["genie_exports"][kind]["file"]=target.name
                except Exception as exc:
                    result["warnings"].append(f"{label(source)} auto-export of {ext} skipped: {exc}")
        _write_outputs(work,result)
        moved = False
        for attempt in range(5):
            try:
                os.rename(work,output)
                moved = True
                break
            except (PermissionError, OSError):
                time.sleep(0.08)
        if not moved:
            shutil.copytree(work, output)
            shutil.rmtree(work, ignore_errors=True)
        return result
    finally:
        if work.exists():shutil.rmtree(work, ignore_errors=True)
