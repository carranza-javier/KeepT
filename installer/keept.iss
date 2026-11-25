; Inno Setup script for KeepT (per user install, no administrator rights needed).
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer\keept.iss

#define AppName "KeepT"
; The release workflow passes the version of the tag: ISCC /DAppVersion=X.Y.Z
#ifndef AppVersion
  #define AppVersion "0.9.1"
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
; KeepT icon instead of Inno Setup's default images, one file per display scaling (100 to 200 %)
WizardSmallImageFile=..\packaging\wizard\small-100.bmp,..\packaging\wizard\small-125.bmp,..\packaging\wizard\small-150.bmp,..\packaging\wizard\small-200.bmp
WizardImageFile=..\packaging\wizard\large-100.bmp,..\packaging\wizard\large-125.bmp,..\packaging\wizard\large-150.bmp,..\packaging\wizard\large-200.bmp
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

en.DownloadSize=Download during installation: about %1 MB, %2 of the %3 language models needed (only this once).
de.DownloadSize=Download während der Installation: etwa %1 MB, %2 der %3 benötigten Sprachmodelle (nur dieses eine Mal).
es.DownloadSize=Descarga durante la instalación: unos %1 MB, %2 de los %3 modelos de idioma necesarios (solo esta vez).
fr.DownloadSize=Téléchargement pendant l'installation : environ %1 Mo, %2 des %3 modèles de langue nécessaires (une seule fois).
it.DownloadSize=Download durante l'installazione: circa %1 MB, %2 dei %3 modelli linguistici necessari (solo questa volta).
pt.DownloadSize=Transferência durante a instalação: cerca de %1 MB, %2 dos %3 modelos de idioma necessários (só desta vez).
nl.DownloadSize=Download tijdens de installatie: ongeveer %1 MB, %2 van de %3 benodigde taalmodellen (alleen deze keer).
pl.DownloadSize=Pobieranie podczas instalacji: około %1 MB, %2 z %3 potrzebnych modeli językowych (tylko ten jeden raz).
en.DownloadNone=Nothing to download: the %1 language models needed are already installed.
de.DownloadNone=Nichts herunterzuladen: die %1 benötigten Sprachmodelle sind bereits installiert.
es.DownloadNone=No hay nada que descargar: los %1 modelos de idioma necesarios ya están instalados.
fr.DownloadNone=Rien à télécharger : les %1 modèles de langue nécessaires sont déjà installés.
it.DownloadNone=Niente da scaricare: i %1 modelli linguistici necessari sono già installati.
pt.DownloadNone=Nada para transferir: os %1 modelos de idioma necessários já estão instalados.
nl.DownloadNone=Niets te downloaden: de %1 benodigde taalmodellen zijn al geïnstalleerd.
pl.DownloadNone=Nie ma nic do pobrania: %1 potrzebnych modeli językowych jest już zainstalowanych.
en.NoSources=Choose at least one language to translate from.
de.NoSources=Wähle mindestens eine Sprache, aus der übersetzt werden soll.
es.NoSources=Elige al menos un idioma desde el que traducir.
fr.NoSources=Choisissez au moins une langue à traduire.
it.NoSources=Scegli almeno una lingua da cui tradurre.
pt.NoSources=Escolha pelo menos um idioma a partir do qual traduzir.
nl.NoSources=Kies ten minste één taal om uit te vertalen.
pl.NoSources=Wybierz co najmniej jeden język, z którego chcesz tłumaczyć.
en.TargetMark=(target)
de.TargetMark=(Ziel)
es.TargetMark=(destino)
fr.TargetMark=(cible)
it.TargetMark=(destinazione)
pt.TargetMark=(destino)
nl.TargetMark=(doel)
pl.TargetMark=(docelowy)

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
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

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
  SourceBoxes: array of TNewCheckBox;
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
    if SourceBoxes[I].Checked then
    begin
      if Result <> '' then
        Result := Result + ',';
      Result := Result + LangCodes[I];
    end;
end;

// Packages the current choice needs (Missing = only those not installed yet), comma separated.
function ChoicePairs(Missing: Boolean): String;
var
  I: Integer;
  Chain, Code: String;
begin
  Result := '';
  for I := 0 to GetArrayLength(LangCodes) - 1 do
    if SourceBoxes[I].Checked and (LangCodes[I] <> SelectedTarget) then
    begin
      Chain := KeepTRoute(LangCodes[I], SelectedTarget);
      while Chain <> '' do
      begin
        Code := PopItem(Chain);
        if (Code <> '') and not InList(Code, Result) and not (Missing and ModelInstalled(Code)) then
        begin
          if Result <> '' then
            Result := Result + ',';
          Result := Result + Code;
        end;
      end;
    end;
end;

function NeededPairs: String;
begin
  Result := ChoicePairs(True);
end;

function CountItems(List: String): Integer;
begin
  Result := 0;
  while List <> '' do
    if PopItem(List) <> '' then
      Result := Result + 1;
end;

procedure UpdateSize(Sender: TObject);
var
  Pairs: String;
  Total: Int64;
  Missing, All: Integer;
