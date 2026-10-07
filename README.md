# Masaüstü Araçları

İki Windows programı ve ikisini birlikte kuran tek bir kurulum dosyası:

- **ApexTube 8K Downloader** (`apextube/`): YouTube'dan 8K'ya kadar video, klip (zaman aralığı) ve MP3 indirici. Python + CustomTkinter, yt-dlp ve FFmpeg.
- **Hareketli Duvar Kağıdı** (`wallpaper/`): Videoyu masaüstü arka planında oynatır. .NET 9 WPF + LibVLC (AV1/VP9/H.264, GPU hızlandırmalı).

## Kurulum (kullanıcılar için)

1. [Releases](https://github.com/AktasFurkann/masaustu-araclari/releases/latest) sayfasından `MasaustuAraclari-Setup-x.y.z.exe` dosyasını indirin.
2. Çalıştırın. Windows "bilgisayarınızı korudu" uyarısı verirse **Ek bilgi → Yine de çalıştır** deyin (programlar imzasız olduğu için).
3. Kurmak istediğiniz programları seçip kurulumu bitirin. Ek bir şey kurmanız gerekmez.

Güncellemeler programların içinden alınır: ApexTube'da başlıktaki **Güncellemeleri Denetle**, duvar kağıdında ayarlar penceresindeki **Güncelleme** bölümü.

> Not: AV1 videoların akıcı oynaması için AV1 donanım çözme destekli ekran kartı gerekir (NVIDIA RTX 30+, AMD RX 6000+, Intel 11. nesil+). Daha eski kartlarda ApexTube'da **H.264** formatını seçin.

## Yeni sürüm yayınlama (geliştirici için)

Gerekenler: Python 3.12 (+ `apextube/requirements.txt`), .NET 9 SDK, [Inno Setup 6](https://jrsoftware.org/isinfo.php), GitHub CLI (`gh auth login` ile giriş yapılmış).

```powershell
.\yayinla.ps1 -Version 1.1.0 -Notes "Neler değişti"
```

Betik sürüm numarasını iki programa yazar, ikisini derler, `installer\Output` altında kurulum dosyasını üretir, değişiklikleri GitHub'a gönderir ve yeni sürümü yayınlar. Yalnızca kurulum dosyası üretip denemek için `-SadeceDerle` ekleyin.
