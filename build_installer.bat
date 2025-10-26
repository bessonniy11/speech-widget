@echo off
setlocal enableextensions

rem ============================================================
rem  build_installer.bat
rem  Builds a standalone Nuitka directory and then an Inno Setup
rem  installer. Run this script from a Developer Command Prompt
rem  (MSVC toolchain must be available on PATH).
rem ============================================================

set "PYTHON=python"
set "APP_NAME=Speech Widget"
set "APP_DESC=Speech recognition widget"
set "COMPANY_NAME=Bessonniy"
set "ICO_PATH=assets\icon.ico"
set "MODEL_PATH=model"
set "OUTPUT_DIR_STANDALONE=nuitka_dist_installer"
set "STANDALONE_NAME=speech_widget"
set "APP_EXECUTABLE=SpeechWidget.exe"
set "INSTALLER_OUTPUT_DIR=dist_installer"
set "INSTALLER_BASENAME=SpeechWidgetInstaller"
set "INNO_SCRIPT=installer\speech_widget.iss"

set "PYTHONDONTWRITEBYTECODE=1"

rem --- Read __version__ directly from speech_widget.py ---
for /f "usebackq delims=" %%I in (`%PYTHON% -c "import ast, pathlib, sys; module = ast.parse(pathlib.Path('speech_widget.py').read_text(encoding='utf-8')); version = next((node.value.value for node in module.body if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == '__version__' for t in node.targets) and isinstance(node.value, ast.Constant)), None); sys.exit(1) if version is None else print(version)"`) do set "APP_VERSION=%%I"

if not defined APP_VERSION (
    echo [ERROR] Could not read __version__ from speech_widget.py
    goto :fail
)

rem --- Verify that the Vosk model is present ---
if not exist "%MODEL_PATH%" (
    echo [ERROR] Vosk model directory "%MODEL_PATH%" was not found.
    goto :fail
)

rem --- Clean previous standalone build (if any) ---
if exist "%OUTPUT_DIR_STANDALONE%" (
    echo Removing previous build directory "%OUTPUT_DIR_STANDALONE%"...
    rd /s /q "%OUTPUT_DIR_STANDALONE%"
)

rem --- Build standalone directory with Nuitka ---
echo Step 1/2: running Nuitka...
call "%PYTHON%" -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --enable-plugin=pyside6 ^
    --msvc=latest ^
    --include-data-dir=%MODEL_PATH%=%MODEL_PATH% ^
    --include-data-dir=assets=assets ^
    --output-dir=%OUTPUT_DIR_STANDALONE% ^
    --windows-icon-from-ico=%ICO_PATH% ^
    --product-name="%APP_NAME%" ^
    --file-description="%APP_DESC%" ^
    --company-name="%COMPANY_NAME%" ^
    --file-version=%APP_VERSION% ^
    --output-filename=%APP_EXECUTABLE% ^
    speech_widget.py
if errorlevel 1 (
    echo [ERROR] Nuitka build failed.
    goto :fail
)

set "DIST_DIR=%OUTPUT_DIR_STANDALONE%\%STANDALONE_NAME%.dist"
if not exist "%DIST_DIR%\%APP_EXECUTABLE%" (
    echo [ERROR] Expected executable "%DIST_DIR%\%APP_EXECUTABLE%" was not produced.
    goto :fail
)

if not exist "%INSTALLER_OUTPUT_DIR%" (
    mkdir "%INSTALLER_OUTPUT_DIR%"
)

set "PROJECT_DIR=%CD%"
set "DIST_DIR_FULL=%PROJECT_DIR%\%DIST_DIR%"
set "ICON_FULL=%PROJECT_DIR%\%ICO_PATH%"
set "OUTPUT_DIR_FULL=%PROJECT_DIR%\%INSTALLER_OUTPUT_DIR%"
set "INNO_SCRIPT_FULL=%PROJECT_DIR%\%INNO_SCRIPT%"

rem --- Locate Inno Setup compiler (ISCC.exe) ---
if defined ISCC_PATH (
    if not exist "%ISCC_PATH%" (
        echo [ERROR] ISCC_PATH is set but "%ISCC_PATH%" does not exist.
        goto :fail
    )
) else (
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
        set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    ) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
        set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    ) else (
        echo [ERROR] Inno Setup compiler was not found. Install Inno Setup 6 or set ISCC_PATH.
        goto :fail
    )
)

rem --- Run Inno Setup compiler ---
echo Step 2/2: running Inno Setup...
call "%ISCC_PATH%" ^
    "/DMyAppName=%APP_NAME%" ^
    "/DMyAppVersion=%APP_VERSION%" ^
    "/DMyAppPublisher=%COMPANY_NAME%" ^
    "/DMyAppExeName=%APP_EXECUTABLE%" ^
    "/DMyOutputDir=%OUTPUT_DIR_FULL%" ^
    "/DMyOutputBaseFilename=%INSTALLER_BASENAME%" ^
    "/DMyDistDir=%DIST_DIR_FULL%" ^
    "/DMyIconPath=%ICON_FULL%" ^
    "%INNO_SCRIPT_FULL%"

if errorlevel 1 (
    echo [ERROR] Inno Setup reported an error while creating the installer.
    goto :fail
)

echo Installer created: %OUTPUT_DIR_FULL%\%INSTALLER_BASENAME%.exe
goto :success

:fail
echo.
echo Build aborted due to errors. See messages above.
pause
endlocal
exit /b 1

:success
pause
endlocal
exit /b 0
