; SmolSlime Configurator – Windows-Installer (Inno Setup)
; Installiert pro Benutzer ohne Admin-Rechte, damit der Update-Knopf der App
; die .exe spaeter selbst ersetzen kann. Version kommt aus dem Build: /DMyAppVersion=1.0.x
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "SmolSlime Configurator"
#define MyAppExeName "SmolSlimeConfigurator.exe"

[Setup]
AppId={{0FEB2833-581F-40E8-8503-1AA9BBBC6C11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=LucyWolf
AppPublisherURL=https://github.com/LucyWolf/SmolSlimeConfigurator
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SmolSlimeConfigurator-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\SmolSlimeConfigurator-Windows.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[UninstallDelete]
; Rest eines Updates (alte, umbenannte .exe)
Type: files; Name: "{app}\{#MyAppExeName}.alt"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
