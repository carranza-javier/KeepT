; Inno Setup script for KeepT (per user install, no administrator rights needed).
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer\keept.iss

#define AppName "KeepT"
#define AppVersion "1.0.0"
#define AppExe "KeepT.exe"

[Setup]
AppId={{6F2B7C1E-4B1A-4E8B-9C55-6B1E2A0D7A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=KeepT
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=KeepT-Setup-{#AppVersion}
SetupIconFile=..\packaging\keept.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
en.Autostart=Start KeepT with Windows
de.Autostart=KeepT mit Windows starten
es.Autostart=Iniciar KeepT con Windows

[Tasks]
Name: "autostart"; Description: "{cm:Autostart}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\dist\KeepT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; \
    ValueData: """{app}\{#AppExe}"" --autostart"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "StopKeepT"
; The tray toggle may have created the autostart entry even if the installer task was off.
Filename: "{sys}\reg.exe"; Parameters: "delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v {#AppName} /f"; Flags: runhidden; RunOnceId: "RemoveAutostart"

[UninstallDelete]
; Downloaded models, log and settings
Type: filesandordirs; Name: "{localappdata}\KeepT"
Type: filesandordirs; Name: "{userappdata}\KeepT"
