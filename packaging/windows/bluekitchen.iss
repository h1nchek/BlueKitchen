#define MyAppName "BlueKitchen"
#define MyAppExeName "bluekitchen.exe"

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{B6D9E0F1-6B18-4E9D-8B2A-2E7C3B5A91D4}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher=BlueKitchen contributors
DefaultDirName={autopf}\BlueKitchen
DefaultGroupName=BlueKitchen
DisableProgramGroupPage=yes
OutputBaseFilename=BlueKitchen-Setup-{#AppVersion}-windows-x86_64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Files]
Source: "..\..\dist\bluekitchen.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\bluekitchen-gui.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\BlueKitchen command-line tool"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\BlueKitchen GUI"; Filename: "{app}\bluekitchen-gui.exe"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--help"; Description: "Show BlueKitchen command-line help"; Flags: postinstall skipifsilent
