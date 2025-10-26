@echo off
setlocal

chcp 65001 >nul

rem ============================================================
rem  СЦЕНАРИЙ: build_onefile.bat
rem  Назначение: собрать переносимый .exe-файл Speech Widget
rem  с помощью Nuitka в режиме --onefile.
rem ============================================================

rem --- Основные метаданные приложения (отражаются в ресурсе файла) ---
set "APP_NAME=Speech Widget"
set "APP_DESC=Speech recognition widget"
set "COMPANY_NAME=Bessonniy"
set "ICO_PATH=assets\icon.ico"
set "VOSK_MODEL_PATH=model"
set "OUTPUT_DIR_ONEFILE=nuitka_dist_onefile"
set "APP_EXECUTABLE=Speech Widget.exe"
set "PYTHON=python"

rem --- Определяем версию приложения, разбирая исходник (без импорта зависимостей) ---
for /f "usebackq delims=" %%I in (`%PYTHON% -c "import ast,pathlib,sys; module=ast.parse(pathlib.Path('speech_widget.py').read_text(encoding='utf-8')); version=next((node.value.value for node in module.body if isinstance(node, ast.Assign) and any(getattr(t,'id',None)=='__version__' for t in node.targets) and isinstance(node.value, ast.Constant)), None); sys.exit(1) if version is None else print(version)"`) do set "APP_VERSION=%%I"

if not defined APP_VERSION (
    rem Если версия не получена, прекращаем работу, чтобы не плодить файлы без метаданных
    echo [ERROR] Не удалось прочитать __version__ из speech_widget.py
    exit /b 1
)

rem --- Очищаем предыдущий результат сборки, чтобы не смешивать версии ---
if exist "%OUTPUT_DIR_ONEFILE%" (
    echo Удаляем старую директорию сборки: %OUTPUT_DIR_ONEFILE%...
    rd /s /q "%OUTPUT_DIR_ONEFILE%"
)

echo Запускаем Nuitka для сборки однофайловой версии...

rem --- Основной вызов Nuitka. Каждая опция вынесена отдельной строкой для наглядности ---
call "%PYTHON%" -m nuitka --onefile --windows-disable-console --enable-plugin=pyside6 ^
    --include-data-dir=%VOSK_MODEL_PATH%=%VOSK_MODEL_PATH% --include-data-dir=assets=assets ^
    --output-dir="%OUTPUT_DIR_ONEFILE%" --windows-icon-from-ico="%ICO_PATH%" ^
    --product-name="%APP_NAME%" --file-description="%APP_DESC%" --company-name="%COMPANY_NAME%" ^
    --file-version="%APP_VERSION%" --output-filename="%APP_EXECUTABLE%" speech_widget.py

rem Пояснения к ключевым опциям:
rem   --onefile                — сборка в один exe без внешних директорий.
rem   --windows-disable-console — отключаем консольное окно, чтобы приложение стартовало тихо.
rem   --enable-plugin=pyside6   — плагин подтягивает нужные DLL Qt.
rem   --include-data-dir        — упаковываем модель Vosk и папку assets в итоговый файл.
rem   --product/file/company    — метаданные, отображаемые в свойствах файла.
rem   --file-version            — окно «Свойства → Подробно» показывает реальную версию приложения.
rem   --output-filename         — явное имя результата вместо стандартного имени Nuitka.

if errorlevel 1 (
    rem Любая ошибка Nuitka делает сборку невалидной, поэтому завершаем с кодом 1
    echo [ERROR] Сборка Nuitka завершилась неуспешно.
    exit /b 1
)

echo Готово. Найти результат можно в %OUTPUT_DIR_ONEFILE%\%APP_EXECUTABLE%
pause
endlocal
