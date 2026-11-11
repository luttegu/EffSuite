"""Original EFFTRAN model field ordering shared by the GUI and easy CLI."""
from __future__ import annotations
import csv
import io
import math
from pathlib import Path
import re

from .parallel_coincidence import CoincidenceError

ASSETS = Path(__file__).parent/"assets/engines"
COMMON_DATA = Path(__file__).parent/"assets/common"
COMMON_ASSETS = COMMON_DATA
MODES = {"cylindrical": "EFFTRAN", "marinelli": "MEFFTRAN", "well": "WEFFTRAN"}
ALIASES = {"cylinder": "cylindrical", "efftran": "cylindrical", "mefftran": "marinelli", "wefftran": "well"}
CYLINDER_DETECTOR = [
    ("End cap (housing) diameter", "mm"), ("End cap (housing) thickness", "mm"),
    ("Crystal diameter", "mm"), ("Crystal length", "mm"), ("Top dead layer", "mm"),
    ("Side dead layer", "mm"), ("Window thickness", "mm"), ("Window-to-crystal gap", "mm"),
    ("Crystal hole (cavity) diameter", "mm"), ("Crystal hole (cavity) length", "mm"),
    ("Mount cup (holder) thickness", "mm"), ("Bulletization (crystal rounding) radius", "mm"),
    ("Absorber diameter", "mm"), ("Absorber thickness", "mm"),
    ("Crystal material", "material"), ("Window material", "material"),
    ("End cap (housing) material", "material"), ("Mount cup (holder) material", "material"),
    ("Absorber material", "material")]
WELL_DETECTOR = [("Crystal diameter", "mm"), ("Crystal length", "mm"),
                 ("Absorber thickness", "mm"), ("Well diameter", "mm"), ("Well length", "mm"),
                 ("Crystal material", "material"), ("Absorber material", "material")]
WELL_DETECTOR_OPTIONAL = [("Mantle (side) dead layer", "mm"),
                          ("Bottom dead layer", "mm"),
                          ("Mount cup (holder) thickness", "mm"),
                          ("Well bottom sample offset", "mm"),
                          ("Mount cup (holder) material", "material")]
CYLINDER_SOURCE = [("Container diameter", "mm"), ("Source filling height", "mm"),
                   ("Container bottom thickness", "mm"), ("Container side wall thickness", "mm"),
                   ("Container-to-absorber gap", "mm"), ("Source material", "material"),
                   ("Container material", "material"), ("Source density", "g/cm³")]
MARINELLI_SOURCE = [("Container diameter", "mm"), ("Container hole diameter", "mm"),
                    ("Source filling height", "mm"), ("Container hole length", "mm"),
                    ("Container thickness", "mm"), ("Source material", "material"),
                    ("Container material", "material"), ("Source density", "g/cm³")]


def default_material_density(material_name: str, data_directory: str | Path | None = None) -> float:
    name = str(material_name).strip()
    if not name or name.lower() == "vacuum":
        return 0.0
    roots = []
    if data_directory:
        roots.append(Path(data_directory).expanduser() / "Composition")
    roots.append(Path.home() / "Documents/EffSuite/Data/Composition")
    roots.append(COMMON_DATA / "Composition")
    for root in roots:
        if not root.is_dir():
            continue
        direct = root / f"{name}.txt"
        target = direct if direct.is_file() else next(
            (p for p in root.glob("*.txt") if p.stem.lower() == name.lower()),
            None,
        )
        if target is not None:
            try:
                for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.strip():
                        val = float(line.strip().split()[0])
                        return 0.0 if val <= 1e-12 else val
            except (ValueError, OSError):
                pass
    return 1.0


def mode_name(value):
    value = ALIASES.get(value.lower(), value.lower())
    if value not in MODES: raise CoincidenceError("Choose cylinder, marinelli or well")
    return value


