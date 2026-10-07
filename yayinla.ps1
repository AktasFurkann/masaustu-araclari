<#
.SYNOPSIS
    İki programı derler, kurulum dosyasını (setup.exe) oluşturur ve GitHub'a yeni sürüm olarak yayınlar.
    Yayınlanan sürüm, programlardaki "Güncelle" düğmesiyle kullanıcılara ulaşır.

.EXAMPLE
    .\yayinla.ps1 -Version 1.1.0 -Notes "Klip indirme hızlandı"

.EXAMPLE
    .\yayinla.ps1 -Version 1.1.0 -SadeceDerle
    GitHub'a yüklemeden yalnızca installer\Output altında setup.exe üretir (denemek için).
#>
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Notes = "",
    [switch]$SadeceDerle
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$repo = "AktasFurkann/masaustu-araclari"
$utf8 = New-Object System.Text.UTF8Encoding $false

function Step([string]$message) { Write-Host "`n=== $message ===" -ForegroundColor Cyan }
function Assert-Success([string]$what) {
    if ($LASTEXITCODE -ne 0) { throw "$what başarısız oldu (çıkış kodu $LASTEXITCODE)." }
}

if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Sürüm x.y.z biçiminde olmalı (ör. 1.2.0)." }

if (-not $SadeceDerle) {
    if (git -C $root tag --list "v$Version") { throw "v$Version zaten yayınlanmış; daha yüksek bir sürüm numarası verin." }
    gh auth status *> $null
    Assert-Success "GitHub girişi kontrolü ('gh auth login' ile giriş yapın)"
}

Step "Sürüm numarası $Version olarak ayarlanıyor"
[IO.File]::WriteAllText("$root\VERSION", $Version, $utf8)

$configPath = "$root\apextube\config.py"
$config = [IO.File]::ReadAllText($configPath)
$config = [regex]::Replace($config, 'APP_VERSION = "[^"]*"', "APP_VERSION = `"$Version`"")
[IO.File]::WriteAllText($configPath, $config, $utf8)

$projPath = "$root\wallpaper\WallpaperApp.csproj"
$proj = [IO.File]::ReadAllText($projPath)
$proj = [regex]::Replace($proj, '<Version>[^<]*</Version>', "<Version>$Version</Version>")
[IO.File]::WriteAllText($projPath, $proj, $utf8)

Step "ApexTube 8K Downloader derleniyor"
Push-Location "$root\apextube"
try { python build_exe.py --no-desktop; Assert-Success "ApexTube derlemesi" } finally { Pop-Location }

Step "Hareketli Duvar Kağıdı derleniyor"
$publish = "$root\wallpaper\publish"
if (Test-Path $publish) { Remove-Item $publish -Recurse -Force }
# .NET çalışma zamanı içine gömülür: hedef bilgisayarda .NET kurulu olması gerekmez.
dotnet publish $projPath -c Release -r win-x64 --self-contained true -o $publish
Assert-Success "Duvar kağıdı derlemesi"

# VLC eklenti önbelleği önceden oluşturulur; aksi halde kurulumdan sonraki ilk açılış ~15 sn sürer.
Start-Process -FilePath "$publish\WallpaperApp.exe" -ArgumentList "--generate-vlc-cache" -Wait
if (-not (Test-Path "$publish\libvlc\win-x64\plugins\plugins.dat")) { throw "VLC eklenti önbelleği oluşturulamadı." }

Step "Kurulum dosyası oluşturuluyor"
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup bulunamadı: winget install JRSoftware.InnoSetup" }
& $iscc "/DAppVersion=$Version" "$root\installer\setup.iss"
Assert-Success "Kurulum dosyası oluşturma"
$setup = "$root\installer\Output\MasaustuAraclari-Setup-$Version.exe"

if ($SadeceDerle) {
    Write-Host "`nHazır (yayınlanmadı): $setup" -ForegroundColor Green
    return
}

Step "GitHub'a gönderiliyor"
git -C $root add -A
git -C $root commit -m "Sürüm $Version"
Assert-Success "git commit"
git -C $root tag "v$Version"
git -C $root push origin HEAD --tags
Assert-Success "git push"

if (-not $Notes) { $Notes = "Sürüm $Version" }
gh release create "v$Version" $setup --repo $repo --title "v$Version" --notes $Notes
Assert-Success "GitHub sürümü oluşturma"

Write-Host "`nv$Version yayınlandı: https://github.com/$repo/releases/tag/v$Version" -ForegroundColor Green
Write-Host "Programlardaki 'Güncelle' düğmesi artık bu sürümü bulacak." -ForegroundColor Green
