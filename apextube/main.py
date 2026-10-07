"""
ApexTube 8K Video Downloader - Masaüstü Uygulaması Başlatıcı (Main Entrypoint)
"""
import sys
import os

# Çalışma dizinini sys.path'e ekle
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Windows yüksek çözünürlüklü ekran (Hi-DPI) ölçekleme desteği
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

from ui.app import ModernDownloaderApp


def main():
    """Uygulamayı başlatır ve olay döngüsünü (main loop) çalıştırır."""
    try:
        app = ModernDownloaderApp()
        app.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Kritik Uygulama Hatası: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
