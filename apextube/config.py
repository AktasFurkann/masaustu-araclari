"""
ApexTube 8K Video Downloader - Konfigürasyon ve Ayarlar
"""
import os
import sys
from pathlib import Path

# Uygulama Bilgileri
APP_NAME = "ApexTube 8K Downloader"
APP_VERSION = "1.0.0"  # yayinla.ps1 tarafından güncellenir
APP_AUTHOR = "Furkan"

# Güncellemelerin yayınlandığı GitHub deposu (Releases)
UPDATE_REPO = "AktasFurkann/masaustu-araclari"

# Pencere Boyutları
WINDOW_WIDTH = 980
WINDOW_HEIGHT = 740
MIN_WINDOW_WIDTH = 880
MIN_WINDOW_HEIGHT = 650

# Dizin Yolları
BASE_DIR = Path(__file__).resolve().parent

if sys.platform == "win32":
    APP_DATA_DIR = Path(os.environ.get("APPDATA", BASE_DIR)) / "ApexTube"
else:
    APP_DATA_DIR = Path.home() / ".apextube"

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Geçmiş Dosyası
HISTORY_FILE = APP_DATA_DIR / "download_history.json"
SETTINGS_FILE = APP_DATA_DIR / "settings.json"

# Varsayılan İndirme Klasörü
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

# İlk eleman varsayılandır. Duvar kağıdı uygulaması LibVLC'ye geçtiği için AV1'i oynatabiliyor.
OUTPUT_FORMATS = [
    "MP4 (Orijinal AV1 / VP9 - Küçük Boyut, Önerilen)",
    "MP4 (H.264 - Eski Cihazlarla Tam Uyumlu)",
    "MKV (Kayıpsız / Orijinal)",
    "MP3 (Yalnızca Ses - 320 kbps)"
]
