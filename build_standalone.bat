@echo off
rem Определяем переменные с кавычками, если есть пробелы
set APP_NAME="Speech Widget"
set APP_DESC="Speech recognition widget"
set COMPANY_NAME="Bessonniy"
set APP_VERSION=1.0
set ICO_PATH="assets\icon.ico"
set VOSK_MODEL_PATH=model
set OUTPUT_DIR_STANDALONE=speech_widget_dist

echo Building standalone version (folder)...

rem Используем переменные БЕЗ лишних кавычек в опциях Nuitka
python -m nuitka ^
    --standalone ^
    --enable-plugin=pyside6 ^
    --windows-disable-console ^
    --include-data-dir=%VOSK_MODEL_PATH%=%VOSK_MODEL_PATH% ^
    --include-data-dir=assets=assets ^
    --output-dir=%OUTPUT_DIR_STANDALONE% ^
    --windows-icon-from-ico=%ICO_PATH% ^
    --product-name=%APP_NAME% ^
    --file-description=%APP_DESC% ^
    --company-name=%COMPANY_NAME% ^
    --file-version=%APP_VERSION% ^
    --output-filename=%APP_NAME%.exe ^
    speech_widget.py

echo Build finished. Result in %OUTPUT_DIR_STANDALONE%\%APP_NAME%.dist
pause