begin
  Pairs := NeededPairs;
  Missing := CountItems(Pairs);
  All := CountItems(ChoicePairs(False));
  Total := 0;
  while Pairs <> '' do
    Total := Total + PairSizes[PairIndex(PopItem(Pairs))];
  if All = 0 then
    SizeLabel.Caption := CustomMessage('NoSources')
  else if Missing = 0 then
    SizeLabel.Caption := FmtMessage(CustomMessage('DownloadNone'), [IntToStr(All)])
  else
    SizeLabel.Caption := FmtMessage(CustomMessage('DownloadSize'), [IntToStr((Total + 524288) div 1048576), IntToStr(Missing), IntToStr(All)]);
end;

// The target language is shown checked, greyed out and marked "(target)": it needs no download.
procedure ShowTarget;
var
  I: Integer;
begin
  for I := 0 to GetArrayLength(LangCodes) - 1 do
  begin
    if I = TargetCombo.ItemIndex then
    begin
      SourceBoxes[I].Checked := True;
      SourceBoxes[I].Enabled := False;
      SourceBoxes[I].Caption := LangNames[I] + ' ' + CustomMessage('TargetMark');
    end
    else
    begin
      SourceBoxes[I].Enabled := True;
      SourceBoxes[I].Caption := LangNames[I];
    end;
  end;
end;

procedure TargetChanged(Sender: TObject);
begin
  ShowTarget;
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
  SizeLabel.Height := ScaleY(36);
  SizeLabel.Top := FromLabel.Top + FromLabel.Height + ScaleY(8) + 4 * ScaleY(24) + ScaleY(10);

  // Two columns of check boxes, indented from the page edge so they are never clipped.
  SetArrayLength(SourceBoxes, GetArrayLength(LangCodes));
  for I := 0 to GetArrayLength(LangCodes) - 1 do
  begin
    SourceBoxes[I] := TNewCheckBox.Create(LangPage);
    SourceBoxes[I].Parent := LangPage.Surface;
    SourceBoxes[I].Caption := LangNames[I];
    SourceBoxes[I].Left := ScaleX(12) + (I mod 2) * (LangPage.SurfaceWidth div 2);
    SourceBoxes[I].Top := FromLabel.Top + FromLabel.Height + ScaleY(8) + (I div 2) * ScaleY(24);
    SourceBoxes[I].Width := LangPage.SurfaceWidth div 2 - ScaleX(16);
    SourceBoxes[I].Height := ScaleY(20);
    SourceBoxes[I].OnClick := @UpdateSize;
  end;

  // Defaults: the previous choice when reinstalling; otherwise the Windows language as target,
  // and the Windows language, English and the target as languages to translate from.
  if not RegQueryStringValue(HKCU, 'Software\KeepT', 'TargetLang', Target) or (LangIndex(Target) < 0) then
    Target := WindowsLang;
  if not RegQueryStringValue(HKCU, 'Software\KeepT', 'SourceLangs', Sources) or (Sources = '') then
    Sources := WindowsLang + ',en,' + Target;
  TargetCombo.ItemIndex := LangIndex(Target);
  for I := 0 to GetArrayLength(LangCodes) - 1 do
    SourceBoxes[I].Checked := InList(LangCodes[I], Sources) or (LangCodes[I] = Target);
  ShowTarget;

  TargetCombo.OnChange := @TargetChanged;
  UpdateSize(nil);

  DownloadPage := CreateDownloadPage(CustomMessage('DownloadingLanguages'), CustomMessage('DownloadingLanguagesHint'), nil);
end;

// Inno Setup's check lists (tasks page, "launch KeepT" on the last page) clip their boxes on the
// left with a high display scaling, depending on the monitor setup (fixed only in Inno Setup
// 7.2, still a preview). They are hidden and shown as plain check boxes that stay in sync with
// the original list, which Setup keeps using for the tasks and the run entries.
var
  TaskBoxes, RunBoxes: array of TNewCheckBox;

procedure TaskBoxClick(Sender: TObject);
begin
  WizardForm.TasksList.Checked[TNewCheckBox(Sender).Tag] := TNewCheckBox(Sender).Checked;
end;

procedure RunBoxClick(Sender: TObject);
begin
  WizardForm.RunList.Checked[TNewCheckBox(Sender).Tag] := TNewCheckBox(Sender).Checked;
end;

procedure MirrorCheckList(List: TNewCheckListBox; var Boxes: array of TNewCheckBox; OnClick: TNotifyEvent);
var
  I: Integer;
begin
  for I := 0 to GetArrayLength(Boxes) - 1 do
    Boxes[I].Free;
  SetArrayLength(Boxes, List.Items.Count);
  for I := 0 to List.Items.Count - 1 do
  begin
    Boxes[I] := TNewCheckBox.Create(WizardForm);
    Boxes[I].Parent := List.Parent;
    Boxes[I].Caption := List.ItemCaption[I];
    Boxes[I].Checked := List.Checked[I];
    Boxes[I].Enabled := List.ItemEnabled[I];
    Boxes[I].Tag := I;
    Boxes[I].Left := List.Left + ScaleX(4);
    Boxes[I].Top := List.Top + ScaleY(2) + I * ScaleY(26);
    Boxes[I].Width := List.Width - ScaleX(8);
    Boxes[I].Height := ScaleY(22);
    Boxes[I].OnClick := OnClick;
  end;
  List.Visible := False;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectTasks then
    MirrorCheckList(WizardForm.TasksList, TaskBoxes, @TaskBoxClick)
  else if (CurPageID = wpFinished) and (WizardForm.RunList.Items.Count > 0) then
    MirrorCheckList(WizardForm.RunList, RunBoxes, @RunBoxClick);
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
