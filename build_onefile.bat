@echo off
setlocal enableextensions

rem ============================================================
rem  build_onefile.bat
rem  Produces a portable one-file executable using Nuitka.
rem ============================================================

set "PYTHON=python"
set "APP_NAME=Speech Widget"
set "APP_DESC=Speech recognition widget"
set "COMPANY_NAME=Bessonniy"
set "ICO_PATH=assets\icon.ico"
set "MODEL_PATH=model"
set "OUTPUT_DIR_ONEFILE=nuitka_dist_onefile"
set "APP_EXECUTABLE=SpeechWidget.exe"

set "PYTHONDONTWRITEBYTECODE=1"

rem --- Read version from speech_widget.py without importing dependencies ---
for /f "usebackq delims=" %%I in (`%PYTHON% -c "import ast, pathlib, sys; module = ast.parse(pathlib.Path('speech_widget.py').read_text(encoding='utf-8')); version = next((node.value.value for node in module.body if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == '__version__' for t in node.targets) and isinstance(node.value, ast.Constant)), None); sys.exit(1) if version is None else print(version)"`) do set "APP_VERSION=%%I"

if not defined APP_VERSION (
    echo [ERROR] Could not read __version__ from speech_widget.py
    exit /b 1
)

rem --- Remove previous build output to avoid mixing old files ---
if exist "%OUTPUT_DIR_ONEFILE%" (
    echo Removing existing directory "%OUTPUT_DIR_ONEFILE%"...
    rd /s /q "%OUTPUT_DIR_ONEFILE%"
)

echo Building one-file executable with Nuitka...
call "%PYTHON%" -m nuitka ^
    --onefile ^
    --windows-console-mode=disable ^
    --enable-plugin=pyside6 ^
    --msvc=latest ^
    --include-data-dir=%MODEL_PATH%=%MODEL_PATH% ^
    --include-data-dir=assets=assets ^
    --output-dir=%OUTPUT_DIR_ONEFILE% ^
    --windows-icon-from-ico=%ICO_PATH% ^
    --product-name="%APP_NAME%" ^
    --file-description="%APP_DESC%" ^
    --company-name="%COMPANY_NAME%" ^
    --file-version=%APP_VERSION% ^
    --output-filename=%APP_EXECUTABLE% ^
    speech_widget.py
if errorlevel 1 (
    echo [ERROR] Nuitka failed to build the one-file executable.
    exit /b 1
)

echo Done. Result: %OUTPUT_DIR_ONEFILE%\%APP_EXECUTABLE%
pause
endlocal
