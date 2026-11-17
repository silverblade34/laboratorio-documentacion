[Setup]
AppId=MateriaPrima.Especificaciones
AppName=Especificaciones de Materias Primas
AppVersion=1.2.3
DefaultDirName={localappdata}\Programs\MateriaPrima
DefaultGroupName=Especificaciones de Materias Primas
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=MateriaPrima-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\MateriaPrima.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "dist\MateriaPrima\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Especificaciones de Materias Primas"; Filename: "{app}\MateriaPrima.exe"

Name: "{autodesktop}\Materia"; Filename: "{app}\MateriaPrima.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MateriaPrima.exe"; Description: "Abrir Especificaciones de Materias Primas"; Flags: nowait postinstall skipifsilent
