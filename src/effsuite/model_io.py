"""Detector, source and calibration models, in the field order of the original
EFFTRAN, MEFFTRAN and WEFFTRAN programs. Shared by the GUI and the CLI.

A "model" is a list of values, one per field, for example a cylindrical
detector has 19 fields (see CYLINDER_DETECTOR). Model files are plain text
with one value per line, exactly as the original programs read them.
"""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from .parallel_coincidence import CoincidenceError

ASSETS = Path(__file__).parent / "assets/engines"     # per-engine files (models, Fortran programs)
COMMON_DATA = Path(__file__).parent / "assets/common"  # materials and decay data shared by all engines

MODES = {"cylindrical": "EFFTRAN", "marinelli": "MEFFTRAN", "well": "WEFFTRAN"}
ALIASES = {"cylinder": "cylindrical", "efftran": "cylindrical", "mefftran": "marinelli", "wefftran": "well"}

# (field label, unit) for every model, in file order.
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

def _user_data_folders(data_directory=None) -> list[Path]:
    """Laboratory data folders to search, most specific first (see paths.user_data_dirs)."""
    from .paths import user_data_dirs
    return user_data_dirs(data_directory)


def material_roots(data_directory=None) -> list[Path]:
    """Folders holding Material/ and Composition/, most specific first.

    The user's folders (project, default, legacy) come first, the bundled
    original EFFTRAN / MEFFTRAN materials last.
    """
    return _user_data_folders(data_directory) + [COMMON_DATA]


def material_names(data_directory=None) -> list[str]:
    """Names of every material with a Composition file (user folders and bundled originals)."""
    names = set()
    for root in material_roots(data_directory):
        folder = root / "Composition"
        if folder.is_dir():
            names |= {p.stem for p in folder.glob("*.txt")}
    return sorted(names, key=str.lower)


def find_material_file(name: str, kind: str = "Composition", data_directory=None) -> Path | None:
    """The Composition (or Material) file of a material, most specific folder first."""
    for root in material_roots(data_directory):
        candidate = root / kind / f"{name}.txt"
        if candidate.is_file():
            return candidate
    return None


def default_material_density(material_name: str, data_directory: str | Path | None = None) -> float:
    """Density (g/cm³) written on the first line of the material's Composition file.

    Raises CoincidenceError when the material cannot be found, so a mistyped
    material name is reported instead of silently getting density 1.0.
    """
    name = str(material_name).strip()
    if not name or name.lower() == "vacuum":
        return 0.0
    roots = [folder / "Composition" for folder in material_roots(data_directory)]
    for root in roots:
        if not root.is_dir():
            continue
        # Exact file name first, then the same name with different upper/lower case.
        target = root / f"{name}.txt"
        if not target.is_file():
            target = next((p for p in root.glob("*.txt") if p.stem.lower() == name.lower()), None)
        if target is None:
            continue
        try:
            text = target.read_text(encoding="utf-8", errors="ignore")
            first_line = next(line for line in text.splitlines() if line.strip())
            density = float(first_line.split()[0])
        except (StopIteration, ValueError, OSError) as exc:
            raise CoincidenceError(f"Cannot read the density of material '{name}' in {target}") from exc
        return 0.0 if density <= 1e-12 else density
    raise CoincidenceError(f"Material '{name}' not found in any Composition folder; "
                           "check the spelling or create the material")


def mode_name(value: str) -> str:
    """Standard geometry name: "cylindrical", "marinelli" or "well"."""
    value = ALIASES.get(value.lower(), value.lower())
    if value not in MODES:
        raise CoincidenceError("Choose cylinder, marinelli or well")
    return value


def fields(mode: str, kind: str, extended: bool = False) -> list[tuple[str, str]]:
    """(label, unit) of every field of a model.

    kind is "detector", "sample" or "standard" (sample and standard have the
    same fields). extended=True adds the optional well-detector fields.
    """
    if kind == "detector":
        if mode == "well":
            return WELL_DETECTOR + WELL_DETECTOR_OPTIONAL if extended else WELL_DETECTOR
        if mode == "marinelli":
            # MEFFTRAN has no absorber: fields 12, 13 and 18 do not exist.
            return CYLINDER_DETECTOR[:12] + CYLINDER_DETECTOR[14:18]
        return CYLINDER_DETECTOR
    if mode == "marinelli":
        return MARINELLI_SOURCE
    if mode == "well":
        # Field 4 is the distance from the well bottom instead of a gap to the absorber.
        return CYLINDER_SOURCE[:4] + [("Sample bottom–well bottom distance", "mm")] + CYLINDER_SOURCE[5:]
    return CYLINDER_SOURCE


