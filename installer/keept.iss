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
AppPublisher=KettenKI (Javier Carranza)
AppPublisherURL=https://kettenki.com
AppCopyright=© 2026 Javier Carranza
AppSupportURL=https://github.com/carranza-javier/KeepT/issues
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoDescription=KeepT screen translator installer
VersionInfoCompany=KettenKI
VersionInfoCopyright=© 2026 Javier Carranza
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
; The installer starts in the Windows display language, or in English when it is none of the eight.
LanguageDetectionMethod=uilanguage

; Each language shows the privacy notice (what KeepT sends over the network and how to turn it
; off) before installing.
[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "..\packaging\privacy\privacy-en.txt"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"; InfoBeforeFile: "..\packaging\privacy\privacy-de.txt"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"; InfoBeforeFile: "..\packaging\privacy\privacy-es.txt"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"; InfoBeforeFile: "..\packaging\privacy\privacy-fr.txt"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"; InfoBeforeFile: "..\packaging\privacy\privacy-it.txt"
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"; InfoBeforeFile: "..\packaging\privacy\privacy-pt.txt"
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"; InfoBeforeFile: "..\packaging\privacy\privacy-nl.txt"
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"; InfoBeforeFile: "..\packaging\privacy\privacy-pl.txt"

[CustomMessages]
en.Autostart=Start KeepT with Windows
de.Autostart=KeepT mit Windows starten
es.Autostart=Iniciar KeepT con Windows
fr.Autostart=Démarrer KeepT avec Windows
it.Autostart=Avvia KeepT con Windows
pt.Autostart=Iniciar o KeepT com o Windows
nl.Autostart=KeepT starten met Windows
pl.Autostart=Uruchamiaj KeepT razem z systemem Windows
en.Updates=Check for new KeepT versions on GitHub (once a day)
de.Updates=Einmal täglich auf GitHub nach neuen KeepT-Versionen suchen
es.Updates=Buscar nuevas versiones de KeepT en GitHub (una vez al día)
fr.Updates=Rechercher les nouvelles versions de KeepT sur GitHub (une fois par jour)
it.Updates=Cerca nuove versioni di KeepT su GitHub (una volta al giorno)
pt.Updates=Procurar novas versões do KeepT no GitHub (uma vez por dia)
nl.Updates=Op GitHub controleren op nieuwe KeepT-versies (één keer per dag)
pl.Updates=Sprawdzaj nowe wersje KeepT na GitHubie (raz dziennie)

en.LanguagesTitle=Languages
de.LanguagesTitle=Sprachen
es.LanguagesTitle=Idiomas
fr.LanguagesTitle=Langues
it.LanguagesTitle=Lingue
pt.LanguagesTitle=Idiomas
nl.LanguagesTitle=Talen
pl.LanguagesTitle=Języki
en.LanguagesDescription=Choose the languages KeepT translates, so the first translation is instant.
de.LanguagesDescription=Wähle die Sprachen, die KeepT übersetzt, damit schon die erste Übersetzung sofort erscheint.
es.LanguagesDescription=Elige los idiomas que traducirá KeepT, para que la primera traducción sea instantánea.
fr.LanguagesDescription=Choisissez les langues que KeepT traduit, pour que la première traduction soit instantanée.
it.LanguagesDescription=Scegli le lingue che KeepT traduce, così anche la prima traduzione è immediata.
pt.LanguagesDescription=Escolha os idiomas que o KeepT traduz, para que a primeira tradução seja imediata.
nl.LanguagesDescription=Kies de talen die KeepT vertaalt, zodat ook de eerste vertaling direct verschijnt.
pl.LanguagesDescription=Wybierz języki, które tłumaczy KeepT, aby już pierwsze tłumaczenie było natychmiastowe.
en.TranslateInto=Translate into:
de.TranslateInto=Übersetzen in:
es.TranslateInto=Traducir a:
fr.TranslateInto=Traduire en :
it.TranslateInto=Traduci in:
pt.TranslateInto=Traduzir para:
nl.TranslateInto=Vertalen naar:
pl.TranslateInto=Tłumacz na:
en.TranslateFrom=Translate from:
de.TranslateFrom=Übersetzen aus:
es.TranslateFrom=Traducir desde:
fr.TranslateFrom=Traduire depuis :
it.TranslateFrom=Traduci da:
pt.TranslateFrom=Traduzir de:
nl.TranslateFrom=Vertalen uit:
pl.TranslateFrom=Tłumacz z:
en.DownloadSize=Download during installation: about %1 MB (only this once).
de.DownloadSize=Download während der Installation: etwa %1 MB (nur dieses eine Mal).
es.DownloadSize=Descarga durante la instalación: unos %1 MB (solo esta vez).
fr.DownloadSize=Téléchargement pendant l'installation : environ %1 Mo (une seule fois).
it.DownloadSize=Download durante l'installazione: circa %1 MB (solo questa volta).
pt.DownloadSize=Transferência durante a instalação: cerca de %1 MB (só desta vez).
nl.DownloadSize=Download tijdens de installatie: ongeveer %1 MB (alleen deze keer).
pl.DownloadSize=Pobieranie podczas instalacji: około %1 MB (tylko ten jeden raz).
en.DownloadNone=Nothing to download: these languages are ready.
de.DownloadNone=Nichts herunterzuladen: diese Sprachen sind bereit.
es.DownloadNone=No hay nada que descargar: estos idiomas ya están listos.
fr.DownloadNone=Rien à télécharger : ces langues sont prêtes.
it.DownloadNone=Niente da scaricare: queste lingue sono pronte.
pt.DownloadNone=Nada para transferir: estes idiomas já estão prontos.
nl.DownloadNone=Niets te downloaden: deze talen zijn klaar.
pl.DownloadNone=Nie ma nic do pobrania: te języki są gotowe.
en.DownloadingLanguages=Downloading languages (only this once)
de.DownloadingLanguages=Sprachen werden heruntergeladen (nur dieses eine Mal)
es.DownloadingLanguages=Descargando idiomas (solo esta vez)
fr.DownloadingLanguages=Téléchargement des langues (une seule fois)
it.DownloadingLanguages=Download delle lingue (solo questa volta)
pt.DownloadingLanguages=A transferir idiomas (só desta vez)
nl.DownloadingLanguages=Talen downloaden (alleen deze keer)
pl.DownloadingLanguages=Pobieranie języków (tylko ten jeden raz)
en.DownloadingLanguagesHint=Without internet the installation finishes anyway, and KeepT downloads them later.
de.DownloadingLanguagesHint=Ohne Internet wird die Installation trotzdem abgeschlossen, und KeepT lädt sie später herunter.
es.DownloadingLanguagesHint=Sin internet la instalación termina igual y KeepT los descargará después.
fr.DownloadingLanguagesHint=Sans Internet, l'installation se termine quand même et KeepT les téléchargera plus tard.
it.DownloadingLanguagesHint=Senza Internet l'installazione termina comunque e KeepT le scaricherà più tardi.
pt.DownloadingLanguagesHint=Sem Internet a instalação termina na mesma e o KeepT transfere-os mais tarde.
nl.DownloadingLanguagesHint=Zonder internet wordt de installatie toch voltooid en downloadt KeepT ze later.
pl.DownloadingLanguagesHint=Bez internetu instalacja i tak się zakończy, a KeepT pobierze je później.
en.InstallingLanguages=Installing languages...
de.InstallingLanguages=Sprachen werden installiert...
es.InstallingLanguages=Instalando idiomas...
fr.InstallingLanguages=Installation des langues...
it.InstallingLanguages=Installazione delle lingue...
pt.InstallingLanguages=A instalar idiomas...
nl.InstallingLanguages=Talen installeren...
pl.InstallingLanguages=Instalowanie języków...

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

[Code]
#include "models.iss"

// Languages page: "Translate into" and the languages to translate from. The models they need are
// downloaded from the models-v1 release (verified with SHA-256) before installing, and unpacked by
// KeepT.exe --install-model afterwards, which checks them again against the manifest of the app.
var
  LangPage: TWizardPage;
  TargetCombo: TNewComboBox;
  SourceList: TNewCheckListBox;
  SizeLabel: TNewStaticText;
  DownloadPage: TDownloadWizardPage;
  Downloaded: String;

function WindowsLang: String;
begin
  case GetUILanguage and $3FF of
    $07: Result := 'de';
    $09: Result := 'en';
    $0A: Result := 'es';
    $0C: Result := 'fr';
    $10: Result := 'it';
    $16: Result := 'pt';
    $13: Result := 'nl';
    $15: Result := 'pl';
  else
    Result := 'en';
  end;
end;

function LangIndex(const Code: String): Integer;
var
  I: Integer;
begin
  Result := -1;
  for I := 0 to GetArrayLength(LangCodes) - 1 do
    if LangCodes[I] = Code then
      Result := I;
end;

function PairIndex(const Code: String): Integer;
var
  I: Integer;
begin
  Result := -1;
  for I := 0 to GetArrayLength(PairCodes) - 1 do
    if PairCodes[I] = Code then
      Result := I;
end;

function InList(const Code, List: String): Boolean;
begin
  Result := Pos(',' + Code + ',', ',' + List + ',') > 0;
end;

// Takes the first item of a comma separated list and removes it from the list.
function PopItem(var List: String): String;
var
  P: Integer;
begin
  P := Pos(',', List);
  if P = 0 then
  begin
    Result := List;
    List := '';
  end
  else
  begin
    Result := Copy(List, 1, P - 1);
    Delete(List, 1, P);
  end;
end;

function ModelInstalled(const Code: String): Boolean;
var
  Dir: String;
begin
  Dir := Code;
  StringChangeEx(Dir, '-', '_', True);
  Result := FileExists(ExpandConstant('{localappdata}\KeepT\models\') + Dir + '\keept.json');
end;

function SelectedTarget: String;
begin
  Result := LangCodes[TargetCombo.ItemIndex];
end;

function SelectedSources: String;
var
  I: Integer;
begin
  Result := '';
  for I := 0 to GetArrayLength(LangCodes) - 1 do
    if SourceList.Checked[I] then
    begin
      if Result <> '' then
        Result := Result + ',';
      Result := Result + LangCodes[I];
    end;
end;

// Packages still missing for the current choice, comma separated.
function NeededPairs: String;
var
  I: Integer;
  Chain, Code: String;
begin
  Result := '';
  for I := 0 to GetArrayLength(LangCodes) - 1 do
    if SourceList.Checked[I] and (LangCodes[I] <> SelectedTarget) then
    begin
      Chain := KeepTRoute(LangCodes[I], SelectedTarget);
      while Chain <> '' do
      begin
        Code := PopItem(Chain);
        if (Code <> '') and not InList(Code, Result) and not ModelInstalled(Code) then
        begin
          if Result <> '' then
            Result := Result + ',';
          Result := Result + Code;
        end;
      end;
    end;
end;

procedure UpdateSize(Sender: TObject);
var
  Pairs: String;
  Total: Int64;
begin
  Pairs := NeededPairs;
  Total := 0;
  while Pairs <> '' do
    Total := Total + PairSizes[PairIndex(PopItem(Pairs))];
  if Total = 0 then
    SizeLabel.Caption := CustomMessage('DownloadNone')
  else
    SizeLabel.Caption := FmtMessage(CustomMessage('DownloadSize'), [IntToStr((Total + 524288) div 1048576)]);
end;

procedure TargetChanged(Sender: TObject);
begin
  SourceList.Checked[TargetCombo.ItemIndex] := True;
  UpdateSize(Sender);
end;

procedure InitializeWizard;
var
  IntoLabel, FromLabel: TNewStaticText;
  I: Integer;
  Target, Sources: String;
begin
  KeepTInitModels;
  LangPage := CreateCustomPage(wpSelectTasks, CustomMessage('LanguagesTitle'), CustomMessage('LanguagesDescription'));

  IntoLabel := TNewStaticText.Create(LangPage);
  IntoLabel.Parent := LangPage.Surface;
  IntoLabel.Caption := CustomMessage('TranslateInto');
  IntoLabel.Top := 0;

  TargetCombo := TNewComboBox.Create(LangPage);
  TargetCombo.Parent := LangPage.Surface;
  TargetCombo.Style := csDropDownList;
  TargetCombo.Top := IntoLabel.Top + IntoLabel.Height + ScaleY(4);
  TargetCombo.Width := ScaleX(220);
  for I := 0 to GetArrayLength(LangNames) - 1 do
    TargetCombo.Items.Add(LangNames[I]);

  FromLabel := TNewStaticText.Create(LangPage);
  FromLabel.Parent := LangPage.Surface;
  FromLabel.Caption := CustomMessage('TranslateFrom');
  FromLabel.Top := TargetCombo.Top + TargetCombo.Height + ScaleY(12);

  SizeLabel := TNewStaticText.Create(LangPage);
  SizeLabel.Parent := LangPage.Surface;
  SizeLabel.AutoSize := False;
  SizeLabel.WordWrap := True;
  SizeLabel.Width := LangPage.SurfaceWidth;
  SizeLabel.Height := ScaleY(32);
  SizeLabel.Top := LangPage.SurfaceHeight - SizeLabel.Height;

  SourceList := TNewCheckListBox.Create(LangPage);
  SourceList.Parent := LangPage.Surface;
  SourceList.Top := FromLabel.Top + FromLabel.Height + ScaleY(4);
  SourceList.Width := LangPage.SurfaceWidth;
  SourceList.Height := SizeLabel.Top - SourceList.Top - ScaleY(8);
  for I := 0 to GetArrayLength(LangNames) - 1 do
    SourceList.AddCheckBox(LangNames[I], '', 0, False, True, False, False, nil);

  // Defaults: the previous choice when reinstalling; otherwise the Windows language as target,
  // and the Windows language, English and the target as languages to translate from.
  if not RegQueryStringValue(HKCU, 'Software\KeepT', 'TargetLang', Target) or (LangIndex(Target) < 0) then
    Target := WindowsLang;
  if not RegQueryStringValue(HKCU, 'Software\KeepT', 'SourceLangs', Sources) or (Sources = '') then
    Sources := WindowsLang + ',en,' + Target;
  TargetCombo.ItemIndex := LangIndex(Target);
  for I := 0 to GetArrayLength(LangCodes) - 1 do
    SourceList.Checked[I] := InList(LangCodes[I], Sources) or (LangCodes[I] = Target);

  TargetCombo.OnChange := @TargetChanged;
  SourceList.OnClickCheck := @UpdateSize;
  UpdateSize(nil);

  DownloadPage := CreateDownloadPage(CustomMessage('DownloadingLanguages'), CustomMessage('DownloadingLanguagesHint'), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Pairs, Code: String;
  I: Integer;
begin
  Result := True;
  if (CurPageID <> wpReady) or WizardSilent then
    Exit;
  Downloaded := '';
  Pairs := NeededPairs;
  if Pairs = '' then
    Exit;
  DownloadPage.Show;
  try
    while Pairs <> '' do
    begin
      Code := PopItem(Pairs);
      I := PairIndex(Code);
      DownloadPage.Clear;
      DownloadPage.Add(PairUrls[I], 'keept-' + Code + '.zip', PairShas[I]);
      try
        DownloadPage.Download;  // raises if the download fails or the SHA-256 does not match
        Downloaded := Downloaded + Code + ',';
      except
        // No internet, cancelled, or a damaged file: install anyway, KeepT downloads it later.
        Log('Language package ' + Code + ' not downloaded: ' + GetExceptionMessage);
        Pairs := '';
      end;
    end;
  finally
    DownloadPage.Hide;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Pairs, Code: String;
  ResultCode: Integer;
begin
  if (CurStep <> ssPostInstall) or WizardSilent then
    Exit;
  WizardForm.StatusLabel.Caption := CustomMessage('InstallingLanguages');
  Pairs := Downloaded;
  while Pairs <> '' do
  begin
    Code := PopItem(Pairs);
    if Code <> '' then
      Exec(ExpandConstant('{app}\{#AppExe}'),
           '--install-model "' + ExpandConstant('{tmp}\keept-' + Code + '.zip') + '" ' + Copy(Code, 1, 2) + ' ' + Copy(Code, 4, 2),
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
  // Read once by KeepT on its next start (a new stamp per installation).
  RegWriteStringValue(HKCU, 'Software\KeepT', 'TargetLang', SelectedTarget);
  RegWriteStringValue(HKCU, 'Software\KeepT', 'SourceLangs', SelectedSources);
  RegWriteStringValue(HKCU, 'Software\KeepT', 'LanguagesStamp', GetDateTimeString('yyyymmddhhnnss', #0, #0));
end;