def fields(mode, kind, extended=False):
    if kind == "detector":
        if mode == "well":
            return WELL_DETECTOR + WELL_DETECTOR_OPTIONAL if extended else WELL_DETECTOR
        return CYLINDER_DETECTOR[:12]+CYLINDER_DETECTOR[14:18] if mode == "marinelli" else CYLINDER_DETECTOR
    if mode == "marinelli": return MARINELLI_SOURCE
    if mode == "well":
        return CYLINDER_SOURCE[:4]+[("Sample bottom–well bottom distance", "mm")]+CYLINDER_SOURCE[5:]
    return CYLINDER_SOURCE


def validate_model(mode, kind, values, data_directory=None):
    if isinstance(values, dict):
        if mode == "well" and kind == "detector":
            dr = values.get("crystal_diameter", values.get("dr", values.get("Crystal diameter")))
            dl = values.get("crystal_length", values.get("dl", values.get("Crystal length")))
            dd = values.get("absorber_thickness", values.get("dd", values.get("Absorber thickness", 0.0)))
            wd = values.get("well_diameter", values.get("well_d", values.get("Well diameter")))
            wh = values.get("well_length", values.get("well_h", values.get("Well length")))
            dm = values.get("crystal_material", values.get("dmat", values.get("Crystal material", "Ge")))
            am = values.get("absorber_material", values.get("amat", values.get("Absorber material", "aluminium")))
            md = values.get("mantle_dead_layer", values.get("side_dead_layer", values.get("Mantle (side) dead layer", dd)))
            bd = values.get("bottom_dead_layer", values.get("Bottom dead layer", dd))
            ht = values.get("holder_thickness", values.get("Mount cup (holder) thickness", 0.0))
            so = values.get("sample_offset", values.get("Well bottom sample offset", 0.0))
            hm = values.get("holder_material", values.get("Mount cup (holder) material", "copper"))
            values = [dr, dl, dd, wd, wh, dm, am, md, bd, ht, so, hm]
        else:
            definition = fields(mode, kind)
            values = [values.get(label, values.get(label.lower().replace(" ", "_"))) for label, _ in definition]
            if kind != "detector" and len(values) == 8 and values[7] is None:
                values[7] = default_material_density(values[5] if values[5] is not None else "water", data_directory=data_directory)

    if mode == "well" and kind == "detector":
        if not (7 <= len(values) <= 12):
            raise CoincidenceError(f"WEFFTRAN detector: expected 7 to 12 fields, got {len(values)}")
        full_def = WELL_DETECTOR + WELL_DETECTOR_OPTIONAL
        out = []
        for i in range(len(values)):
            label, unit = full_def[i]
            val = values[i]
            if unit == "mm":
                try: numeric = float(val)
                except (ValueError, TypeError) as exc: raise CoincidenceError(f"{label}: enter a number in mm") from exc
                if isinstance(val, bool) or not math.isfinite(numeric) or numeric < 0:
                    raise CoincidenceError(f"{label}: enter a finite, nonnegative dimension")
                out.append(numeric)
            else:
                name = str(val).strip()
                if not name or name in {".", ".."} or any(c in name for c in '/\\:\r\n'):
                    raise CoincidenceError(f"{label}: choose a material name")
                out.append(name)
        dd = out[2]
        if len(out) < 8: out.append(dd)
        if len(out) < 9: out.append(dd)
        if len(out) < 10: out.append(0.0)
        if len(out) < 11: out.append(0.0)
        if len(out) < 12: out.append("copper")

        dr, dl, dd, well_d, well_h = out[:5]
        if min(dr, dl) <= 0: raise CoincidenceError("Crystal diameter and length must be positive")
        if well_d <= 0 or well_h <= 0 or well_d >= dr or well_h >= dl:
            raise CoincidenceError("The well must fit inside the crystal")
        mantle_dead, bottom_dead = out[7], out[8]
        if 2 * mantle_dead >= dr - well_d:
            raise CoincidenceError("Mantle dead layer is too thick for the crystal mantle")
        if bottom_dead >= dl - well_h:
            raise CoincidenceError("Bottom dead layer is too thick for the crystal base")
        return out

    if kind == "detector":
        if mode == "marinelli" and len(values) == 19:
            # Convert EFFTRAN 19-line detector -> MEFFTRAN 16-line detector:
            # Indices 0..11: crystal, housing, dead layer dimensions
            # Indices 12..13: absorber diameter & thickness (omitted in Marinelli)
            # Indices 14..17: crystal, window, housing, holder materials -> 12..15
            # Index 18: absorber material (omitted in Marinelli)
            values = list(values[:12]) + [values[14], values[15], values[16], values[17]]
        elif mode in ("cylindrical", "efftran") and len(values) == 16:
            # Convert MEFFTRAN 16-line detector -> EFFTRAN 19-line detector:
            # Indices 0..11: crystal, housing, dead layer dimensions
            # Insert absorber diameter = 0.0, absorber thickness = 0.0
            # Indices 12..15: crystal, window, housing, holder materials -> 14..17
            # Insert absorber material = "copper"
            values = list(values[:12]) + [0.0, 0.0, values[12], values[13], values[14], values[15], "copper"]

    definition = fields(mode, kind)
    if kind != "detector" and len(values) == 7:
        values = list(values) + [default_material_density(values[5], data_directory=data_directory)]
    if len(values) != len(definition):
        raise CoincidenceError(f"{MODES[mode]} {kind}: expected {len(definition)} fields, got {len(values)}")
    out=[]
    for (label, unit), value in zip(definition, values):
        if unit in ("mm", "g/cm³"):
            try: numeric = float(value)
            except (ValueError, TypeError) as exc: raise CoincidenceError(f"{label}: enter a number in {unit}") from exc
            if isinstance(value,bool) or not math.isfinite(numeric) or numeric < 0:
                raise CoincidenceError(f"{label}: enter a finite, nonnegative value")
            out.append(numeric)
        else:
            name=str(value).strip()
            if not name or name in {".",".."} or any(c in name for c in '/\\:\r\n'):
                raise CoincidenceError(f"{label}: choose a material name")
            out.append(name)
    if kind == "detector":
        dr,dl=(out[2],out[3])
        if min(dr,dl)<=0: raise CoincidenceError("Crystal diameter and length must be positive")
        if out[0]<dr or out[4]>=dl or 2*out[5]>=dr:
            raise CoincidenceError("Check end cap, crystal and dead-layer dimensions")
    elif mode=="marinelli" and out[1]>=out[0]:
        raise CoincidenceError("Marinelli hole diameter must be smaller than the outer diameter")
    elif mode=="well" and (out[0]<=2*out[3] or out[1]<=0):
        raise CoincidenceError("The well sample must have a positive active radius and filling height")
    return out


