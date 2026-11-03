#!/usr/bin/env python3
"""Prepare ``vendor/tesseract`` so PyInstaller can bundle the OCR engine inside the .exe.

It copies ``tesseract.exe`` and its DLLs from an existing Windows installation (the
GitHub workflow installs one with Chocolatey) and downloads the compact English and
Spanish language models (tessdata_fast, Apache-2.0). Run it before PyInstaller.

Usage: python scripts/prepare_tesseract.py [--from "C:\\Program Files\\Tesseract-OCR"] [--no-download]
Exit code 0 when ``vendor/tesseract/tesseract.exe`` and the language files are ready.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "tesseract"
LANGS = ("eng", "spa")
MODEL_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{}.traineddata"
KNOWN_INSTALLS = (
    r"C:\Program Files\Tesseract-OCR",
    r"C:\Program Files (x86)\Tesseract-OCR",
)


def find_install(explicit: str | None) -> Path | None:
    candidates = [Path(explicit)] if explicit else []
    found = shutil.which("tesseract")
    if found:
        candidates.append(Path(found).parent)
    candidates += [Path(p) for p in KNOWN_INSTALLS]
    for folder in candidates:
        if (folder / "tesseract.exe").exists():
            return folder
    return None


def install_tesseract() -> None:
    """Install Tesseract automatically on Windows (winget first, then Chocolatey).

    Windows may show a single permission prompt (UAC); accept it. Failures are ignored here:
    the caller simply looks for the installation again afterwards.
    """
    attempts = []
    if shutil.which("winget"):
        attempts.append(["winget", "install", "--id", "UB-Mannheim.TesseractOCR", "-e", "--silent",
                         "--accept-package-agreements", "--accept-source-agreements"])
    if shutil.which("choco"):
        attempts.append(["choco", "install", "tesseract", "-y", "--no-progress"])
    for command in attempts:
        print("Installing Tesseract with:", " ".join(command[:2]), "...")
        try:
            subprocess.run(command, check=False, timeout=900)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  could not run {command[0]}: {exc}", file=sys.stderr)
            continue
        if find_install(None) is not None:
            return


def copy_engine(src: Path) -> None:
    VENDOR.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_file() and (item.suffix.lower() == ".dll" or item.name.lower() == "tesseract.exe"):
            shutil.copy2(item, VENDOR / item.name)


def download_models() -> None:
    tessdata = VENDOR / "tessdata"
    tessdata.mkdir(parents=True, exist_ok=True)
    for lang in LANGS:
        target = tessdata / f"{lang}.traineddata"
        if target.exists() and target.stat().st_size > 100_000:
            continue
        print(f"Downloading {lang}.traineddata ...")
        urllib.request.urlretrieve(MODEL_URL.format(lang), target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="source", help="folder of an existing Tesseract installation")
    parser.add_argument("--no-download", action="store_true", help="do not download language models")
    args = parser.parse_args()

    if not (VENDOR / "tesseract.exe").exists():
        install = find_install(args.source)
        if install is None and not args.source:
            install_tesseract()
            install = find_install(None)
        if install is None:
            print(
                "Tesseract was not found and could not be installed automatically, so the OCR engine "
                "will NOT be bundled.\nInstall it once from https://github.com/UB-Mannheim/tesseract/wiki "
                "(or pass --from <folder>) and run this script again.",
                file=sys.stderr,
            )
            return 1
        print(f"Copying Tesseract from {install} ...")
        copy_engine(install)
    if not args.no_download:
        try:
            download_models()
        except OSError as exc:
            print(f"Could not download the language models: {exc}", file=sys.stderr)
            return 1
    ready = (VENDOR / "tesseract.exe").exists() and all(
        (VENDOR / "tessdata" / f"{lang}.traineddata").exists() for lang in LANGS
    )
    print("OCR engine ready in vendor/tesseract" if ready else "OCR engine incomplete", file=sys.stderr if not ready else sys.stdout)
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