def _checked_number(label: str, value, unit: str) -> float:
    """The value as a finite, nonnegative number, or a clear error."""
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise CoincidenceError(f"{label}: enter a number in {unit}") from exc
    if isinstance(value, bool) or not math.isfinite(number) or number < 0:
        raise CoincidenceError(f"{label}: enter a finite, nonnegative value")
    return number


def _checked_material(label: str, value) -> str:
    """A material name that is safe to use as a file name."""
    name = str(value).strip()
    if not name or name in {".", ".."} or any(c in name for c in '/\\:\r\n'):
        raise CoincidenceError(f"{label}: choose a material name")
    return name


def _checked_values(definition, values) -> list:
    """Check every value against its field definition (number or material)."""
    return [_checked_material(label, value) if unit == "material" else _checked_number(label, value, unit)
            for (label, unit), value in zip(definition, values)]


def _well_detector_from_dict(values: dict) -> list:
    """The 12 well-detector fields from a dict (several key spellings accepted)."""
    def get(*keys, default=None):
        return next((values[key] for key in keys if key in values), default)
    absorber = get("absorber_thickness", "dd", "Absorber thickness", default=0.0)
    return [get("crystal_diameter", "dr", "Crystal diameter"),
            get("crystal_length", "dl", "Crystal length"),
            absorber,
            get("well_diameter", "well_d", "Well diameter"),
            get("well_length", "well_h", "Well length"),
            get("crystal_material", "dmat", "Crystal material", default="Ge"),
            get("absorber_material", "amat", "Absorber material", default="aluminium"),
            get("mantle_dead_layer", "side_dead_layer", "Mantle (side) dead layer", default=absorber),
            get("bottom_dead_layer", "Bottom dead layer", default=absorber),
            get("holder_thickness", "Mount cup (holder) thickness", default=0.0),
            get("sample_offset", "Well bottom sample offset", default=0.0),
            get("holder_material", "Mount cup (holder) material", default="copper")]


def _validate_well_detector(values) -> list:
    """Check a well detector (7 to 12 fields) and return all 12 fields."""
    if not 7 <= len(values) <= 12:
        raise CoincidenceError(f"WEFFTRAN detector: expected 7 to 12 fields, got {len(values)}")
    checked = _checked_values(WELL_DETECTOR + WELL_DETECTOR_OPTIONAL, values)
    # Missing optional fields: both dead layers default to the absorber thickness.
    absorber = checked[2]
    checked += [absorber, absorber, 0.0, 0.0, "copper"][len(checked) - 7:]

    crystal_diameter, crystal_length, _, well_diameter, well_length = checked[:5]
    mantle_dead_layer, bottom_dead_layer = checked[7], checked[8]
    if min(crystal_diameter, crystal_length) <= 0:
        raise CoincidenceError("Crystal diameter and length must be positive")
    if (well_diameter <= 0 or well_length <= 0 or well_diameter >= crystal_diameter
            or well_length >= crystal_length):
        raise CoincidenceError("The well must fit inside the crystal")
    if 2 * mantle_dead_layer >= crystal_diameter - well_diameter:
        raise CoincidenceError("Mantle dead layer is too thick for the crystal mantle")
    if bottom_dead_layer >= crystal_length - well_length:
        raise CoincidenceError("Bottom dead layer is too thick for the crystal base")
    return checked


