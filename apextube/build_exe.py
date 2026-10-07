"""
ApexTube 8K Video Downloader - Tek Tıkla PyInstaller .exe Derleme Scripti
"""
import sys
import os
import subprocess
import shutil
from pathlib import Path


def build(copy_to_desktop: bool = True) -> bool:
    print("==================================================")
    print("  ApexTube 8K Downloader - Windows .exe Derleyici ")
    print("==================================================")

    # 1. PyInstaller kontrolü
    try:
        import PyInstaller
        print(f"[OK] PyInstaller bulundu: v{PyInstaller.__version__}")
    except ImportError:
        print("[!] PyInstaller bulunamadı. Otomatik kuruluyor...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller başarıyla kuruldu.")

    # 2. Çalışma ve çıktı dizinleri
    base_dir = Path(__file__).resolve().parent
    main_file = base_dir / "main.py"
    dist_dir = base_dir / "dist"
    desktop_dir = Path(os.environ.get("USERPROFILE", "C:/Users/furkan")) / "Desktop"

    # 3. PyInstaller Komut Parametreleri
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name=ApexTube_8K_Downloader",
        "--noconsole",                    # Konsol penceresini gizle
        "--onefile",                      # Tek bir bağımsız .exe üret
        "--clean",
        "--collect-all", "customtkinter", # CustomTkinter tema ve font dosyaları
        "--collect-all", "imageio_ffmpeg",# Gömülü FFmpeg binary'si
        "--collect-all", "yt_dlp",        # yt-dlp ayrıştırıcıları
        str(main_file)
    ]

    print("\n[INFO] Derleme işlemi başlatılıyor, bu işlem 1-2 dakika sürebilir...")
    print(f"Komut: {' '.join(cmd)}\n")

    try:
        subprocess.check_call(cmd, cwd=str(base_dir))
        exe_path = dist_dir / "ApexTube_8K_Downloader.exe"
        
        if exe_path.exists():
            print("\n==================================================")
            print("[OK] DERLEME BAŞARIYLA TAMAMLANDI!")
            print(f"[OK] Üretilen .exe: {exe_path}")

            if copy_to_desktop:
                desktop_exe = desktop_dir / "ApexTube 8K Downloader.exe"
                try:
                    shutil.copy2(exe_path, desktop_exe)
                    print(f"[OK] Masaüstüne kopyalandı: {desktop_exe}")
                except Exception as copy_err:
                    print(f"[!] Masaüstüne kopyalanamadı: {copy_err}")

            print("==================================================")
            return True

        print("[!] Derleme bitti ancak .exe dosyası bulunamadı.")
        return False

    except subprocess.CalledProcessError as e:
        print(f"\n[HATA] Derleme sırasında hata oluştu: {e}")
        return False


if __name__ == "__main__":
    # --no-desktop: yayın (yayinla.ps1) sırasında masaüstüne kopyalama yapılmaz
    ok = build(copy_to_desktop="--no-desktop" not in sys.argv)
    sys.exit(0 if ok else 1)
