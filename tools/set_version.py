#!/usr/bin/env python3
"""EffSuite Version Management Utility.

Usage:
    python tools/set_version.py <new_version>
    python tools/set_version.py --show

Examples:
    python tools/set_version.py 0.1.1-beta
    python tools/set_version.py 1.0.0
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERSION_FILES = {
    # 1. Python package definition
    ROOT / "src/effsuite/__init__.py": [
        (r'__version__\s*=\s*["\'][^"\']+["\']', '__version__ = "{version}"'),
    ],
    # 2. Pyproject TOML
    ROOT / "pyproject.toml": [
        (r'version\s*=\s*["\'][^"\']+["\']', 'version = "{version}"'),
    ],
    # 3. Inno Setup script
    ROOT / "installer/EffSuite.iss": [
        (r'#define MyAppVersion\s*["\'][^"\']+["\']', '#define MyAppVersion "{version}"'),
    ],
    # 4. GitHub README badge & attribution
    ROOT / "README.md": [
        (r'https://img\.shields\.io/badge/Version-[^\s"]+-yellow\.svg" alt="Version [^"]+"',
         lambda v: f'https://img.shields.io/badge/Version-{v.replace("-", "--")}-yellow.svg" alt="Version {v}"'),
        (r'\*EffSuite \(v[^\)]+\) built by', '*EffSuite (v{version}) built by'),
    ],
}


def get_current_version() -> str:
    init_file = ROOT / "src/effsuite/__init__.py"
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_file.read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError("Could not find __version__ in src/effsuite/__init__.py")
    return match.group(1)


def set_version(new_version: str) -> None:
    current = get_current_version()
    print(f"Current version : {current}")
    print(f"Target version  : {new_version}")
    print("-" * 50)

    modified_count = 0
    for file_path, replacements in VERSION_FILES.items():
        if not file_path.is_file():
            print(f"[SKIP] File not found: {file_path.relative_to(ROOT)}")
            continue

        text = file_path.read_text(encoding="utf-8")
        updated = text
        for pattern, replacement in replacements:
            if callable(replacement):
                target_str = replacement(new_version)
            else:
                target_str = replacement.format(version=new_version)
            updated = re.sub(pattern, target_str, updated)

        if updated != text:
            file_path.write_text(updated, encoding="utf-8")
            print(f"[UPDATED] {file_path.relative_to(ROOT)}")
            modified_count += 1
        else:
            print(f"[UNCHANGED] {file_path.relative_to(ROOT)}")

    print("-" * 50)
    print(f"Version successfully updated to '{new_version}' across {modified_count} files!")


def main():
    parser = argparse.ArgumentParser(description="EffSuite Version Management Utility")
    parser.add_argument("version", nargs="?", help="New version string, e.g., '0.1.1-beta' or '1.0.0'")
    parser.add_argument("--show", action="store_true", help="Show current version")

    args = parser.parse_args()

    if args.show or not args.version:
        print(f"EffSuite current version: {get_current_version()}")
        return

    set_version(args.version.strip())


if __name__ == "__main__":
    main()
