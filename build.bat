@echo off
REM Builds ONE portable file: dist\TidyFolder.exe  (share that file, nothing else is needed).
REM The OCR engine (Tesseract + Spanish/English models) is fetched automatically and bundled inside.
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

echo.
echo Preparing the OCR engine. If Windows asks for permission to install Tesseract, accept it.
python scripts\prepare_tesseract.py

set OCR=
if exist vendor\tesseract\tesseract.exe goto :build
echo.
echo WARNING: the OCR engine could not be prepared.
choice /c YN /m "Build the .exe WITHOUT OCR anyway"
if errorlevel 2 goto :cancel
goto :compile

:build
set OCR=--add-data "vendor\tesseract;tesseract"

:compile
pyinstaller --noconfirm --clean --onefile --windowed --name TidyFolder %ICON% %OCR% ^
    --collect-all customtkinter --collect-all pypdfium2 --collect-all pypdfium2_raw ^
    --hidden-import keyring.backends.Windows run.py || goto :error

echo.
echo ============================================================
echo  Done! Your portable app is: dist\TidyFolder.exe
if "%OCR%"=="" (echo  NOTE: built WITHOUT OCR.) else (echo  OCR is bundled inside the .exe.)
echo  To share it: GitHub - Releases - Draft a new release - attach dist\TidyFolder.exe
echo ============================================================
pause
exit /b 0

:cancel
echo.
echo Build cancelled. Run build.bat again once Tesseract is available.
pause
exit /b 1

:error
echo.
echo Build failed. See the messages above.
pause
exit /b 1
