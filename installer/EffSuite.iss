; =====================================================================
; EffSuite - Inno Setup script
; Gamma-Ray Spectrometry Efficiency Transfer & True Coincidence Summing
; =====================================================================

#define MyAppName "EffSuite"
#define MyAppVersion "0.5.3"
#define MyAppPublisher "GL"
#define MyAppURL "https://github.com/luttegu/EffSuite"
#define MyAppExeName "EffSuite_GUI.exe"
#define MyAppCliName "EffSuite_CLI.exe"
#define MyAppId "{{B25C1CCB-A9CA-4B1C-9F95-1FD8481EA283}"

#ifndef AppSource
  #define AppSource "..\dist\EffSuite"
#endif

#ifndef OutputPath
  #define OutputPath "..\installer_output"
#endif

[Setup]
; --- Application Identification ---
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion} (Beta)
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={code:GetDefaultInstallDir}
DefaultGroupName={#MyAppName}

; --- Installation Experience & Behavior ---
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes
DisableProgramGroupPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
UsedUserAreasWarning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; --- Output & Compression ---
OutputDir={#OutputPath}
OutputBaseFilename=EffSuite_{#MyAppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=12

; --- Setup appearance ---
SetupIconFile=..\src\effsuite\assets\icon.ico
WizardStyle=modern
WizardImageStretch=no
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=yes

; --- Version Metadata Embedded in Setup.exe ---
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=EffSuite Efficiency Transfer & True Coincidence Summing Suite (Beta)
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}:"; Flags: unchecked
Name: "addtopath"; Description: "Add the EffSuite folder to the user PATH (run EffSuite_CLI.exe from any terminal)"; GroupDescription: "System Integration:"; Flags: unchecked

[Dirs]
Name: "{app}"
; Data and results live next to the program only in the Genie 2000 layout
; (C:\GENIE2K\EffSuite) or when an earlier installation already set EFFSUITE_ROOT
; to this folder. Otherwise EffSuite chooses Documents\EffSuite on first start.
Name: "{app}\Data"; Check: UsesAppAsRoot
; The user's own materials (only the original EFFTRAN / MEFFTRAN materials are bundled)
Name: "{app}\Data\Composition"; Check: UsesAppAsRoot
Name: "{app}\Data\Material"; Check: UsesAppAsRoot
Name: "{app}\Results"; Check: UsesAppAsRoot

[Files]
; Main application binaries and dependencies from PyInstaller bundle
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Core technical documentation and validation reports
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\*.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\RELEASE_NOTES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\src\effsuite\assets\templates\Material_Composition.xlsx"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Desktop and Start Menu shortcuts
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\EffSuite Command Line (CLI)"; Filename: "{cmd}"; Parameters: "/k """"{app}\{#MyAppCliName}"""" --help"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"

; Workspace & Folder Shortcuts
Name: "{group}\Folders\Data Library"; Filename: "{app}\Data"; Check: UsesAppAsRoot
Name: "{group}\Folders\Calculation Results"; Filename: "{app}\Results"; Check: UsesAppAsRoot
Name: "{group}\Folders\Application Directory"; Filename: "{app}"

; Technical Documentation Shortcuts
Name: "{group}\Documentation\User Guide (Markdown)"; Filename: "{app}\docs\USER_GUIDE.md"
Name: "{group}\Documentation\Materials Reference"; Filename: "{app}\docs\MATERIALS.md"
Name: "{group}\Documentation\Summing Factor Uncertainty"; Filename: "{app}\docs\TCS_UNCERTAINTY.md"
Name: "{group}\Documentation\Validation Report (DET952, DET007)"; Filename: "{app}\docs\VALIDATION.md"
Name: "{group}\Documentation\Third-Party Notices"; Filename: "{app}\THIRD_PARTY_NOTICES.md"
Name: "{group}\Documentation\Licence (GPL-3.0-or-later)"; Filename: "{app}\LICENSE.txt"
Name: "{group}\Documentation\Material Composition Template (Excel)"; Filename: "{app}\Material_Composition.xlsx"

; Uninstaller Shortcut
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

[Registry]
; Register application in App Paths for Windows Run (Win+R) dialog (per-user HKCU requires no admin elevation)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey noerror
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey noerror
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppCliName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppCliName}"; Flags: uninsdeletekey noerror
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppCliName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey noerror

; EffSuite standard environment pointer
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "EFFSUITE_ROOT"; ValueData: "{app}"; Flags: uninsdeletevalue noerror; Check: UsesAppAsRoot

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\docs\USER_GUIDE.md"; Description: "Open the EffSuite User Guide"; Flags: postinstall shellexec skipifsilent unchecked
; Silent upgrade started by the in-app updater (/RELAUNCH=1): restart EffSuite.
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifnotsilent runasoriginaluser; Check: RelaunchRequested

[Code]
function GetDefaultInstallDir(Param: string): string;
begin
  if DirExists('C:\GENIE2K') then
    Result := 'C:\GENIE2K\EffSuite'
  else
    Result := ExpandConstant('{autopf}\EffSuite');
end;

function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;

function UsesAppAsRoot: Boolean;
{ True for the Genie 2000 layout, or when EFFSUITE_ROOT already points to the
  installation folder (installed by an earlier version: keep its data there). }
var
  Existing: string;
begin
  Result := CompareText(Copy(AddBackslash(ExpandConstant('{app}')), 1, 11), 'C:\GENIE2K\') = 0;
  if (not Result) and RegQueryStringValue(HKCU, 'Environment', 'EFFSUITE_ROOT', Existing) then
    Result := CompareText(RemoveBackslashUnlessRoot(Existing), RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) = 0;
end;

function GetEnvRootKey: Integer;
begin
  Result := HKCU;
end;

function GetEnvSubKey: string;
begin
  Result := 'Environment';
end;

function IsPathAlreadyPresent(PathToAdd: string): Boolean;
var
  CurrentPath: string;
begin
  Result := False;
  if RegQueryStringValue(GetEnvRootKey, GetEnvSubKey, 'Path', CurrentPath) then
  begin
    CurrentPath := ';' + CurrentPath + ';';
    Result := (Pos(';' + Uppercase(PathToAdd) + ';', Uppercase(CurrentPath)) > 0);
  end;
end;

procedure AddAppToSystemPath;
var
  CurrentPath, AppPath: string;
  RootKey: Integer;
  SubKey: string;
begin
  AppPath := ExpandConstant('{app}');
  if not IsPathAlreadyPresent(AppPath) then
  begin
    RootKey := GetEnvRootKey;
    SubKey := GetEnvSubKey;
    if RegQueryStringValue(RootKey, SubKey, 'Path', CurrentPath) then
    begin
      if (Length(CurrentPath) > 0) and (CurrentPath[Length(CurrentPath)] <> ';') then
        CurrentPath := CurrentPath + ';';
      CurrentPath := CurrentPath + AppPath;
      RegWriteExpandStringValue(RootKey, SubKey, 'Path', CurrentPath);
    end
    else
    begin
      RegWriteExpandStringValue(RootKey, SubKey, 'Path', AppPath);
    end;
  end;
end;

procedure RemoveAppFromSystemPath;
var
  CurrentPath, AppPath, SearchStr: string;
  RootKey: Integer;
  SubKey: string;
  P: Integer;
begin
  AppPath := ExpandConstant('{app}');
  RootKey := GetEnvRootKey;
  SubKey := GetEnvSubKey;
  if RegQueryStringValue(RootKey, SubKey, 'Path', CurrentPath) then
  begin
    SearchStr := ';' + Uppercase(AppPath);
    P := Pos(SearchStr, ';' + Uppercase(CurrentPath));
    if P > 0 then
    begin
      CurrentPath := ';' + CurrentPath + ';';
      SearchStr := ';' + AppPath + ';';
      P := Pos(Uppercase(SearchStr), Uppercase(CurrentPath));
      if P > 0 then
      begin
        Delete(CurrentPath, P, Length(SearchStr) - 1);
        if (Length(CurrentPath) > 0) and (CurrentPath[1] = ';') then
          Delete(CurrentPath, 1, 1);
        if (Length(CurrentPath) > 0) and (CurrentPath[Length(CurrentPath)] = ';') then
          Delete(CurrentPath, Length(CurrentPath), 1);
        RegWriteExpandStringValue(RootKey, SubKey, 'Path', CurrentPath);
      end;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('addtopath') then
    begin
      try
        AddAppToSystemPath();
      except
      end;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    try
      RemoveAppFromSystemPath();
    except
    end;
  end;
end;
