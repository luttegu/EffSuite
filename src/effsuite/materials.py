"""Materials: compositions (as in the original Material.xls workbook) and their
attenuation tables, calculated with NIST XCOM.

A material has two files in a data folder:

* Composition/<name>.txt : the density, then pairs of "formula" and "weight"
  lines (for example "H2O" and "1"). This is what the user enters.
* Material/<name>.txt    : the attenuation table calculated by XCOM, which
  the Fortran engines read.

A third file, Material_Metadata/<name>.json, records how the table was made.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from .model_io import COMMON_DATA
from .parallel_coincidence import CalculationCancelled, CoincidenceError, _publish_new, _terminate

XCOM = Path(__file__).parent / "assets/xcom"
TEMPLATE = Path(__file__).parent / "assets/templates/Material_Composition.xlsx"
ELEMENTS = set("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As "
               "Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu "
               "Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np "
               "Pu Am Cm Bk Cf Es Fm".split())
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}

# Cells of the "Material" sheet in the Excel template.
NAME_CELL, DENSITY_CELL = "D4", "D20"
COMPONENT_ROWS = range(9, 19)   # formula in column C, weight in column D (up to 10 compounds)


# ---------------------------------------------------------------------------
# Checking and writing a composition
# ---------------------------------------------------------------------------

def finite(value, label: str) -> float:
    """The value as a finite number, or an error naming the field."""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CoincidenceError(label + ": enter a finite number") from exc
    if isinstance(value, bool) or not math.isfinite(number):
        raise CoincidenceError(label + ": enter a finite number")
    return number


def _check_name(name: str) -> None:
    """The material name becomes a file name, so it must be safe on Windows."""
    if (not name or len(name) > 60 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.endswith((".", " ")) or name in {".", ".."}):
        raise CoincidenceError("Material name: use 1–60 filename-safe characters")
    if name.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
        raise CoincidenceError("Material name is reserved by Windows")
    try:
        name.encode("cp1252")
    except UnicodeEncodeError as exc:
        raise CoincidenceError("Material name must use characters supported by the original Windows text format") from exc


def _check_formula(formula: str) -> None:
    """XCOM accepts only flat formulas: element symbols with optional counts."""
    tokens = list(re.finditer(r"([A-Z][a-z]?)([0-9]*)", formula))
    rebuilt = "".join(token.group() for token in tokens)
    bad_token = any(token[1] not in ELEMENTS or (token[2] and not 1 <= int(token[2]) <= 100000) for token in tokens)
    if not formula or len(formula) > 70 or rebuilt != formula or bad_token:
        raise CoincidenceError(f"Invalid XCOM formula {formula!r}; use flat formulas such as H2O, NaCl, CaO, "
                               "without parentheses or isotope labels")


def validate_composition(definition) -> dict:
    """Check a material definition and return it in standard form.

    The definition is {"name", "density_g_cm3", "components": [{"formula", "weight"}]}.
    Weights are relative (they do not need to add up to 1).
    """
    if not isinstance(definition, dict):
        raise CoincidenceError("Material definition must be a JSON object")
    if definition.get("schema_version", 1) != 1:
        raise CoincidenceError("Unsupported material definition schema")
    name = str(definition.get("name", "")).strip()
    _check_name(name)
    density = finite(definition.get("density_g_cm3"), "Density [g/cm³]")
    if density <= 0:
        raise CoincidenceError("Density [g/cm³] must be positive; it is an input, not calculated from the mixture")

    rows = definition.get("components")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10:
        raise CoincidenceError("Enter 1–10 compounds, as in the original Material workbook")
    components = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise CoincidenceError("Each component must contain formula and weight fields")
        formula = str(row.get("formula", "")).strip()
        _check_formula(formula)
        if formula in seen:
            raise CoincidenceError("Duplicate compound: " + formula)
        seen.add(formula)
        weight = finite(row.get("weight"), "Weight for " + formula)
        if weight < 0:
            raise CoincidenceError("Compound weights must be nonnegative")
        components.append({"formula": formula, "weight": weight})

    try:
        total = math.fsum(component["weight"] for component in components)
    except OverflowError as exc:
        raise CoincidenceError("Total weight is too large; scale all relative weights by a common factor") from exc
    if not math.isfinite(total) or total <= 0:
        raise CoincidenceError("At least one compound must have a positive weight")
    return {"schema_version": 1, "name": name, "density_g_cm3": density, "components": components}


def composition_bytes(definition) -> bytes:
    """The Composition/<name>.txt file: density, then formula and weight lines."""
    d = validate_composition(definition)
    lines = [format(d["density_g_cm3"], ".17g")]
    for component in d["components"]:
        lines += [component["formula"], format(component["weight"], ".17g")]
    return ("\r\n".join(lines) + "\r\n").encode("cp1252")   # Windows line endings, like the original


# ---------------------------------------------------------------------------
# Reading a composition (JSON, Excel template, or original text file)
# ---------------------------------------------------------------------------

def _xlsx_inputs(path) -> dict[str, str]:
    """Values of the input cells of the template's "Material" sheet (.xlsx/.xlsm).

    An .xlsx file is a zip of XML files; we read only the cells we need,
    without any Excel library.
    """
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    wanted = {NAME_CELL, DENSITY_CELL, *[f"{column}{row}" for column in "CD" for row in COMPONENT_ROWS]}
    with zipfile.ZipFile(path) as archive:
        if sum(item.file_size for item in archive.infolist()) > 20_000_000:
            raise CoincidenceError("Material workbook is too large")
        # Find the XML file of the "Material" sheet.
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet = next((s for s in workbook.findall("m:sheets/m:sheet", ns) if s.attrib["name"] == "Material"), None)
        if sheet is None:
            raise CoincidenceError("The workbook needs a Material sheet in the supplied template layout")
        relation_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(r.attrib["Target"] for r in relations if r.attrib["Id"] == relation_id)
        target = target.lstrip("/") if target.startswith("/") else "xl/" + target

        # Text cells usually point into a shared list of strings.
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(n.itertext()) for n in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns)]

        cells = {}
        for cell in ET.fromstring(archive.read(target)).findall(".//m:sheetData/m:row/m:c", ns):
            address = cell.attrib["r"]
            if address not in wanted:
                continue
            if cell.find("m:f", ns) is not None:
                raise CoincidenceError(address + ": composition inputs must be entered as values, not formulas; use Paste Values")
            value, cell_type = cell.find("m:v", ns), cell.attrib.get("t")
            if value is None and cell_type != "inlineStr":
                cells[address] = ""                                   # empty cell
            elif cell_type == "s":
                cells[address] = shared[int(value.text)]              # shared text
            elif cell_type == "inlineStr":
                cells[address] = "".join(cell.find("m:is", ns).itertext())
            else:
                cells[address] = value.text                           # number
        return cells


def _xls_inputs(path) -> dict[str, object]:
    """Same as _xlsx_inputs, for the old Excel 97 format (.xls)."""
    import xlrd
    try:
        sheet = xlrd.open_workbook(str(path)).sheet_by_name("Material")
    except xlrd.XLRDError as exc:
        raise CoincidenceError(f"Cannot read the Excel 97 workbook: {exc}") from exc
    cells = {}
    for column in "CD":
        for row in [4, 20, *COMPONENT_ROWS]:
            column_index = ord(column) - ord("A")
            inside = row <= sheet.nrows and column_index < sheet.ncols
            cells[f"{column}{row}"] = sheet.cell_value(row - 1, column_index) if inside else ""
    return cells


def load_composition(path, name=None) -> dict:
    """Read a material definition from .json, .xlsx/.xlsm/.xls or a Composition .txt file."""
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            definition = json.loads(path.read_text(encoding="utf-8-sig"))
        elif suffix in {".xlsx", ".xlsm", ".xls"}:
            cells = _xls_inputs(path) if suffix == ".xls" else _xlsx_inputs(path)
            components = []
            for row in COMPONENT_ROWS:
                formula, weight = cells.get(f"C{row}", ""), cells.get(f"D{row}", "")
                if formula == "" and weight == "":
                    continue   # empty row
                components.append({"formula": formula, "weight": weight})
            definition = {"name": cells.get(NAME_CELL) or path.stem, "density_g_cm3": cells.get(DENSITY_CELL),
                          "components": components}
        else:
            # Original text format: density, then alternating formula and weight lines.
            lines = [line.strip() for line in path.read_bytes().decode("cp1252").splitlines() if line.strip()]
            if not lines or len(lines) % 2 != 1:
                raise CoincidenceError("Original composition format: density, then alternating formula and weight lines")
            definition = {"name": path.stem, "density_g_cm3": lines[0],
                          "components": [{"formula": lines[i], "weight": lines[i + 1]} for i in range(1, len(lines), 2)]}
        if name:
            definition["name"] = name
        return validate_composition(definition)
    except (OSError, ValueError, KeyError, IndexError, AttributeError, zipfile.BadZipFile, ET.ParseError, StopIteration) as exc:
        raise CoincidenceError("Cannot read material definition: " + str(exc)) from exc


def save_definition(path, definition) -> None:
    """Save a material definition as JSON (never overwrites a file)."""
    _publish_new(Path(path), (json.dumps(validate_composition(definition), indent=2) + "\n").encode())


# ---------------------------------------------------------------------------
# XCOM: attenuation tables
# ---------------------------------------------------------------------------

def attenuation_rows(raw: bytes) -> list[list[float]]:
    """Check an XCOM table and return its numeric rows (8 values per energy)."""
    result = []
    for line in raw.decode("cp1252").splitlines():
        tokens = line[6:].split()   # the first 6 characters mark absorption edges
        if len(tokens) != 8:
            continue
        try:
            row = [float(token.replace("D", "E")) for token in tokens]
        except ValueError:
            continue   # a header line
        if not all(math.isfinite(value) and value >= 0 for value in row) or row[0] <= 0:
            raise CoincidenceError("XCOM produced invalid attenuation coefficients")
        if result and row[0] < result[-1][0]:
            raise CoincidenceError("XCOM energy grid is not monotone")
        result.append(row)
    if len(result) < 80 or result[0][0] > .00101 or result[-1][0] < 100000:
        raise CoincidenceError("XCOM did not produce a complete standard-grid attenuation table")
    return result


def _xcom_program() -> Path:
    """The XCOM program built for this operating system."""
    target = "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"
    return XCOM / "bin" / target / ("xcom.exe" if os.name == "nt" else "xcom")


@lru_cache(maxsize=1)
def _xcom_fingerprint() -> tuple[str, tuple[tuple[str, str], ...]]:
    """SHA-256 of the XCOM program and of its 100 data files.

    Computed once per session (remembered by lru_cache): these files belong to
    the installation and do not change while the program runs.
    """
    program_hash = sha256(_xcom_program().read_bytes()).hexdigest()
    data_hashes = tuple((p.name, sha256(p.read_bytes()).hexdigest()) for p in sorted(XCOM.glob("MDATX3.*")))
    return program_hash, data_hashes


def _xcom_input(d: dict) -> str:
    """The answers typed into XCOM: the same choices as the original Material.xls "Save" button."""
    answers = [d["name"], "4", str(len(d["components"]))]   # 4 = mixture of compounds
    for component in d["components"]:
        answers += [component["formula"], format(component["weight"], ".17g")]
    answers += ["1", "1", "material.txt", "1"]               # standard energy grid, output file
    return "\n".join(answers) + "\n"


def generate_attenuation(definition, *, cancel=None, timeout=60, progress=None) -> tuple[bytes, dict]:
    """Run XCOM for one material; return (table bytes, metadata)."""
    d = validate_composition(definition)
    stop = cancel if cancel is not None else threading.Event()
    if stop.is_set():
        raise CalculationCancelled("Material calculation cancelled")
    program = _xcom_program()
    if not program.is_file():
        raise CoincidenceError("Build XCOM for this platform with tools/build_xcom.py")
    input_text = _xcom_input(d)
    if progress:
        progress("XCOM: generating attenuation table")

    with tempfile.TemporaryDirectory(prefix="effsuite-xcom-") as temporary:
        work = Path(temporary)
        # XCOM expects its data files in its working folder.
        for path in XCOM.glob("MDATX3.*"):
            if stop.is_set():
                raise CalculationCancelled("Material calculation cancelled")
            shutil.copyfile(path, work / path.name)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        process = subprocess.Popen([str(program.resolve())], cwd=work, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, shell=False, creationflags=flags)
        started = time.monotonic()
        try:
            # Wait in short steps so Cancel and the time limit are checked often.
            # The answers are sent with the first communicate() call only.
            answers = input_text.encode("cp1252")
            while True:
                if stop.is_set():
                    raise CalculationCancelled("Material calculation cancelled")
                if time.monotonic() - started > timeout:
                    raise CoincidenceError("XCOM time limit exceeded")
                try:
                    log = process.communicate(input=answers, timeout=.1)[0]
                    break
                except subprocess.TimeoutExpired:
                    answers = None
        finally:
            _terminate(process)
        if process.returncode or not (work / "material.txt").is_file():
            raise CoincidenceError("XCOM failed: " + log.decode("cp1252", errors="replace")[-2000:])
        raw = (work / "material.txt").read_bytes()
        rows = attenuation_rows(raw)

    program_hash, data_hashes = _xcom_fingerprint()
    metadata = {"xcom_version": "3.1 supplied with original EFFTRAN", "executable_sha256": program_hash,
                "data_sha256": dict(data_hashes), "input_text": input_text, "row_count": len(rows),
                "output_sha256": sha256(raw).hexdigest()}
    return raw, metadata


# ---------------------------------------------------------------------------
# Creating a material in a data folder
# ---------------------------------------------------------------------------

def default_library(geometry=None) -> Path:
    """The laboratory data folder where new materials are saved by default.

    Same folder as the rest of EffSuite uses (see paths.get_data_dir), so a
    material created here is found by the next calculation.
    """
    from .paths import get_data_dir, get_effsuite_root
    return get_data_dir() or get_effsuite_root() / "Data"


def _new_library(staged: Path, base: Path) -> None:
    """Fill a new data folder with a copy of the base data (bundled or chosen)."""
    staged.mkdir()
    for folder in ("Composition", "Material", "Decay_Data", "Material_Metadata"):
        if (base / folder).is_dir():
            shutil.copytree(base / folder, staged / folder)
    for name in ("param.txt", "zzaa.txt", "kordaten.txt"):
        if (base / name).is_file():
            shutil.copyfile(base / name, staged / name)
    (staged / "Composition").mkdir(parents=True, exist_ok=True)
    (staged / "Material").mkdir(parents=True, exist_ok=True)


def create_material(definition, library=None, *, geometry="cylindrical", base_directory=None,
                    cancel=None, progress=None, overwrite=False) -> dict:
    """Calculate a material's attenuation table and save its three files.

    ``library`` is the data folder (default: default_library()). A new or
    empty folder is first filled with a copy of the base data. Existing
    materials are only replaced when ``overwrite`` is True.
    """
    d = validate_composition(definition)
    if library is None:
        library = default_library(geometry)
    library = Path(library).expanduser().resolve()
    # An existing but empty folder (e.g. the Data folder made by the installer)
    # is set up exactly like a folder that does not exist yet.
    is_new_library = not library.exists() or not any(library.iterdir())
    if not is_new_library and not all((library / folder).is_dir() for folder in ("Composition", "Material")):
        raise CoincidenceError("The data folder must contain Composition and Material directories")
    name_taken = any((library / folder / (d["name"] + ".txt")).exists() for folder in ("Composition", "Material"))
    if not overwrite and not is_new_library and name_taken:
        raise CoincidenceError("Material name already exists; save under a new name to preserve the original")

    raw, metadata = generate_attenuation(d, cancel=cancel, progress=progress)
    library.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="effsuite-material-") as temporary:
        # A new library is prepared in a temporary folder and copied into place
        # at the end, so a failure never leaves a half-made library behind.
        staged = Path(temporary) / "library"
        if is_new_library:
            _new_library(staged, Path(base_directory) if base_directory else COMMON_DATA)
            target = staged
        else:
            target = library
        if not overwrite and any((target / folder / (d["name"] + ".txt")).exists() for folder in ("Composition", "Material")):
            raise CoincidenceError("This name already exists in the base library; choose a new material name")

        files = {"Material": target / "Material" / (d["name"] + ".txt"),
                 "Composition": target / "Composition" / (d["name"] + ".txt"),
                 "Material_Metadata": target / "Material_Metadata" / (d["name"] + ".json")}
        contents = {"Material": raw,
                    "Composition": composition_bytes(d),
                    "Material_Metadata": (json.dumps({"definition": d, "generation": metadata}, indent=2) + "\n").encode()}
        files["Material_Metadata"].parent.mkdir(exist_ok=True)
        written = []
        try:
            if cancel is not None and cancel.is_set():
                raise CalculationCancelled("Material calculation cancelled")
            for key, path in files.items():
                if overwrite and path.exists():
                    path.write_bytes(contents[key])
                else:
                    _publish_new(path, contents[key])
                written.append(path)
            if target == staged:
                # Copy the new library into place. If this fails (read-only or
                # missing folder...), the error is reported: never claim success
                # for files that were not written.
                try:
                    shutil.copytree(staged, library, dirs_exist_ok=True)
                except OSError as exc:
                    raise CoincidenceError(f"Cannot write the material library to {library}: {exc}") from exc
        except Exception:
            # Undo: remove the files we created (replaced files cannot be restored).
            for path in written:
                if not overwrite:
                    path.unlink(missing_ok=True)
            raise

    weights = [component["weight"] for component in d["components"]]
    total = math.fsum(weights)
    return {"definition": d, "normalized_mass_fractions": [weight / total for weight in weights],
            "data_directory": str(library),
            "composition_file": str(library / "Composition" / (d["name"] + ".txt")),
            "attenuation_file": str(library / "Material" / (d["name"] + ".txt")),
            "generation": metadata}