def validate_model(mode: str, kind: str, values, data_directory=None) -> list:
    """Check a model and return its values (numbers as float, materials as str).

    ``values`` may be a list in file order or a dict keyed by field label.
    A cylindrical detector given in MEFFTRAN form (16 fields) is converted,
    and the other way round, so models can be shared between the two.
    A source without density (7 fields) gets the material's default density.
    """
    if isinstance(values, dict):
        if mode == "well" and kind == "detector":
            values = _well_detector_from_dict(values)
        else:
            values = [values.get(label, values.get(label.lower().replace(" ", "_")))
                      for label, _ in fields(mode, kind)]
            if kind != "detector" and len(values) == 8 and values[7] is None:
                material = values[5] if values[5] is not None else "water"
                values[7] = default_material_density(material, data_directory=data_directory)

    if mode == "well" and kind == "detector":
        return _validate_well_detector(values)

    if kind == "detector":
        if mode == "marinelli" and len(values) == 19:
            # EFFTRAN (19 fields) -> MEFFTRAN (16): drop the absorber fields 12, 13 and 18.
            values = list(values[:12]) + [values[14], values[15], values[16], values[17]]
        elif mode in ("cylindrical", "efftran") and len(values) == 16:
            # MEFFTRAN (16 fields) -> EFFTRAN (19): no absorber (0 mm), material "copper".
            values = list(values[:12]) + [0.0, 0.0, values[12], values[13], values[14], values[15], "copper"]

    definition = fields(mode, kind)
    if kind != "detector" and len(values) == 7:
        values = list(values) + [default_material_density(values[5], data_directory=data_directory)]
    if len(values) != len(definition):
        raise CoincidenceError(f"{MODES[mode]} {kind}: expected {len(definition)} fields, got {len(values)}")
    checked = _checked_values(definition, values)

    # Geometry checks.
    if kind == "detector":
        end_cap_diameter, crystal_diameter, crystal_length = checked[0], checked[2], checked[3]
        top_dead_layer, side_dead_layer = checked[4], checked[5]
        if min(crystal_diameter, crystal_length) <= 0:
            raise CoincidenceError("Crystal diameter and length must be positive")
        if end_cap_diameter < crystal_diameter or top_dead_layer >= crystal_length or 2 * side_dead_layer >= crystal_diameter:
            raise CoincidenceError("Check end cap, crystal and dead-layer dimensions")
    elif mode == "marinelli" and checked[1] >= checked[0]:
        raise CoincidenceError("Marinelli hole diameter must be smaller than the outer diameter")
    elif mode == "well" and (checked[0] <= 2 * checked[3] or checked[1] <= 0):
        raise CoincidenceError("The well sample must have a positive active radius and filling height")
    return checked


def model_bytes(mode: str, kind: str, values) -> bytes:
    """A model as the text file the Fortran programs read (one value per line)."""
    validated = validate_model(mode, kind, values)
    if mode == "well" and kind == "detector" and len(values) == 7:
        validated = validated[:7]   # keep the original 7-line format when no optional field was given
    lines = (format(value, ".17g") if isinstance(value, (int, float)) else value for value in validated)
    return ("\n".join(lines) + "\n").encode("cp1252")


