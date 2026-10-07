# WallpaperApp — 4K Hareketli Masaüstü Duvar Kağıdı Yönetim Uygulaması

WPF tabanlı, WorkerW katmanına gömülen, GPU hızlandırmalı hareketli masaüstü
uygulaması. Arka plan motoru (duvar kağıdı) ile modern bir yönetim arayüzü
ayrı pencereler olarak çalışır.

## Bileşenler

- `WallpaperWindow` — videoyu/GIF'i masaüstünün WorkerW katmanına gömer, oynatır,
  tam ekran uygulama açıldığında otomatik duraklar.
- `ControlPanel` — dark-mode yönetim arayüzü (dosya seçimi, doldurma modu,
  çözünürlük/ölçek, ses, oynatma kontrolü).
- `AppSettings` + `SettingsService` — `%LOCALAPPDATA%\WallpaperApp\settings.json`
  üzerinden kalıcı yapılandırma.
- `TrayIcon` — sistem tepsisi (Ayarları Aç / Duraklat-Oynat / Çıkış).
- `Win32Interop` — `user32.dll` sarmalayıcıları.

## Derleme

```powershell
dotnet build -c Release
```

## Çalıştırma

```powershell
dotnet run -c Release
```

## Dağıtım

```powershell
dotnet publish -c Release -r win-x64 --self-contained false -o publish
```

`publish` klasörünün tamamını (içindeki `libvlc` klasörüyle birlikte) kurulum
klasörüne kopyalayın. VLC eklentileri tek dosyaya gömülemediği için
`PublishSingleFile` kullanılmaz.

## Notlar

- Video, WPF `MediaElement` yerine **LibVLC** (LibVLCSharp) ile oynatılır.
  `MediaElement` eski Windows Media Player altyapısını kullandığı için AV1
  dosyalarını hiç açamıyordu; LibVLC AV1 / VP9 / H.264 / HEVC'yi (MP4, MKV,
  WebM) GPU ile çözer.
- İlk açılışta VLC eklenti önbelleği (`libvlc\win-x64\plugins\plugins.dat`)
  oluşturulur; bu açılış ~15 sn sürer, sonrakiler ~1,5 sn.
- GIF dosyaları VLC ile değil `Image` + `BitmapImage` ile oynatılır.
- .NET Framework 4.8 (Windows 10/11'de hazır gelir) için `WallpaperApp.csproj`
  içindeki `TargetFramework` değerini `net48` yapın; ayrıca `System.Text.Json`
  NuGet paketini ekleyin (net48 tabanında yerleşik değildir).
- Uygulama penceresi kapatıldığında tepsiye küçülür; tamamen kapatmak için tepsi
  simgesine sağ tıklayıp "Çıkış" seçin.
