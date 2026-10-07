; Masaüstü Araçları kurulumu: ApexTube 8K Downloader + Hareketli Duvar Kağıdı
; Derleme: yayinla.ps1 (ISCC /DAppVersion=x.y.z setup.iss)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Masaüstü Araçları"
#define ApexExe "ApexTube_8K_Downloader.exe"
#define WallExe "WallpaperApp.exe"

[Setup]
AppId={{D91D8AB3-2E41-4826-8812-15C763368E95}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Furkan
AppPublisherURL=https://github.com/AktasFurkann/masaustu-araclari
VersionInfoVersion={#AppVersion}
; Kullanıcı klasörüne kurulur: yönetici izni gerekmez, programlar kendini güncelleyebilir
; ve VLC eklenti önbelleği (plugins.dat) yazılabilir kalır.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\MasaustuAraclari
DisableDirPage=yes
DisableProgramGroupPage=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\Wallpaper\{#WallExe}
SetupIconFile=..\wallpaper\icon.ico
OutputDir=Output
OutputBaseFilename=MasaustuAraclari-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
ShowLanguageDialog=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Types]
Name: "full"; Description: "Tam kurulum (iki program)"
Name: "custom"; Description: "Özel kurulum"; Flags: iscustom

[Components]
Name: "apextube"; Description: "ApexTube 8K Downloader (YouTube video indirici)"; Types: full custom
Name: "wallpaper"; Description: "Hareketli Duvar Kağıdı"; Types: full custom

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Kısayollar:"
Name: "autostart"; Description: "Hareketli Duvar Kağıdı Windows açılınca başlasın"; GroupDescription: "Başlangıç:"; Components: wallpaper

[Files]
Source: "..\apextube\dist\{#ApexExe}"; DestDir: "{app}\ApexTube"; Components: apextube; Flags: ignoreversion
Source: "..\wallpaper\publish\*"; DestDir: "{app}\Wallpaper"; Components: wallpaper; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ApexTube 8K Downloader"; Filename: "{app}\ApexTube\{#ApexExe}"; Components: apextube
Name: "{autoprograms}\Hareketli Duvar Kağıdı"; Filename: "{app}\Wallpaper\{#WallExe}"; Components: wallpaper
Name: "{autodesktop}\ApexTube 8K Downloader"; Filename: "{app}\ApexTube\{#ApexExe}"; Components: apextube; Tasks: desktopicon
Name: "{autodesktop}\Hareketli Duvar Kağıdı"; Filename: "{app}\Wallpaper\{#WallExe}"; Components: wallpaper; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "HareketliDuvarKagidi"; ValueData: """{app}\Wallpaper\{#WallExe}"""; Flags: uninsdeletevalue; Components: wallpaper; Tasks: autostart
; Seçenek sonradan kaldırılırsa eski kaydı sil
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "HareketliDuvarKagidi"; Flags: deletevalue dontcreatekey; Tasks: not autostart

[Run]
Filename: "{app}\Wallpaper\{#WallExe}"; Description: "Hareketli Duvar Kağıdı'nı başlat"; Flags: nowait postinstall; Components: wallpaper; Check: ShouldLaunch('wallpaper')
Filename: "{app}\ApexTube\{#ApexExe}"; Description: "ApexTube 8K Downloader'ı başlat"; Flags: nowait postinstall; Components: apextube; Check: ShouldLaunch('apextube')

[UninstallDelete]
Type: files; Name: "{app}\Wallpaper\startup.log"

[Code]
var
  WallpaperWasRunning, ApexWasRunning: Boolean;

function IsProcessRunning(const ExeName: String): Boolean;
var
  Locator, Service, Items: Variant;
begin
  Result := False;
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2');
    Items := Service.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name = ''' + ExeName + '''');
    Result := Items.Count > 0;
  except
  end;
end;

procedure KillProcess(const ExeName: String);
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM "' + ExeName + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  // Güncellemede dosyalar kilitli olmasın diye açık programlar kapatılır; kurulumdan sonra yeniden açılır.
  WallpaperWasRunning := IsProcessRunning('{#WallExe}');
  ApexWasRunning := IsProcessRunning('{#ApexExe}');
  KillProcess('{#WallExe}');
  KillProcess('{#ApexExe}');
  Sleep(800);
  Result := '';
end;

// Normal kurulumda bitiş sayfasındaki onay kutuları geçerlidir. Sessiz güncellemede yalnızca
// güncellemeden önce açık olan ya da güncellemeyi başlatan (/RESTART=...) program yeniden açılır.
function ShouldLaunch(const App: String): Boolean;
begin
  if not WizardSilent then
    Result := True
  else if App = 'wallpaper' then
    Result := WallpaperWasRunning or (ExpandConstant('{param:RESTART|}') = 'wallpaper')
  else
    Result := ApexWasRunning or (ExpandConstant('{param:RESTART|}') = 'apextube');
end;

function InitializeUninstall(): Boolean;
begin
  KillProcess('{#WallExe}');
  KillProcess('{#ApexExe}');
  Sleep(800);
  Result := True;
end;
