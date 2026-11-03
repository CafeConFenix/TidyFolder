@echo off
REM Builds a single-file portable executable: dist\TidyFolder.exe
REM Requires Python 3.10+ installed and available as "python".
setlocal
cd /d "%~dp0"

if not exist .venv (
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements-dev.txt || goto :error

set ICON=
if exist assets\icon.ico set ICON=--icon assets\icon.ico

pyinstaller --noconfirm --clean --onefile --windowed --name TidyFolder %ICON% --collect-all customtkinter run.py || goto :error

echo.
echo Done! Your portable app is: dist\TidyFolder.exe
pause
exit /b 0

:error
echo.
echo Build failed. See the messages above.
pause
exit /b 1
