#define AppVersion GetStringFileVersion(AddBackslash(SourcePath) + "..\\dist\\StargateDialer.exe")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{7C6A6A9F-0F39-424D-95DA-2BB01171D243}
AppName=Stargate Dialing Computer + DHD
AppVersion={#AppVersion}
AppPublisher=Stargate Fan Project
DefaultDirName={autopf}\Stargate Dialer
DefaultGroupName=Stargate Dialer
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=StargateDialer-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\stargate_icon.ico
UninstallDisplayIcon={app}\StargateDialer.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; Flags: unchecked

[Files]
Source: "..\dist\StargateDialer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Stargate Dialer"; Filename: "{app}\StargateDialer.exe"
Name: "{autodesktop}\Stargate Dialer"; Filename: "{app}\StargateDialer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StargateDialer.exe"; Description: "Launch Stargate Dialer"; Flags: nowait postinstall skipifsilent
