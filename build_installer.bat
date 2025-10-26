@echo off
setlocal

chcp 65001 >nul

rem ============================================================
rem  СЦЕНАРИЙ: build_installer.bat
rem  Назначение: собрать установщик Speech Widget.
rem  Этапы: 1) Nuitka строит standalone-директорию,
rem         2) Inno Setup упаковывает её в .exe-инсталлятор.
rem ============================================================

rem --- Базовые метаданные приложения и пути ---
set "APP_NAME=Speech Widget"
set "APP_DESC=Speech recognition widget"
set "COMPANY_NAME=Bessonniy"
set "ICO_PATH=assets\icon.ico"
set "VOSK_MODEL_PATH=model"
set "OUTPUT_DIR_STANDALONE=nuitka_dist_installer"
set "STANDALONE_NAME=speech_widget"
set "APP_EXECUTABLE=SpeechWidget.exe"
set "INSTALLER_OUTPUT_DIR=dist_installer"
set "INSTALLER_BASENAME=SpeechWidgetInstaller"
set "INNO_SCRIPT=installer\speech_widget.iss"
set "PYTHON=python"

set "PYTHONDONTWRITEBYTECODE=1"
set "BUILD_FAILED="

rem --- Вычитываем актуальную версию приложения напрямую из исходника, без импорта зависимостей ---
for /f "usebackq delims=" %%I in (`%PYTHON% -c "import ast,pathlib,sys; module=ast.parse(pathlib.Path('speech_widget.py').read_text(encoding='utf-8')); version=next((node.value.value for node in module.body if isinstance(node, ast.Assign) and any(getattr(t,'id',None)=='__version__' for t in node.targets) and isinstance(node.value, ast.Constant)), None); sys.exit(1) if version is None else print(version)"`) do set "APP_VERSION=%%I"

if not defined APP_VERSION (
    echo [ERROR] Не удалось прочитать __version__ из speech_widget.py
    set "BUILD_FAILED=1"
    goto :finish
)

rem --- Проверяем наличие модели Vosk, без неё приложение не заработает ---
if not exist "%VOSK_MODEL_PATH%" (
    echo [ERROR] Не найдена папка с моделью Vosk: "%VOSK_MODEL_PATH%".
    echo         Скачайте и распакуйте модель, затем повторите сборку.
    set "BUILD_FAILED=1"
    goto :finish
)

rem --- Удаляем предыдущую standalone-сборку, чтобы не мешала свежему результату ---
if exist "%OUTPUT_DIR_STANDALONE%" (
    echo Удаляем старую папку: %OUTPUT_DIR_STANDALONE%...
    rd /s /q "%OUTPUT_DIR_STANDALONE%"
)

echo Шаг 1/2: создаём standalone-директорию через Nuitka...

call "%PYTHON%" -m nuitka --standalone --windows-disable-console --enable-plugin=pyside6 ^
    --include-data-dir=%VOSK_MODEL_PATH%=%VOSK_MODEL_PATH% --include-data-dir=assets=assets ^
    --output-dir="%OUTPUT_DIR_STANDALONE%" --windows-icon-from-ico="%ICO_PATH%" ^
    --product-name="%APP_NAME%" --file-description="%APP_DESC%" --company-name="%COMPANY_NAME%" ^
    --file-version="%APP_VERSION%" --output-filename="%APP_EXECUTABLE%" speech_widget.py

if errorlevel 1 (
    echo [ERROR] Nuitka не смогла собрать standalone-директорию.
    set "BUILD_FAILED=1"
    goto :finish
)

rem Папка вида SpeechWidget.dist поступит на вход Inno Setup
set "DIST_DIR=%OUTPUT_DIR_STANDALONE%\%STANDALONE_NAME%.dist"

if not exist "%DIST_DIR%\%APP_EXECUTABLE%" (
    echo [ERROR] Ожидаемый exe не найден в "%DIST_DIR%".
    set "BUILD_FAILED=1"
    goto :finish
)

rem Создаём выходную директорию для конечного установщика при необходимости
if not exist "%INSTALLER_OUTPUT_DIR%" (
    mkdir "%INSTALLER_OUTPUT_DIR%"
)

rem --- Приводим пути к абсолютному виду для передачи Inno Setup ---
set "PROJECT_DIR=%CD%"
set "DIST_DIR_FULL=%PROJECT_DIR%\%DIST_DIR%"
set "ICON_FULL=%PROJECT_DIR%\%ICO_PATH%"
set "OUTPUT_DIR_FULL=%PROJECT_DIR%\%INSTALLER_OUTPUT_DIR%"
set "INNO_SCRIPT_FULL=%PROJECT_DIR%\%INNO_SCRIPT%"

rem --- Определяем путь к компилятору Inno Setup (ISCC.exe) ---
if defined ISCC_PATH (
    if not exist "%ISCC_PATH%" (
        echo [ERROR] Переменная ISCC_PATH задана, но файл "%ISCC_PATH%" не найден.
        set "BUILD_FAILED=1"
        goto :finish
    )
) else (
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
        set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    ) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
        set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    ) else (
        echo [ERROR] Компилятор Inno Setup (ISCC.exe) не найден.
        echo         Установите Inno Setup 6 или задайте путь через переменную ISCC_PATH.
        set "BUILD_FAILED=1"
        goto :finish
    )
)

echo Шаг 2/2: запускаем Inno Setup — используем %ISCC_PATH%

"%ISCC_PATH%" ^
    "/DMyAppName=%APP_NAME%" ^
    "/DMyAppVersion=%APP_VERSION%" ^
    "/DMyAppPublisher=%COMPANY_NAME%" ^
    "/DMyAppExeName=%APP_EXECUTABLE%" ^
    "/DMyOutputDir=%OUTPUT_DIR_FULL%" ^
    "/DMyOutputBaseFilename=%INSTALLER_BASENAME%" ^
    "/DMyDistDir=%DIST_DIR_FULL%" ^
    "/DMyIconPath=%ICON_FULL%" ^
    "%INNO_SCRIPT_FULL%"

rem Пояснения:
rem   /DMyAppName и т.п. — переменные, которые затем используются внутри файла speech_widget.iss.
rem   /DMyDistDir         — путь к директории, собранной Nuitka.
rem   /DMyOutputDir       — куда поместить итоговый установщик.
rem   /DMyAppExeName      — главный исполняемый файл, который будет запускаться после установки.

if errorlevel 1 (
    echo [ERROR] Inno Setup завершился с ошибкой.
    set "BUILD_FAILED=1"
    goto :finish
)

echo Установщик успешно создан: %OUTPUT_DIR_FULL%\%INSTALLER_BASENAME%.exe

:finish
if defined BUILD_FAILED (
    echo.
    echo Работа прервана из-за ошибок, см. сообщения выше.
    pause
    endlocal
    exit /b 1
) else (
    pause
    endlocal
    exit /b 0
)
