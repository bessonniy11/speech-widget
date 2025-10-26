# Speech Widget

Небольшой голосовой виджет для Windows, который позволяет диктовать текст в любое приложение, перехватывать глобальные сочетания клавиш, управлять буфером обмена и выводить компактный интерфейс поверх всех окон. Проект написан на Python и использует PySide6, Vosk и другие локальные библиотеки, поэтому работает полностью офлайн.

## Возможности
- Распознавание речи офлайн (модель Vosk).
- Плавающая панель с индикатором активности микрофона.
- Глобальное сочетание клавиш (по умолчанию `Ctrl+Space`) для быстрого запуска диктовки.
- Управление буфером обмена и автоматическое вставление распознанного текста.
- Автозапуск, логирование и управление через иконку в системном трее.

## Требования
1. **Python 3.9+**, установленный и доступный в `PATH`.
2. **Микрофон** с разрешением на использование в Windows.
3. **Модель Vosk** — по умолчанию ожидается `vosk-model-small-ru-0.22`, распакованная в каталог `model`.
4. Для сборки исполняемых файлов:
   - `nuitka`, `numpy`, Microsoft Visual C++ Build Tools (доступны через Visual Studio или Build Tools).
   - Inno Setup 6 (компилятор `ISCC.exe`).

## Установка зависимостей
```powershell
python -m pip install --upgrade pip
pip install numpy vosk sounddevice pynput pyperclip Pillow PySide6 pywin32 nuitka
```

Модель Vosk скачивается отдельно: [https://alphacephei.com/vosk/models](https://alphacephei.com/vosk/models). Распакуйте архив в папку `model`, которая лежит рядом со `speech_widget.py`.

## Запуск из исходников
```powershell
python speech_widget.py
```

Логи пишутся в `%TEMP%\speech_widget_log.txt`. При первом запуске приложение может запросить разрешение на использование микрофона.

## Сборка переносимого `.exe`
1. Убедитесь, что установлен компилятор MSVC (запустите «Developer Command Prompt for VS» либо выполните `vcvarsall.bat`).
2. Выполните:
   ```powershell
   .\build_onefile.bat
   ```
3. Готовый файл `Speech Widget.exe` появится в папке `nuitka_dist_onefile`.

## Сборка установщика
Скрипт `build_installer.bat` выполняет оба шага: собирает standalone-директорию через Nuitka и упаковку Inno Setup. Запускайте его из «x64 Native Tools Command Prompt for VS» (или другой консоли, где доступен `cl.exe`).

```powershell
.\build_installer.bat
```

Если всё прошло успешно, установщик будет лежать в `dist_installer\SpeechWidgetInstaller.exe`.

### Ручная сборка (при необходимости)
Если требуется выполнить шаги вручную:
1. Nuitka:
   ```powershell
   python -m nuitka --standalone --windows-console-mode=disable --enable-plugin=pyside6 --msvc=latest `
       --include-data-dir=model=model --include-data-dir=assets=assets `
       --output-dir=nuitka_dist_installer --windows-icon-from-ico=assets\icon.ico `
       --product-name="Speech Widget" --file-description="Speech recognition widget" `
       --company-name=Bessonniy --file-version=1.0.2 `
       --output-filename=SpeechWidget.exe speech_widget.py
   ```
2. Inno Setup:
   ```powershell
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" `
       "/DMyAppName=Speech Widget" `
       "/DMyAppVersion=1.0.2" `
       "/DMyAppPublisher=Bessonniy" `
       "/DMyAppExeName=SpeechWidget.exe" `
       "/DMyOutputDir=D:\areact\speech-widget\dist_installer" `
       "/DMyOutputBaseFilename=SpeechWidgetInstaller" `
       "/DMyDistDir=D:\areact\speech-widget\nuitka_dist_installer\speech_widget.dist" `
       "/DMyIconPath=D:\areact\speech-widget\assets\icon.ico" `
       "D:\areact\speech-widget\installer\speech_widget.iss"
   ```

## Структура репозитория
```
assets/                 — иконки и дополнительные ресурсы
docs/                   — спецификация, план, задачи
installer/speech_widget.iss — шаблон установщика Inno Setup
model/                  — модель Vosk (не версионируется)
nuitka_dist_onefile/    — результат onefile-сборки (игнорируется git)
nuitka_dist_installer/  — standalone-вывод Nuitka для установщика (игнорируется git)
dist_installer/         — готовые установщики (игнорируются git)
speech_widget.py        — основной код приложения
build_onefile.bat       — сборка переносимого .exe
build_installer.bat     — сборка установщика
```

## Отладка и поддержка
- Логи: `%TEMP%\speech_widget_log.txt`.
- Если приложение не появляется в трее, проверьте наличие `SpeechWidget.exe` в Диспетчере задач и откройте лог.
- Для сброса положения окна удалите ключ `HKEY_CURRENT_USER\Software\MyCompany\SpeechWidget`.

## Лицензия
Подробнее в файле `LICENSE`.
