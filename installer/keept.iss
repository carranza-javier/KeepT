; Inno Setup script for KeepT (per user install, no administrator rights needed).
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer\keept.iss

#define AppName "KeepT"
; The release workflow passes the version of the tag: ISCC /DAppVersion=X.Y.Z
#ifndef AppVersion
  #define AppVersion "0.9.0"
#endif
#define AppExe "KeepT.exe"

[Setup]
AppId={{6F2B7C1E-4B1A-4E8B-9C55-6B1E2A0D7A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=KeepT
AppPublisherURL=https://github.com/carranza-javier/KeepT
AppSupportURL=https://github.com/carranza-javier/KeepT/issues
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoDescription=KeepT screen translator installer
; Privacy notice shown before installing (what KeepT sends over the network and how to turn it off)
InfoBeforeFile=..\packaging\privacy.txt
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
en.Updates=Check for new KeepT versions on GitHub (once a day)
de.Updates=Einmal täglich auf GitHub nach neuen KeepT-Versionen suchen
es.Updates=Buscar nuevas versiones de KeepT en GitHub (una vez al día)

[Tasks]
Name: "autostart"; Description: "{cm:Autostart}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked
Name: "updates"; Description: "{cm:Updates}"

[Files]
Source: "..\dist\KeepT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "KeepT"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; \
    ValueData: """{app}\{#AppExe}"" --autostart"; Flags: uninsdeletevalue; Tasks: autostart

; The app reads this on its first start (afterwards the tray menu setting is used).
Root: HKCU; Subkey: "Software\KeepT"; ValueType: dword; ValueName: "CheckUpdates"; ValueData: 1; Flags: uninsdeletekey; Tasks: updates
Root: HKCU; Subkey: "Software\KeepT"; ValueType: dword; ValueName: "CheckUpdates"; ValueData: 0; Flags: uninsdeletekey; Tasks: not updates

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
