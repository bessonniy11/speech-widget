; -----------------------------------------------------------------
;  Speech Widget installer template for Inno Setup 6
;  Values may be overridden via /D switches (see build_installer.bat).
; -----------------------------------------------------------------

#ifndef MyAppName
#define MyAppName "Speech Widget"
#endif

#ifndef MyAppVersion
#define MyAppVersion "1.0.2"
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
#define MyDistDir "..\nuitka_dist_installer\speech_widget.dist"
#endif

#ifndef MyIconPath
#define MyIconPath "..\assets\icon.ico"
#endif

#define MyAppId "{{BC6F709F-EA74-4819-97A5-4BCDA0D2F6D0}}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppMutex={#MyAppId}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile={#SourcePath}\..\LICENSE
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBaseFilename}
SetupIconFile={#MyIconPath}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
