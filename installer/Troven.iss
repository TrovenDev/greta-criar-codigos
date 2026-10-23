#ifndef ProjectRoot
  #error ProjectRoot precisa ser informado pelo script de build.
#endif
#ifndef AppVersion
  #define AppVersion "9.0.0"
#endif
#define Release ProjectRoot + "\dist\Troven Cadastro"

[Setup]
AppId=TrovenCadastro.Desktop
AppName=Troven Cadastro
AppVersion={#AppVersion}
AppVerName=Troven Cadastro {#AppVersion}
AppPublisher=Troven
AppPublisherURL=https://marca.troven.com.br/
DefaultDirName={localappdata}\Programs\Troven Cadastro
DefaultGroupName=Troven
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
AppMutex=TrovenCadastroDesktop
CloseApplications=yes
RestartApplications=no
OutputDir={#ProjectRoot}\dist
OutputBaseFilename=Troven-Cadastro-Instalador-v{#AppVersion}
SetupIconFile={#ProjectRoot}\app\assets\troven.ico
UninstallDisplayIcon={app}\Troven Cadastro.exe
UninstallDisplayName=Troven Cadastro
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
WizardImageFile=wizard-side-small.bmp,wizard-side.bmp
WizardSmallImageFile=wizard-icon.bmp
WizardImageStretch=yes
WizardImageBackColor=$00F0352B
DisableWelcomePage=no
DisableProgramGroupPage=yes
ShowLanguageDialog=no
VersionInfoCompany=Troven
VersionInfoDescription=Instalador do Troven Cadastro
VersionInfoProductName=Troven Cadastro
VersionInfoVersion={#AppVersion}.0

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
WelcomeLabel1=Boas-vindas ao Troven Cadastro
WelcomeLabel2=Do estoque à grade, em um fluxo simples.%n%nEste assistente instala o Troven Cadastro no seu computador, com acesso pelo menu Iniciar.%n%nSuas reservas, regras e lotes ficam separados do programa e são preservados nas atualizações e na desinstalação.%n%nSe necessário, o componente Microsoft WebView2 será preparado usando uma conexão com a internet.%n%nClique em Avançar para continuar.
FinishedLabel=O Troven Cadastro está instalado.%n%nComece pelo estoque e use o tutorial dentro do sistema para conhecer o fluxo.%n%nPara retomar uma versão antiga, acesse Base e continuidade e escolha o arquivo reservas.sqlite3 anterior.

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "{#Release}\Troven Cadastro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Release}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LEIA-ME.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\.build\tools\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{group}\Troven Cadastro"; Filename: "{app}\Troven Cadastro.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Troven Cadastro"; Filename: "{app}\Troven Cadastro.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Troven Cadastro.exe"; Description: "Abrir o Troven Cadastro"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := (RegQueryStringValue(HKCU, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
  if not Result then
    Result := (RegQueryStringValue(HKLM32, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
  if (not Result) and IsWin64 then
    Result := (RegQueryStringValue(HKLM64, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
begin
  Result := '';
  if not HasWebView2 then begin
    WizardForm.StatusLabel.Caption := 'Preparando o Microsoft WebView2. Mantenha a conexão com a internet.';
    ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
      Result := 'Não foi possível preparar o Microsoft WebView2. Verifique a conexão com a internet e execute novamente este instalador.'
    else if not HasWebView2 then
      Result := 'O Microsoft WebView2 ainda não está disponível. Verifique a conexão com a internet e execute novamente este instalador.';
  end;
end;