def find_model(mode: str, kind: str, name, data_directory=None) -> Path:
    """Find a model file by path or by name (laboratory data first, then bundled models)."""
    path = Path(name).expanduser()
    if path.is_file():
        return path.resolve()
    folder = {"detector": "Detector", "sample": "Sample", "standard": "Standard"}[kind]
    candidates = []
    for index, root in enumerate(_user_data_folders(data_directory)):
        candidates += [root / folder / name, root / folder / (name + ".txt"), root / name, root / (name + ".txt")]
        if index == 0 and data_directory and kind == "sample":
            # A sample may also be one of the laboratory's standards.
            candidates += [root / "Standard" / name, root / "Standard" / (name + ".txt")]
    candidates += [ASSETS / mode / folder / name, ASSETS / mode / folder / (name + ".txt")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise CoincidenceError(f"Cannot find {kind} '{name}'. Use a file path or a bundled model name.")


# Spellings of the well-detector optional fields in "key = value" lines.
# Keys are compared without spaces, underscores or capitals.
WELL_OPTIONAL_KEYS = [
    ("mantledeadlayer", "sidedeadlayer", "mantledl"),
    ("bottomdeadlayer", "bottomdl"),
    ("holderthickness", "mountcupthickness", "holderth"),
    ("sampleoffset", "wellbottomsampleoffset", "welloffset"),
    ("holdermaterial", "mountcupmaterial", "holdermat"),
]


def read_model(mode: str, kind: str, path) -> list:
    """Read and check a model file.

    Lines starting with "#" and text after "#" are comments. Well-detector
    files may give the optional fields as "key = value" lines.
    """
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    if "�" in text:   # not UTF-8: the original programs wrote Windows-1252
        text = raw.decode("cp1252")
    lines = []
    key_values = {}
    for line in text.splitlines():
        code = line.strip().split("#")[0].strip()
        if not code:
            continue
        if "=" in code:
            key, value = (token.strip() for token in code.split("=", 1))
            key_values[re.sub(r"[^a-z0-9]", "", key.lower())] = value
        else:
            lines.append(code)

    if mode == "well" and kind == "detector" and key_values:
        # The 7 required fields come from the plain lines, in order.
        required_defaults = [0.0, 0.0, 0.0, 0.0, 0.0, "Ge", "aluminium"]
        merged = list(lines[:7]) + required_defaults[len(lines[:7]):]
        # Each of the 5 optional fields keeps its own slot (7 to 11). Its value
        # is: the "key = value" line if present, else the plain line at that
        # position, else the default (dead layers default to the absorber
        # thickness, like in validate_model).
        absorber = merged[2]
        optional_defaults = [absorber, absorber, 0.0, 0.0, "copper"]
        for slot, (aliases, default) in enumerate(zip(WELL_OPTIONAL_KEYS, optional_defaults), start=7):
            value = next((key_values[alias] for alias in aliases if alias in key_values), None)
            if value is None:
                value = lines[slot] if len(lines) > slot else default
            merged.append(value)
        return validate_model(mode, kind, merged)

    return validate_model(mode, kind, lines)


CALIBRATION_HEADERS = {"energy_kev", "energy", "e [kev]", "e[kev]"}


def calibration_rows(path) -> list[dict]:
    """Calibration points from a .CAL/.EFT file or a text/CSV table.

    Text rows: energy_keV, efficiency [, relative uncertainty %], separated by
    commas or spaces. Lines starting with "#" are comments; one header line
    (e.g. "energy_keV,...") may come first.
    """
    path = Path(path)
    if path.suffix.lower() in {".cal", ".eft"}:
        from .software import read_cal
        return validate_calibration(read_cal(path))
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        tokens = next(csv.reader([line])) if "," in line else line.split()
        try:
            values = [float(token.replace("D", "E").replace("d", "e")) for token in tokens]
        except ValueError:
            if not rows and tokens and tokens[0].strip().lower() in CALIBRATION_HEADERS:
                continue   # the header line
            raise CoincidenceError("Unexpected text inside calibration data; only a named header may be skipped")
        if len(values) not in {2, 3}:
            raise CoincidenceError("Calibration rows: energy_keV, efficiency, relative_uncertainty_percent")
        rows.append({"energy_keV": values[0], "efficiency": values[1],
                     "u_rel_percent": values[2] if len(values) == 3 else 0.})
    return validate_calibration(rows)


def validate_calibration(rows) -> list[dict]:
    """Check 2 to 93 calibration points (93 is the Genie CAL maximum)."""
    if not 2 <= len(rows) <= 93:
        raise CoincidenceError("Enter 2 to 93 calibration points")
    result = []
    previous_energy = 0.
    for row in rows:
        try:
            energy, efficiency, uncertainty = (float(row[key]) for key in ("energy_keV", "efficiency", "u_rel_percent"))
        except (ValueError, TypeError, KeyError) as exc:
            raise CoincidenceError("Invalid calibration point") from exc
        if (not all(math.isfinite(v) for v in (energy, efficiency, uncertainty))
                or energy <= previous_energy or not 0 < efficiency <= 1 or uncertainty < 0):
            raise CoincidenceError("Calibration energies must increase; efficiency is an absolute "
                                   "probability (0–1); uncertainty is relative %")
        result.append({"energy_keV": energy, "efficiency": efficiency, "u_rel_percent": uncertainty})
        previous_energy = energy
    return result


def normalize_nuclides(names) -> list[str]:
    """Nuclide names in standard spelling, without duplicates.

    Each item may hold several names separated by commas, semicolons or
    spaces. "Co60", "co-60" and "CO-60" all become "CO-60"; "Am242m" becomes "AM-242M".
    """
    output = []
    for name in names:
        for token in re.split(r"[,;\s]+", name.strip()):
            if not token:
                continue
            match = re.fullmatch(r"([A-Za-z]{1,2})-?(\d+)([mM]?)", token)
            if not match:
                raise CoincidenceError(f"Invalid nuclide '{token}'; example: Co-60")
            formatted = f"{match[1].upper()}-{match[2]}{match[3].upper()}"
            if formatted not in output:
                output.append(formatted)
    return output


def canonical_nuclide(name) -> str:
    """Standard spelling of one nuclide name, used to compare names.

    "Co60", "co-60" and "CO-60" all become "CO-60". Names that are not a
    simple nuclide name (for example "RA-226+") are only upper-cased.
    """
    try:
        names = normalize_nuclides([str(name)])
    except CoincidenceError:
        names = []
    return names[0] if len(names) == 1 else str(name).strip().upper()
