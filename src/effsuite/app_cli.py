"""Easy CLI & Batch Runner: effsuite gui; effsuite cylinder/marinelli/well; effsuite batch; effsuite plot-geometry."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import sys

import tempfile

from .model_io import ASSETS, COMMON_DATA, MODES, mode_name, find_model, read_model, calibration_rows, normalize_nuclides
from .parallel_coincidence import CoincidenceError, CalculationCancelled, _publish_new
from .paths import get_results_dir, get_data_dir, get_effsuite_root
from .suite import VERSION, engine_folder, run_project, validate_project


def default_output():
    return get_results_dir() / (datetime.now().strftime("%Y%m%d_%H%M%S_%f"))


def default_data_dir():
    return get_data_dir()


def load_project(path):
    return validate_project(json.loads(Path(path).read_text(encoding="utf-8")))


def _add_common_calc_args(c):
    c.add_argument("--detector",required=True,help="Detector model (.txt path or name in Data/Detector)")
    c.add_argument("--sample",required=True,help="Sample model (.txt path or name in Data/Sample or Data/Standard)")
    c.add_argument("--sample-height",type=float,metavar="MM",help="Override sample filling height [mm] on the fly")
    c.add_argument("--sample-diameter",type=float,metavar="MM",help="Override sample container outer diameter [mm] on the fly")
    c.add_argument("--sample-gap",type=float,metavar="MM",help="Override sample-to-detector positioning gap [mm] on the fly")
    c.add_argument("--sample-material",metavar="NAME",help="Override sample matrix material name on the fly")
    c.add_argument("--sample-density",type=float,metavar="G_CM3",help="Override sample matrix bulk density [g/cm³] and auto-generate XCOM attenuation")
    c.add_argument("--container-material",metavar="NAME",help="Override sample container material name on the fly")
    c.add_argument("--standard",help="Reference standard source model (.txt path or name in Data/Standard)")
    c.add_argument("--calibration",type=Path,help="Reference efficiency .CAL, .txt or .csv (in Data/Calibration)")
    c.add_argument("--export-cal",action="store_true",help="Export transferred Genie .CAL (automatic when --calibration is a .CAL file)")
    c.add_argument("--cal-template",type=Path,help="Genie .CAL template when using a .txt/.csv calibration")
    c.add_argument("--library",type=Path,help="Process a Genie Nuclide Library (.NLB) and export a summing-corrected .NLB")
    c.add_argument("--certificate",type=Path,help="Process a Genie Certificate (.CTF) and export a summing-corrected .CTF")
    c.add_argument("--nuclides",nargs="+",default=[],metavar="Co-60",help="One or more nuclides (comma or space separated)")
    c.add_argument("--output-cal",type=Path,metavar="FILE.CAL",help="Copy the exported Sample .CAL directly to this file path")
    c.add_argument("--output-nlb",type=Path,metavar="FILE.NLB",help="Copy the exported corrected .NLB directly to this file path")
    c.add_argument("--output-ctf",type=Path,metavar="FILE.CTF",help="Copy the exported corrected .CTF directly to this file path")
    c.add_argument("--plot-geometry",nargs="?",const="geometry.png",metavar="PNG_OR_PDF",help="Save CAD axial cross-section diagram with all quotes (default: geometry.png in result folder)")
    c.add_argument("--out",type=Path,help="Result folder (default: Documents/EffSuite/Results/<timestamp>)")
    c.add_argument("--save-project",type=Path,help="Save the resolved project JSON for one-command repeat")
    c.add_argument("--workers",type=int,default=0,help="Worker processes: 0 = automatic, 1 = serial")
    c.add_argument("--data-dir",type=Path,help="Data directory (default: Documents/EffSuite/Data if present)")
    c.add_argument("--verify-serial",action="store_true",help="Verify parallel coincidence results against serial execution")


def parser():
    p=argparse.ArgumentParser(
        description="EFFTRAN • MEFFTRAN • WEFFTRAN — CLI, Batch Runner, and Desktop Suite\nEffSuite built by ChatGPT & Gemini under the supervision of G. Lutter."
    )
    p.add_argument("--version",action="version",version=f"EffSuite {VERSION} (built by ChatGPT & Gemini under the supervision of G. Lutter)")
    sub=p.add_subparsers(dest="command")
    sub.add_parser("gui",help="Open the desktop graphical interface")
    sub.add_parser("doctor",help="Check dependencies and bundled engines")

    material=sub.add_parser("material",help="Create or update material composition & XCOM attenuation files")
    material.add_argument("--input",type=Path,help="Composition JSON, original .txt, Material.xls or XLSX template")
    material.add_argument("--name",help="Material name (e.g. Glucose, Salt_water)")
    material.add_argument("--density",type=float,help="Bulk density in g/cm³ (e.g. 1.346)")
    material.add_argument("--compound",action="append",default=[],metavar="H2O=90",help="Chemical formula and relative weight; repeat for mixtures")
    material.add_argument("--geometry",choices=("cylinder","marinelli","well"),default="cylinder")
    material.add_argument("--library",type=Path,help="Output data folder (default: Documents/EffSuite/Data)")
    material.add_argument("--base-data",type=Path,help="Base data folder when initializing a new library")
    material.add_argument("--save-definition",type=Path,help="Also save the composition definition as JSON")
    material.add_argument("--overwrite",action="store_true",help="Overwrite existing material & recalculate XCOM attenuation")

    examples=sub.add_parser("examples",help="List or run ready-to-use example projects")
    examples.add_argument("--run",choices=("cylinder","marinelli","well"))

    models=sub.add_parser("models",help="List available detector, sample, standard, and material names")
    models.add_argument("geometry",choices=("cylinder","marinelli","well"))
    models.add_argument("--data-dir",type=Path,help="Data directory to inspect (default: Documents/EffSuite/Data)")

    plot_cmd=sub.add_parser("plot-geometry",help="Render dimensioned axial cross-section diagram with all quotes to PNG/PDF/SVG")
    plot_cmd.add_argument("--geometry",choices=("cylinder","marinelli","well","cylindrical","efftran","mefftran","wefftran"),default="cylinder")
    plot_cmd.add_argument("--detector",required=True,help="Detector model file or name")
    plot_cmd.add_argument("--sample",help="Sample model file or name")
    plot_cmd.add_argument("--standard",help="Standard model file or name (if plotting Standard)")
    plot_cmd.add_argument("--kind",choices=("Sample","Standard","Detector"),default="Sample")
    plot_cmd.add_argument("--sample-height",type=float,help="Override sample filling height [mm]")
    plot_cmd.add_argument("--sample-gap",type=float,help="Override positioning gap [mm]")
    plot_cmd.add_argument("--data-dir",type=Path,help="Data directory")
    plot_cmd.add_argument("--out",type=Path,required=True,help="Output image file (.png, .pdf, .svg)")

    batch_cmd=sub.add_parser("batch",help="Run batch calculations from a CSV or JSON table of samples")
    batch_cmd.add_argument("batch_file",nargs="?",type=Path,help="CSV or JSON file describing the batch jobs")
    batch_cmd.add_argument("--template",type=Path,metavar="CSV_PATH",help="Generate a ready-to-fill batch CSV template and exit")
    batch_cmd.add_argument("--out",type=Path,help="Master output folder for all batch jobs and batch_summary.csv/.json")
    batch_cmd.add_argument("--workers",type=int,default=0,help="Worker processes per job (0 = automatic)")
    batch_cmd.add_argument("--data-dir",type=Path,help="Default data directory for the batch")
    batch_cmd.add_argument("--plot-geometry",action="store_true",help="Also save geometry.png with all quotes for every sample in the batch")

    run=sub.add_parser("run",help="Execute a saved GUI/CLI project JSON (with optional CLI overrides)")
    run.add_argument("project",type=Path)
    run.add_argument("--out",type=Path)
    run.add_argument("--workers",type=int)
    run.add_argument("--sample-height",type=float,metavar="MM",help="Override sample filling height [mm]")
    run.add_argument("--sample-material",metavar="NAME",help="Override sample matrix material")
    run.add_argument("--sample-density",type=float,metavar="G_CM3",help="Override sample bulk density [g/cm³]")
    run.add_argument("--output-cal",type=Path,help="Copy exported Sample .CAL to this path")
    run.add_argument("--output-nlb",type=Path,help="Copy exported corrected .NLB to this path")
    run.add_argument("--output-ctf",type=Path,help="Copy exported corrected .CTF to this path")
    run.add_argument("--plot-geometry",nargs="?",const="geometry.png",help="Save CAD cross-section diagram")

    lic_cmd=sub.add_parser("license",help="View license status, import .efflic, or generate activation request")
    lic_cmd.add_argument("--status",action="store_true",help="Display current license status and workstation ID")
    lic_cmd.add_argument("--import",dest="import_file",type=Path,metavar="FILE.efflic",help="Import and activate a .efflic license file")
    lic_cmd.add_argument("--request",type=Path,metavar="REQUEST.req",help="Export an activation request document (.req / .json)")

    for name,aliases in [("cylinder",["efftran"]),("marinelli",["mefftran"]),("well",["wefftran"])]:
        c=sub.add_parser(name,aliases=aliases,help=f"Run {name} calculation from model files/names with inline overrides")
        _add_common_calc_args(c)
    return p


def doctor():
    import importlib.util
    checks={name:importlib.util.find_spec(name) is not None for name in ("numpy","matplotlib","xlrd","PySide6")}
    engines={}
    for mode in MODES:
        folder=engine_folder(mode)
        suffix=".exe" if os.name=="nt" else ""
        stages=["mine","energy","total","scatter","buildup","eta","ptt","efficiency","transfer"]+([] if mode=="well" else ["coincidence"])
        engines[MODES[mode]]={name:(folder/(name+suffix)).is_file() for name in stages}
    from .materials import XCOM,TEMPLATE
    target="windows" if os.name=="nt" else "macos" if sys.platform=="darwin" else "linux"
    materials={"xcom":(XCOM/"bin"/target/("xcom.exe" if os.name=="nt" else "xcom")).is_file(),"excel_template":TEMPLATE.is_file(),"element_data":len(list(XCOM.glob("MDATX3.*")))==100}
    lic_info = {"status": "unlicensed"}
    try:
        from .licensing.storage import default_store
        store = default_store(VERSION)
        lic = store.current()
        lic_info = {"status": "active", "licensee": lic.licensee, "edition": lic.edition, "expires_at": lic.expires_at.isoformat() if lic.expires_at else None}
    except Exception as exc:
        lic_info = {"status": "not_activated", "detail": str(exc)}
    return {"version":VERSION,"python":sys.version,"interpreter":sys.executable,"dependencies":checks,"engines":engines,"materials":materials,
            "license": lic_info,
            "qualification":"Beta Build; experimental qualification pending. Verify installation against reference data"}


def example_path(name):
    return Path(__file__).parent/"assets/examples"/(name+".effsuite.json")


def _resolve_file(path_or_name, subfolder, data_dir):
    if not path_or_name:return None
    p=Path(path_or_name).expanduser()
    if p.is_file():return p.resolve()
    search=[]
    if data_dir:
        d=Path(data_dir).expanduser()
        search.extend([d/subfolder/p.name, d/p.name])
    default_d=default_data_dir()
    if default_d:
        search.extend([default_d/subfolder/p.name, default_d/p.name])
    for candidate in search:
        if candidate.is_file():return candidate.resolve()
    return p


def _apply_sample_overrides(mode, sample_values, *, height=None, diameter=None, gap=None, material=None, density=None, container_material=None, data_dir=None, progress=None):
    out=list(sample_values)
    if diameter is not None:
        out[0]=float(diameter)
    if height is not None:
        idx=2 if mode=="marinelli" else 1
        out[idx]=float(height)
    if gap is not None and mode!="marinelli":
        out[4]=float(gap)
    if material:
        out[5]=str(material).strip()
    if container_material:
        out[6]=str(container_material).strip()
    if density is not None:
        from .materials import load_composition, create_material, default_library
        mat_name=out[5]
        lib_dir=Path(data_dir) if data_dir else (default_data_dir() or default_library())
        comp_candidates=[lib_dir/"Composition"/f"{mat_name}.txt", COMMON_DATA/"Composition"/f"{mat_name}.txt"]
        comp_file=next((c for c in comp_candidates if c.is_file()), None)
        if comp_file is None:
            raise CoincidenceError(f"Cannot override density for '{mat_name}': composition file not found in {lib_dir/'Composition'}")
        d=load_composition(comp_file)
        d["name"]=mat_name
        d["density_g_cm3"]=float(density)
        create_material(d, lib_dir, geometry=mode, base_directory=data_dir, progress=progress, overwrite=True)
    return out


def _save_geometry_plot(project, dest_path, kind="Sample"):
    import matplotlib.pyplot as plt
    from .geometry_view import draw_geometry
    mode=project["geometry"]
    d=project["detector"]
    s=project.get("standard") if kind=="Standard" else project.get("sample") if kind=="Sample" else None
    fig=plt.figure(figsize=(10.5,6.4))
    ax=fig.add_subplot(111)
    fig.subplots_adjust(left=.08,right=.66,bottom=.10,top=.92)
    draw_geometry(ax,mode,d,s,kind,compact=False)
    dest=Path(dest_path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(dest,dpi=150)
    plt.close(fig)
    return str(dest.resolve())


def _copy_direct_outputs(result, *, output_cal=None, output_nlb=None, output_ctf=None):
    exports=result.get("genie_exports") or {}
    copied={}
    for key,target in [("cal_output",output_cal),("nlb_output",output_nlb),("ctf_output",output_ctf)]:
        if target and exports.get(key) and Path(exports[key]).is_file():
            target_path=Path(target).expanduser().resolve()
            target_path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(exports[key],target_path)
            copied[key]=str(target_path)
    if copied:
        result["direct_outputs"]=copied


def _build_project_from_args(mode, args, progress=None):
    data_dir=args.data_dir or default_data_dir()
    cal_path=_resolve_file(args.calibration,"Calibration",data_dir) if args.calibration else None
    nlb_path=_resolve_file(args.library,"NuclideLibrary",data_dir) if args.library else None
    ctf_path=_resolve_file(args.certificate,"Certificates",data_dir) if args.certificate else None
    has_transfer=cal_path is not None and bool(args.standard)
    if (cal_path is not None) != bool(args.standard) and not (args.nuclides or nlb_path or ctf_path):
        raise CoincidenceError("Efficiency transfer needs both --standard and --calibration")
    names=normalize_nuclides(args.nuclides)
    genie_sources={}
    lib_records=None
    for kind,path in (("nlb",nlb_path),("ctf",ctf_path)):
        if path:
            from .genie import read_library,read_certificate
            rows=(read_library if kind=="nlb" else read_certificate)(path)
            names=normalize_nuclides(names+[str(row["nuclide"]) for row in rows])
            genie_sources[kind]=str(path.resolve())
            if lib_records is None:
                lib_records=[{"nuclide":str(row["nuclide"]), "energy_keV":float(row["energy"])} for row in rows]
    if not has_transfer and not names:
        raise CoincidenceError("Add --nuclides / --library / --certificate for summing, or --standard and --calibration for efficiency transfer")
    det_values=read_model(mode,"detector",find_model(mode,"detector",args.detector,data_dir))
    smp_values=read_model(mode,"sample",find_model(mode,"sample",args.sample,data_dir))
    smp_values=_apply_sample_overrides(
        mode,smp_values,
        height=args.sample_height,diameter=args.sample_diameter,gap=args.sample_gap,
        material=args.sample_material,density=args.sample_density,container_material=args.container_material,
        data_dir=data_dir,progress=progress,
    )
    project={
        "schema_version":1,
        "geometry":mode,
        "task":"both" if names and has_transfer else "transfer" if has_transfer else "summing",
        "detector":det_values,
        "sample":smp_values,
        "nuclides":names,
        "workers":args.workers,
        "verify_serial":args.verify_serial,
    }
    if lib_records:
        project["library_rows"]=lib_records
    if has_transfer:
        project["standard"]=read_model(mode,"standard",find_model(mode,"standard",args.standard,data_dir))
        project["calibration"]=calibration_rows(cal_path)
        if cal_path.suffix.lower()==".cal":
            project["calibration_template"]=str(cal_path.resolve())
        if args.cal_template:
            tpl=_resolve_file(args.cal_template,"Calibration",data_dir)
            project["calibration_template"]=str(tpl.resolve())
        if project.get("calibration_template") and (args.export_cal or args.output_cal or cal_path.suffix.lower()==".cal"):
            genie_sources["cal"]=project["calibration_template"]
    elif args.export_cal:
        raise CoincidenceError("--export-cal needs --standard and a .CAL calibration input or --cal-template")
    if genie_sources:
        project["genie_exports"]=genie_sources
    project=validate_project(project)
    if data_dir:
        project["data_directory"]=str(Path(data_dir).resolve())
    return project


BATCH_COLUMNS=[
    "id","geometry","detector","sample","sample_height_mm","sample_material","sample_density_g_cm3","sample_gap_mm",
    "standard","calibration","library","certificate","nuclides","output_cal","output_nlb","output_ctf"
]


def _run_batch(args, progress):
    if args.template:
        tpl=Path(args.template)
        tpl.parent.mkdir(parents=True,exist_ok=True)
        with tpl.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            w.writerow(BATCH_COLUMNS)
            w.writerow(["Sample_001","cylinder","DET002","PET70_40","33.4","Glucose","1.346","0","PET70_40","TF400_268_2025.CAL","NUTECH.NLB","","","Sample_001.CAL","Sample_001.NLB",""])
        print(f"Created batch template: {tpl}",file=sys.stderr)
        return 0
    if not args.batch_file or not args.batch_file.is_file():
        raise CoincidenceError("Provide a batch CSV or JSON file (or use --template batch.csv to generate one)")
    if args.batch_file.suffix.lower()==".json":
        jobs=json.loads(args.batch_file.read_text(encoding="utf-8"))
        if isinstance(jobs,dict):jobs=jobs.get("jobs",[])
    else:
        with args.batch_file.open("r",newline="",encoding="utf-8-sig") as f:
            jobs=[row for row in csv.DictReader(f) if any(v and str(v).strip() for v in row.values())]
    if not jobs:
        raise CoincidenceError("No jobs found in batch file")
    master_out=args.out or (Path.home()/"Documents/EffSuite/Results"/("Batch_"+datetime.now().strftime("%Y%m%d_%H%M%S")))
    master_out.mkdir(parents=True,exist_ok=True)
    summary_rows=[]
    all_ok=True
    for idx,row in enumerate(jobs,1):
        job_id=str(row.get("id") or f"Job_{idx:03d}").strip()
        geom=mode_name(str(row.get("geometry") or "cylinder").strip())
        progress(f"[{idx}/{len(jobs)}] Running batch job '{job_id}' ({geom})...")
        job_ns=argparse.Namespace(
            detector=str(row.get("detector") or "").strip(),
            sample=str(row.get("sample") or "").strip(),
            sample_height=float(row["sample_height_mm"]) if str(row.get("sample_height_mm") or "").strip() else None,
            sample_diameter=float(row["sample_diameter_mm"]) if str(row.get("sample_diameter_mm") or "").strip() else None,
            sample_gap=float(row["sample_gap_mm"]) if str(row.get("sample_gap_mm") or "").strip() else None,
            sample_material=str(row.get("sample_material") or "").strip() or None,
            sample_density=float(row["sample_density_g_cm3"]) if str(row.get("sample_density_g_cm3") or "").strip() else None,
            container_material=str(row.get("container_material") or "").strip() or None,
            standard=str(row.get("standard") or "").strip() or None,
            calibration=Path(row["calibration"].strip()) if str(row.get("calibration") or "").strip() else None,
            export_cal=bool(str(row.get("calibration") or "").strip()),
            cal_template=None,
            library=Path(row["library"].strip()) if str(row.get("library") or "").strip() else None,
            certificate=Path(row["certificate"].strip()) if str(row.get("certificate") or "").strip() else None,
            nuclides=[s.strip() for s in str(row.get("nuclides") or "").split(",") if s.strip()],
            output_cal=Path(row["output_cal"].strip()) if str(row.get("output_cal") or "").strip() else None,
            output_nlb=Path(row["output_nlb"].strip()) if str(row.get("output_nlb") or "").strip() else None,
            output_ctf=Path(row["output_ctf"].strip()) if str(row.get("output_ctf") or "").strip() else None,
            workers=args.workers,
            data_dir=args.data_dir,
            verify_serial=False,
        )
        job_out=master_out/job_id
        project=_build_project_from_args(geom,job_ns,progress=progress)
        res=run_project(project,job_out,progress=progress)
        _copy_direct_outputs(res,output_cal=job_ns.output_cal,output_nlb=job_ns.output_nlb,output_ctf=job_ns.output_ctf)
        if args.plot_geometry:
            res["geometry_plot"]=_save_geometry_plot(project,job_out/"geometry.png")
        all_ok=all_ok and bool(res.get("all_reported_factors_valid",True))
        exports=res.get("genie_exports") or {}
        summary_rows.append({
            "id":job_id,
            "geometry":geom,
            "task":project["task"],
            "sample_material":project["sample"][5],
            "sample_height_mm":project["sample"][2 if geom=="marinelli" else 1],
            "output_directory":res["output_directory"],
            "cal_output":res.get("direct_outputs",{}).get("cal_output") or exports.get("cal_output",""),
            "nlb_output":res.get("direct_outputs",{}).get("nlb_output") or exports.get("nlb_output",""),
            "ctf_output":res.get("direct_outputs",{}).get("ctf_output") or exports.get("ctf_output",""),
            "valid":res.get("all_reported_factors_valid",True),
        })
    summary_csv=master_out/"batch_summary.csv"
    with summary_csv.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(summary_rows[0].keys()))
        w.writeheader();w.writerows(summary_rows)
    summary_json=master_out/"batch_summary.json"
    summary_json.write_text(json.dumps({"batch_directory":str(master_out.resolve()),"jobs":summary_rows},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"batch_directory":str(master_out.resolve()),"summary_csv":str(summary_csv.resolve()),"jobs":summary_rows},indent=2))
    return 0 if all_ok else 1


def _check_cli_license():
    from .licensing.config import LICENSE_REQUIRED
    if not LICENSE_REQUIRED:
        return
    from .licensing.storage import default_store
    from .licensing.verification import LicenseError
    try:
        store = default_store(VERSION)
        store.current()
    except LicenseError as exc:
        raise CoincidenceError(f"Licence check failed: {exc}\nRun 'effsuite license --status' to view status or activate.")


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    args=parser().parse_args(argv)
    progress=lambda s:print(s,file=sys.stderr)
    try:
        if args.command in {None,"gui"}:
            from .gui import main as gui_main
            return gui_main()
        if args.command=="license":
            from .licensing.storage import default_store
            from .licensing.verification import LicenseError
            store=default_store(VERSION)
            if args.request:
                doc=store.request_document()
                args.request.parent.mkdir(parents=True,exist_ok=True)
                args.request.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
                print(f"Activation request written to: {args.request}")
                print(f"Installation ID: {doc['installation_id']}")
                return 0
            if args.import_file:
                if not args.import_file.is_file():
                    raise CoincidenceError(f"Licence file not found: {args.import_file}")
                lic=store.import_license(args.import_file.read_bytes())
                print("Licence imported successfully:")
                print(f"  Licensee:         {lic.licensee}")
                print(f"  Edition:          {lic.edition.title()}")
                print(f"  Expires:          {lic.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC') if lic.expires_at else 'Permanent'}")
                print(f"  Max version:      {lic.max_version or 'All versions'}")
                print(f"  Installation ID:  {lic.installation_id or 'Any workstation'}")
                print(f"  Licence ID:       {lic.license_id}")
                return 0
            inst_id=store.installation_id()
            print("EffSuite Licence Status")
            print("=======================")
            print(f"Product:          EffSuite v{VERSION}")
            print(f"Installation ID:  {inst_id}")
            try:
                lic=store.current()
                print("Status:           ACTIVE & QUALIFIED")
                print(f"Licensee:         {lic.licensee}")
                print(f"Edition:          {lic.edition.title()}")
                print(f"Expires:          {lic.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC') if lic.expires_at else 'Permanent'}")
                print(f"Max version:      {lic.max_version or 'All versions'}")
                print(f"Workstation lock: {'Locked to this workstation' if lic.installation_id else 'Unlocked (Site / Lab licence)'}")
                return 0
            except LicenseError as exc:
                print(f"Status:           UNLICENSED ({exc})")
                print(f"Licence path:     {store.path}")
                print("\nTo activate:")
                print("  1. Generate request:  effsuite license --request activation.req")
                print("  2. Send request to publisher")
                print("  3. Import licence:    effsuite license --import license.efflic")
                return 1
        if args.command=="doctor":
            result=doctor();print(json.dumps(result,indent=2))
            return 0 if all(all(v.values()) for v in result["engines"].values()) and all(result["materials"].values()) and all(result["dependencies"][name] for name in ("numpy","matplotlib","xlrd")) else 1
        if args.command=="material":
            from .materials import load_composition,validate_composition,create_material,default_library,save_definition
            definition=load_composition(args.input) if args.input else {"schema_version":1,"components":[]}
            if args.name:definition["name"]=args.name
            if args.density is not None:definition["density_g_cm3"]=args.density
            if args.compound:
                if args.input:raise CoincidenceError("Use --input or --compound; override density/name explicitly if needed")
                rows=[]
                for value in args.compound:
                    if value.count("=")!=1:raise CoincidenceError("Compound syntax: --compound H2O=90 --compound NaCl=10")
                    formula,weight=value.split("=");rows.append({"formula":formula,"weight":weight})
                definition["components"]=rows
            definition=validate_composition(definition)
            if args.save_definition and args.save_definition.exists():raise CoincidenceError("Definition output exists; choose a new filename")
            result=create_material(definition,args.library or default_library(),geometry=args.geometry,base_directory=args.base_data,progress=progress,overwrite=args.overwrite)
            if args.save_definition:save_definition(args.save_definition,definition)
            print("Saved material: "+definition["name"]+"\nData folder: "+result["data_directory"],file=sys.stderr)
            print(json.dumps(result,indent=2,allow_nan=False));return 0
        if args.command=="models":
            mode=mode_name(args.geometry)
            data_dir=args.data_dir or default_data_dir()
            for label in ("Detector","Sample","Standard"):
                names=set(p.stem for p in (ASSETS/mode/label).glob("*.txt"))
                if data_dir and (Path(data_dir)/label).is_dir():
                    names|=set(p.stem for p in (Path(data_dir)/label).glob("*.txt"))
                print(label+": "+", ".join(sorted(names)))
            mats=set(p.stem for p in (COMMON_DATA/"Composition").glob("*.txt"))
            if data_dir and (Path(data_dir)/"Composition").is_dir():
                mats|=set(p.stem for p in (Path(data_dir)/"Composition").glob("*.txt"))
            print("Materials: "+", ".join(sorted(mats)))
            return 0
        if args.command=="plot-geometry":
            mode=mode_name(args.geometry)
            data_dir=args.data_dir or default_data_dir()
            det=read_model(mode,"detector",find_model(mode,"detector",args.detector,data_dir))
            smp=read_model(mode,"sample",find_model(mode,"sample",args.sample,data_dir)) if args.sample else None
            if smp:
                smp=_apply_sample_overrides(mode,smp,height=args.sample_height,gap=args.sample_gap,data_dir=data_dir)
            std=read_model(mode,"standard",find_model(mode,"standard",args.standard,data_dir)) if args.standard else None
            proj={"geometry":mode,"detector":det,"sample":smp,"standard":std}
            saved=_save_geometry_plot(proj,args.out,kind=args.kind)
            print(json.dumps({"geometry_plot":saved},indent=2))
            return 0
        if args.command=="batch":
            _check_cli_license()
            return _run_batch(args,progress)
        if args.command=="examples":
            if args.run:
                _check_cli_license()
                result=run_project(load_project(example_path(args.run)),default_output(),progress=progress)
                print(json.dumps(result,indent=2,allow_nan=False));return 0 if result["all_reported_factors_valid"] else 1
            for name in ("cylinder","marinelli","well"):print(example_path(name))
            return 0
        if args.command=="run":
            _check_cli_license()
            project=load_project(args.project)
            if args.workers is not None:project["workers"]=args.workers
            if any(v is not None for v in (args.sample_height,args.sample_material,args.sample_density)):
                project["sample"]=_apply_sample_overrides(
                    project["geometry"],project["sample"],
                    height=args.sample_height,material=args.sample_material,density=args.sample_density,
                    data_dir=project.get("data_directory"),progress=progress,
                )
        else:
            _check_cli_license()
            mode=mode_name(args.command)
            project=_build_project_from_args(mode,args,progress=progress)
            if args.save_project:
                with args.save_project.open("x",encoding="utf-8") as f:json.dump(project,f,indent=2);f.write("\n")
        out_dir=args.out or default_output()
        result=run_project(project,out_dir,progress=progress)
        _copy_direct_outputs(result,output_cal=getattr(args,"output_cal",None),output_nlb=getattr(args,"output_nlb",None),output_ctf=getattr(args,"output_ctf",None))
        if getattr(args,"plot_geometry",None):
            plot_arg=args.plot_geometry
            plot_dest=(Path(result["output_directory"])/"geometry.png") if plot_arg=="geometry.png" else Path(plot_arg)
            result["geometry_plot"]=_save_geometry_plot(project,plot_dest)
        print(f"Saved: {result['output_directory']}",file=sys.stderr)
        print(json.dumps(result,indent=2,allow_nan=False))
        return 0 if result["all_reported_factors_valid"] else 1
    except (CoincidenceError,OSError,ValueError) as exc:
        print(f"EffSuite: {exc}",file=sys.stderr);return 2
    except KeyboardInterrupt:return 130


if __name__=="__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
