#define MyAppName "NetworkAutomation Desktop"
#define MyAppVersion "7.0.3"
#define MyAppExeName "NetworkAutomation.exe"

[Setup]
AppId={{5B35C4A0-5D75-4DCE-B948-4D6B3B8E7D70}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={localappdata}\Programs\NetworkAutomation
DefaultGroupName=NetworkAutomation
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\release
OutputBaseFilename=NetworkAutomation_Setup_7.0.3
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài Desktop"; GroupDescription: "Tùy chọn:"; Flags: unchecked
Name: "startup"; Description: "Khởi động NetworkAutomation cùng Windows"; GroupDescription: "Tùy chọn:"; Flags: unchecked

[Files]
Source: "..\dist\NetworkAutomation\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NetworkAutomation Desktop"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\NetworkAutomation Desktop"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\NetworkAutomation Desktop"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Mở NetworkAutomation Desktop"; Flags: nowait postinstall skipifsilent
