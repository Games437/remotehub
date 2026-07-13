[Setup]
AppId={{8F3B2C1A-4D5E-4F6A-9B7C-1234567890AB}}
AppName=RemoteHub Agent
AppVersion=0.1.0
AppPublisher=RemoteHub
DefaultDirName={autopf}\RemoteHub Agent
DefaultGroupName=RemoteHub Agent
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=RemoteHubAgentSetup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\RemoteHubAgent.exe
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\RemoteHubAgent.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\RemoteHub Agent"; Filename: "{app}\RemoteHubAgent.exe"
Name: "{autodesktop}\RemoteHub Agent"; Filename: "{app}\RemoteHubAgent.exe"

[Run]
Filename: "{app}\RemoteHubAgent.exe"; Description: "Launch RemoteHub Agent"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"