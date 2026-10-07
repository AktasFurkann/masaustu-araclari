# 🚀 ApexTube 8K Ultra HD YouTube Downloader

ApexTube, YouTube videolarını **4K, 8K (4320p), 60 FPS ve HDR10** kalitelerinde kayıpsız ses ve görüntü birleştirmesi (Muxing) ile indirebilen, modern karanlık temaya sahip, çok iş parçacıklı (multi-threaded) bir masaüstü uygulamasıdır.

---

## 🏗️ 1. Mimari Tasarım ve Çalışma Prensibi

YouTube, 1080p ve üzeri çözünürlüklerde (2K, 4K, 8K) bant genişliğini optimize etmek amacıyla ses ve görüntüyü **ayrı DASH akışları** (Video: VP9/AV01, Ses: Opus/AAC) olarak sunar.

1. **Bağlantı Doğrulama ve Derin Analiz:**
   - Kullanıcı URL girdiğinde `yt-dlp` arka planda videoyu indirmeden meta verileri çeker.
   - Videonun gerçekte desteklediği çözünürlükler (8K, 4K, 2K, 1080p, 720p vb.), HDR ve FPS değerleri taranarak dinamik açılır menüye aktarılır.
2. **Kayıpsız Birleştirme (Muxing):**
   - Video için `bestvideo[height<=H]`, ses için `bestaudio` akışları indirilir.
   - `FFmpeg` arka planda bu iki akışı yeniden kodlama yapmadan (kayıpsız - remux) tek bir `.mp4` veya `.mkv` konteynerinde birleştirir.
3. **Arka Plan İş Parçacıkları (Threading):**
   - Analiz ve indirme işlemleri ana arayüzü (UI Thread) asla dondurmaz.
   - Canlı hız (MB/s), kalan süre (ETA) ve yüzde bilgisi thread-safe callback'ler ile arayüze aktarılır.
4. **Gömülü FFmpeg Çözümü:**
   - Proje, `imageio-ffmpeg` entegrasyonu sayesinde sistem PATH'inde FFmpeg bulunmasa bile Python ortamındaki FFmpeg v7.1 ikili dosyasını otomatik olarak tespit eder ve kullanır.

---

## 📂 2. Proje Klasör Yapısı

```
mp4donusturucu/
│
├── requirements.txt            # Python bağımlılıkları
├── main.py                     # Uygulama başlatıcı (Hi-DPI & Entrypoint)
├── config.py                   # Sabitler, yollar ve çözünürlük haritaları
├── build_exe.py                # Tek tıkla bağımsız Windows .exe derleme scripti
│
├── core/
│   ├── __init__.py
│   ├── analyzer.py             # YouTube meta veri ve çözünürlük analizcisi
│   ├── downloader.py           # yt-dlp & FFmpeg çok iş parçacıklı indirme motoru
│   └── ffmpeg_checker.py       # FFmpeg algılama, doğrulama ve yönlendirme
│
├── ui/
│   ├── __init__.py
│   ├── app.py                  # CustomTkinter ana pencere ve sayfa düzeni
│   ├── styles.py               # Modern Cyber/Slate Dark Mode renk ve font paleti
│   └── components/
│       ├── __init__.py
│       ├── video_card.py       # Video küçük resmi, başlık ve kalite seçim kartı
│       ├── progress_widget.py  # Canlı ilerleme çubuğu, hız, ETA ve iptal butonu
│       └── history_list.py     # İndirme geçmişi, oynatma ve klasörde açma
│
└── utils/
    ├── __init__.py
    ├── helpers.py              # Boyut/hız biçimlendirme, dosya gezgini açma
    └── history_manager.py      # JSON tabanlı indirme geçmişi kalıcılığı
```

---

## ⚙️ 3. Kurulum ve Çalıştırma

### Adım 1: Bağımlılıkları Yükleyin
PowerShell veya Komut Satırında proje dizinindeyken:
```powershell
pip install -r requirements.txt
```

### Adım 2: Uygulamayı Başlatın
```powershell
python main.py
```

---

## 🎥 4. FFmpeg Hakkında

Uygulama, `imageio-ffmpeg` kütüphanesini içerdiğinden dolayı **harici bir kuruluma gerek kalmadan** doğrudan çalışır.

İsteğe bağlı olarak sistem geneline kurmak isterseniz:
- **Windows (Winget):** `winget install Gyan.FFmpeg`
- **Manuel:** [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/) adresinden indirip `ffmpeg.exe` dosyasını doğrudan proje klasörüne bırakabilirsiniz.

---

## 📦 5. Tek Başına Çalışan Windows `.exe` Derleme (PyInstaller)

Uygulamayı Python yüklü olmayan herhangi bir Windows bilgisayarda çalıştırmak üzere tek bir `.exe` dosyasına dönüştürmek için:

```powershell
python build_exe.py
```

Bu script CustomTkinter temalarını, yt-dlp motorunu ve FFmpeg binary'sini otomatik olarak derleyerek `dist/ApexTube_8K_Downloader.exe` dosyasını üretecektir.
