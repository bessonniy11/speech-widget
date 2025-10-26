; -----------------------------------------------------------------
;  Инсталлятор Speech Widget (Inno Setup)
;  Этот файл параметризуется из build_installer.bat через ключи /D.
;  При ручном запуске значения ниже используются как разумные дефолты.
; -----------------------------------------------------------------

#ifndef MyAppName
#define MyAppName "Speech Widget"
#endif

#ifndef MyAppVersion
#define MyAppVersion "1.0.1"
#endif

#ifndef MyAppPublisher
#define MyAppPublisher "Bessonniy"
#endif

#ifndef MyAppExeName
#define MyAppExeName "SpeechWidget.exe"
#endif

#ifndef MyOutputDir
#define MyOutputDir "..\dist_installer"
#endif

#ifndef MyOutputBaseFilename
#define MyOutputBaseFilename "SpeechWidgetInstaller"
#endif

#ifndef MyDistDir
#define MyDistDir "..\nuitka_dist_installer\SpeechWidget.dist"
#endif

#ifndef MyIconPath
#define MyIconPath "..\assets\icon.ico"
#endif

#define MyAppId "{{BC6F709F-EA74-4819-97A5-4BCDA0D2F6D0}}"

[Setup]
AppId={#MyAppId}                           ; Одинаковый GUID гарантирует обновление поверх существующей версии
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppMutex={#MyAppId}                        ; Блокировка повторного запуска установщика
DefaultDirName={autopf}\{#MyAppName}       ; Program Files (по архитектуре системы)
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes                ; Не спрашиваем про ярлык в «Пуск»
LicenseFile={#SourcePath}\..\LICENSE
OutputDir={#MyOutputDir}                   ; Куда сохраняется готовый .exe
OutputBaseFilename={#MyOutputBaseFilename}
SetupIconFile={#MyIconPath}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest                  ; Достаточно обычных прав пользователя
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64        ; На x64 система ставим в Program Files, а не Program Files (x86)

[Languages]
; Две локализации мастера установки: русская и английская
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Дополнительная опция — создать ярлык на рабочем столе (по умолчанию выключена)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Копируем всю директорию, подготовленную Nuitka, в установленное приложение
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Ярлык в меню «Пуск»
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Ярлык на рабочем столе создаётся только если пользователь выбрал соответствующую задачу
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; После завершения установки предлагаем сразу запустить приложение
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
