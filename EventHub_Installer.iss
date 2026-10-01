#define MyAppName "EventHub"
#define MyAppVersion "0.2.1 Beta"
#define MyAppPublisher "Cohentra Digital"
#define MyAppExeName "EventHub.exe"

[Setup]
AppId={{D7A6D451-4F0A-4ACD-9A1C-7F9A9B3C2810}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\EventHub
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=EventHub-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=eventhub.ico

[Tasks]
Name: "startup"; Description: "EventHub openen bij het starten van Windows"; GroupDescription: "Opstarten:"
Name: "desktopicon"; Description: "Snelkoppeling op het bureaublad maken"; GroupDescription: "Extra snelkoppelingen:"

[Files]
Source: "dist\EventHub\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "eventhub_logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "eventhub.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "settings_gear.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\EventHub Server\*"; DestDir: "{app}\Server"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\EventHub"; Filename: "{app}\{#MyAppExeName}"
Name: "{userstartup}\EventHub"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup
Name: "{autodesktop}\EventHub"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\EventHub Server (standalone)"; Filename: "{app}\Server\EventHub Server.exe"
Name: "{autodesktop}\EventHub Server"; Filename: "{app}\Server\EventHub Server.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "EventHub starten"; Flags: nowait postinstall skipifsilent
