"""
ApexTube 8K Video Downloader - FFmpeg Algılama ve Yönetim Modülü
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


class FFmpegChecker:
    """Sistemde veya proje dizininde FFmpeg yürütülebilir dosyasını arar ve durumunu raporlar."""

    @classmethod
    def get_ffmpeg_path(cls) -> Optional[str]:
        """
        FFmpeg çalıştırılabilir dosyasının konumunu sırayla kontrol eder:
        1. Sistem PATH ortam değişkeni
        2. Uygulama/Script dizini veya yerel ./bin/ klasörü
        3. imageio-ffmpeg kütüphanesinin gömülü binary'si
        """
        # 1. Sistem PATH kontrolü
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg

        # 2. Yerel proje / uygulama klasörü kontrolleri
        base_dir = Path(__file__).resolve().parent.parent
        possible_local_paths = [
            base_dir / "ffmpeg.exe",
            base_dir / "bin" / "ffmpeg.exe",
            base_dir / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path(sys.executable).parent / "ffmpeg.exe",
            Path(sys.executable).parent / "Scripts" / "ffmpeg.exe",
        ]

        for p in possible_local_paths:
            if p.is_file() and os.access(str(p), os.X_OK if sys.platform != "win32" else os.F_OK):
                return str(p)

        # 3. imageio-ffmpeg kütüphanesi kontrolü (Python ortamında hazır gelir)
        try:
            import imageio_ffmpeg
            bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            if bundled_ffmpeg and os.path.isfile(bundled_ffmpeg):
                if cls._test_ffmpeg_binary(bundled_ffmpeg):
                    return bundled_ffmpeg
        except Exception:
            pass

        return None

    @staticmethod
    def _test_ffmpeg_binary(path: str) -> bool:
        try:
            result = subprocess.run(
                [path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            return result.returncode == 0
        except Exception:
            return False

    @classmethod
    def verify_ffmpeg(cls) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        FFmpeg'in çalışıp çalışmadığını ve sürümünü test eder.
        Dönüş: (is_available: bool, ffmpeg_path: str, version_info: str)
        """
        path = cls.get_ffmpeg_path()
        if not path:
            return False, None, "FFmpeg sistemde veya paketlerde bulunamadı."

        try:
            # -version parametresi ile kontrol et
            result = subprocess.run(
                [path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if result.returncode == 0:
                first_line = result.stdout.splitlines()[0] if result.stdout else "FFmpeg Algılandı"
                return True, path, first_line
            return False, path, "FFmpeg çalıştırılamadı (Geçersiz dönüş kodu)."
        except Exception as e:
            return False, path, f"FFmpeg çalıştırma hatası: {e}"

    @classmethod
    def get_installation_instructions(cls) -> str:
        """FFmpeg bulunamadığında kullanıcıya gösterilecek Türkçe kurulum rehberi."""
        return (
            "FFmpeg Yüksek Çözünürlüklü (1080p, 4K, 8K) videoları ve sesleri birleştirmek için zorunludur.\n\n"
            "Hızlı Kurulum Yolları:\n"
            "1. Komut Satırından (Windows): 'winget install Gyan.FFmpeg'\n"
            "2. Proje Klasörüne Ekleme: 'ffmpeg.exe' dosyasını bu programın yanına yapıştırabilirsiniz.\n"
            "3. Python Bağımlılığı: 'pip install imageio-ffmpeg' (Program otomatik kullanacaktır)."
        )
