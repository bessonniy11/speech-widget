# Speech Widget

Простой виджет для распознавания речи с помощью Vosk и вставки текста.

## Зависимости

Установка необходимых библиотек:
```bash
pip install vosk sounddevice pynput pyperclip numpy PySide6
```

## Подготовка

*   Убедитесь, что папка `model` с распакованной моделью Vosk находится в корне проекта.
*   Поместите иконку приложения в формате `.ico` (например, `icon.ico`) в папку `assets`. SVG-иконку (`icon.svg`) можно использовать для трея, но для `.exe` нужен `.ico`. Для конвертации можно использовать онлайн-сервисы или графические редакторы.

## Запуск для разработки

Запускать из терминала, открытого **от имени администратора** (для перехвата клавиш и вставки):
```bash
python speech_widget.py
```

## Сборка .exe с помощью Nuitka

**Необходимо:**
*   Установленный Nuitka (`pip install nuitka`)
*   Установленный компилятор C++ (например, из Visual Studio Community с компонентом "Разработка классических приложений на C++")

**Переменные для команд сборки (замените на свои):**
```bash
# Имя вашего приложения
APP_NAME="Voice Input Widget"
# Описание
APP_DESC="Speech recognition widget"
# Компания
COMPANY_NAME="MyCompany"
# Путь к иконке .ico
ICO_PATH="assets/icon.ico"
# Папка с моделью Vosk
VOSK_MODEL_PATH="model"
# Имя папки для standalone сборки
OUTPUT_DIR_STANDALONE="nuitka_dist"
# Имя папки для onefile сборки
OUTPUT_DIR_ONEFILE="nuitka_dist_onefile"
```

**1. Сборка в самодостаточную папку:**

Результат будет в папке `$OUTPUT_DIR_STANDALONE\$APP_NAME.dist`. Для распространения нужно архивировать всю папку `$APP_NAME.dist`.
```bash
python -m nuitka --standalone --windows-disable-console --enable-plugin=pyside6 --enable-plugin=numpy --include-data-dir=%VOSK_MODEL_PATH%=%VOSK_MODEL_PATH% --output-dir=%OUTPUT_DIR_STANDALONE% --windows-icon-from-ico=%ICO_PATH% --product-name="%APP_NAME%" --file-description="%APP_DESC%" --company-name="%COMPANY_NAME%" --output-filename="%APP_NAME%.exe" speech_widget.py
```
*(Примечание: `%VAR%` используется для переменных окружения в Windows CMD. В PowerShell используйте `$env:VAR` или просто подставьте значения вручную.)*

**2. Сборка в один .exe файл (альтернатива):**

Результат будет в папке `$OUTPUT_DIR_ONEFILE` в виде одного файла `$APP_NAME.exe`. Может дольше запускаться и быть менее стабильным.
```bash
python -m nuitka --onefile --windows-disable-console --enable-plugin=pyside6 --enable-plugin=numpy --include-data-dir=%VOSK_MODEL_PATH%=%VOSK_MODEL_PATH% --output-dir=%OUTPUT_DIR_ONEFILE% --windows-icon-from-ico=%ICO_PATH% --product-name="%APP_NAME%" --file-description="%APP_DESC%" --company-name="%COMPANY_NAME%" --output-filename="%APP_NAME%.exe" speech_widget.py
```
