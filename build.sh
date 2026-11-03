#!/usr/bin/env bash
# Builds a single-file executable for the current OS (Linux/macOS): dist/TidyFolder
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean --onefile --windowed --name TidyFolder --collect-all customtkinter run.py
echo "Done! Your app is in dist/"
