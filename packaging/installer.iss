; Instalador do LUIS MEDIA TOOLS (Inno Setup 6).
; Compilado pelo GitHub Actions (.github/workflows/release.yml) ou localmente com:
;   iscc /DAppVersion=1.0.0 /DSourceDir=..\dist\LUIS MEDIA TOOLS packaging\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\LUIS MEDIA TOOLS"
#endif
#define AppName "LUIS MEDIA TOOLS"
#define AppExe "LUIS MEDIA TOOLS.exe"
#define AppPublisher "LuisCodeMaster"
#define AppURL "https://github.com/LuisCodeMaster/LUIS-MEDIA-TOOLS"

[Setup]
; AppId fixo: identifica o programa nas atualizacoes (nao mudar entre versoes)
AppId={{6B8E4D3A-2F1C-4A7B-9E55-0C4D7A1B9F21}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Instala sem pedir administrador (na pasta do usuario); quem quiser escolhe "para todos"
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
SetupIconFile=..\src\luismedia\gui\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputDir=..\dist
OutputBaseFilename=LUIS-MEDIA-TOOLS-Setup-{#AppVersion}
Compression=lzma2/max
; processo separado de 64 bits: o compressor de 32 bits ficava sem memoria com ~700 MB de arquivos
LZMAUseSeparateProcess=yes
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
Filename: "https://ollama.com/download"; Description: "Baixar o Ollama (opcional: resumo, quiz, cortes e slides com IA)"; Flags: shellexec postinstall skipifsilent unchecked; Check: not OllamaInstalado

[Code]
function OllamaInstalado: Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'))
            or FileExists(ExpandConstant('{commonpf}\Ollama\ollama.exe'));
end;