def model_bytes(mode,kind,values):
    validated = validate_model(mode,kind,values)
    if mode == "well" and kind == "detector" and len(values) == 7:
        validated = validated[:7]
    return ("\n".join(format(v,".17g") if isinstance(v,(int,float)) else v
                       for v in validated)+"\n").encode("cp1252")


def find_model(mode, kind, name, data_directory=None):
    path=Path(name).expanduser()
    if path.is_file(): return path.resolve()
    folder={"detector":"Detector","sample":"Sample","standard":"Standard"}[kind]
    candidates=[]
    if data_directory:
        d=Path(data_directory).expanduser()
        candidates.extend([d/folder/name,d/folder/(name+".txt"),d/name,d/(name+".txt")])
        if kind=="sample":
            candidates.extend([d/"Standard"/name,d/"Standard"/(name+".txt")])
    user_data=Path.home()/"Documents/EffSuite/Data"
    candidates.extend([user_data/folder/name,user_data/folder/(name+".txt"),user_data/name,user_data/(name+".txt")])
    candidates.extend([ASSETS/mode/folder/name,ASSETS/mode/folder/(name+".txt")])
    matches=[p for p in candidates if p.is_file()]
    if not matches: raise CoincidenceError(f"Cannot find {kind} '{name}'. Use a file path or a bundled model name.")
    return matches[0]


