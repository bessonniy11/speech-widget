@echo off
rem Определяем переменные
set APP_NAME="Speech Widget"
set APP_DESC="Speech recognition widget"
set COMPANY_NAME="Bessonniy"
set APP_VERSION=1.0
set ICO_PATH="assets\icon.ico"
set VOSK_MODEL_PATH=model
set OUTPUT_DIR_ONEFILE=nuitka_dist_onefile

echo Building onefile version (.exe)...

python -m nuitka ^
    --onefile ^
    --windows-disable-console ^
    --enable-plugin=pyside6 ^
    --include-data-dir=%VOSK_MODEL_PATH%=%VOSK_MODEL_PATH% ^
    --include-data-dir=assets=assets ^
    --output-dir=%OUTPUT_DIR_ONEFILE% ^
    --windows-icon-from-ico=%ICO_PATH% ^
    --product-name=%APP_NAME% ^
    --file-description=%APP_DESC% ^
    --company-name=%COMPANY_NAME% ^
    --file-version=%APP_VERSION% ^
    --output-filename=%APP_NAME%.exe ^
    speech_widget.py

echo Build finished. Result in %OUTPUT_DIR_ONEFILE%
pause