def read_model(mode,kind,path):
    text=Path(path).read_bytes().decode("utf-8-sig",errors="replace")
    if "\ufffd" in text:text=Path(path).read_bytes().decode("cp1252")
    raw_lines=[line.strip() for line in text.splitlines()]
    lines=[]
    kv_map={}
    for line in raw_lines:
        if not line or line.startswith("#"):continue
        code=line.split("#")[0].strip()
        if not code:continue
        if "=" in code:
            k,v=[token.strip() for token in code.split("=",1)]
            norm_k=re.sub(r"[^a-z0-9]","",k.lower())
            kv_map[norm_k]=v
        else:
            lines.append(code)

    if mode=="well" and kind=="detector" and kv_map:
        opt_keys=[
            ("mantledeadlayer","sidedeadlayer","mantledl"),
            ("bottomdeadlayer","bottomdl"),
            ("holderthickness","mountcupthickness","holderth"),
            ("sampleoffset","wellbottomsampleoffset","welloffset"),
            ("holdermaterial","mountcupmaterial","holdermat"),
        ]
        merged=list(lines[:7])
        while len(merged)<7:merged.append(0.0 if len(merged)<5 else "aluminium")
        for aliases in opt_keys:
            val=next((kv_map[a] for a in aliases if a in kv_map),None)
            if val is not None:merged.append(val)
            elif len(lines)>len(merged):merged.append(lines[len(merged)])
        return validate_model(mode,kind,merged)

    return validate_model(mode,kind,lines)


def calibration_rows(path):
    path=Path(path)
    if path.suffix.lower() in {".cal",".eft"}:
        from .software import read_cal
        return validate_calibration(read_cal(path))
    text=path.read_text(encoding="utf-8-sig")
    rows=[]
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):continue
        tokens=next(csv.reader([line])) if "," in line else line.split()
        try: values=[float(v.replace("D","E").replace("d","e")) for v in tokens]
        except ValueError:
            if not rows and tokens and tokens[0].strip().lower() in {"energy_kev","energy","e [kev]","e[kev]"}:continue
            raise CoincidenceError("Unexpected text inside calibration data; only a named header may be skipped")
        if len(values) not in {2,3}: raise CoincidenceError("Calibration rows: energy_keV, efficiency, relative_uncertainty_percent")
        rows.append({"energy_keV":values[0],"efficiency":values[1],"u_rel_percent":values[2] if len(values)==3 else 0.})
    return validate_calibration(rows)


def validate_calibration(rows):
    if not 2<=len(rows)<=93:raise CoincidenceError("Enter 2 to 93 calibration points")
    result=[];previous=0.
    for row in rows:
        try: e,p,u=[float(row[k]) for k in ("energy_keV","efficiency","u_rel_percent")]
        except (ValueError,TypeError,KeyError) as exc:raise CoincidenceError("Invalid calibration point") from exc
        if not all(math.isfinite(v) for v in (e,p,u)) or e<=previous or not 0<p<=1 or u<0:
            raise CoincidenceError("Calibration energies must increase; efficiency is an absolute probability (0–1); uncertainty is relative %")
        result.append({"energy_keV":e,"efficiency":p,"u_rel_percent":u});previous=e
    return result


def normalize_nuclides(names):
    output=[]
    for name in names:
        for token in re.split(r"[,;\s]+",name.strip()):
            if not token:continue
            match=re.fullmatch(r"([A-Za-z]{1,2})-?(\d+)([mM]?)",token)
            if not match:raise CoincidenceError(f"Invalid nuclide '{token}'; example: Co-60")
            formatted=f"{match[1].upper()}-{match[2]}{match[3].upper()}"
            if formatted not in output:output.append(formatted)
    return output
