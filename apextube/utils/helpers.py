"""
ApexTube 8K Video Downloader - Yardımcı Fonksiyonlar
"""
import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Optional, Union

# YouTube URL Doğrulama Deseni (Standart, Kısaltılmış youtu.be, Shorts, Canlı Yayınlar ve Playlist Parametreleri)
YOUTUBE_URL_REGEX = re.compile(
    r'^(https?://)?(www\.|m\.)?(youtube\.com|youtu\.be)/'
    r'(watch\?v=|embed/|v/|shorts/|live/)?([a-zA-Z0-9_-]{11})'
    r'([&?].*)?$',
    re.IGNORECASE
)


def is_valid_youtube_url(url: str) -> bool:
    """Verilen metnin geçerli bir YouTube URL'si olup olmadığını denetler."""
    if not url or not isinstance(url, str):
        return False
    clean_url = url.strip()
    return bool(YOUTUBE_URL_REGEX.search(clean_url))


def extract_video_id(url: str) -> Optional[str]:
    """YouTube URL'sinden 11 karakterlik video ID'sini çıkarır."""
    if not url:
        return None
    match = YOUTUBE_URL_REGEX.search(url.strip())
    if match:
        return match.group(5)
    return None


def clean_playlist_params(url: str) -> str:
    """
    YouTube URL'sinden playlist ve index parametrelerini temizler.
    Böylece sadece tek video indirilir, playlist tamamı değil.
    Örn: https://www.youtube.com/watch?v=XXX&list=YYY&index=3
    ->   https://www.youtube.com/watch?v=XXX
    """
    if not url:
        return url
    clean = url.strip()
    video_id = extract_video_id(clean)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return clean


def format_bytes(bytes_num: Optional[Union[int, float]]) -> str:
    """Bayt miktarını insan tarafından okunabilir birime dönüştürür (KB, MB, GB)."""
    if bytes_num is None or bytes_num < 0:
        return "Bilinmiyor"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}" if unit in ['MB', 'GB'] else f"{int(bytes_num)} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} PB"


def format_speed(bytes_per_sec: Optional[Union[int, float]]) -> str:
    """İndirme hızını MB/s veya KB/s cinsinden biçimlendirir."""
    if bytes_per_sec is None or bytes_per_sec <= 0:
        return "-- MB/s"
    mb = bytes_per_sec / (1024 * 1024)
    if mb >= 1.0:
        return f"{mb:.2f} MB/s"
    kb = bytes_per_sec / 1024
    return f"{kb:.1f} KB/s"


def format_seconds(seconds: Optional[Union[int, float]]) -> str:
    """Saniye cinsinden süreyi HH:MM:SS veya MM:SS biçimine dönüştürür."""
    if seconds is None or seconds < 0:
        return "--:--"
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_time_to_seconds(time_str: str) -> Optional[float]:
    """
    Kullanıcının girdiği zaman metnini saniyeye dönüştürür.
    Desteklenen formatlar:
    '01:30' -> 90 sn
    '01:15:30' -> 4530 sn
    '45' -> 45 sn
    '5m' -> 300 sn
    """
    if not time_str or not isinstance(time_str, str):
        return None
    s = time_str.strip().lower()

    if s.endswith('m'):
        try:
            return float(s[:-1]) * 60.0
        except ValueError:
            return None
    if s.endswith('h'):
        try:
            return float(s[:-1]) * 3600.0
        except ValueError:
            return None
    if s.endswith('s'):
        try:
            return float(s[:-1])
        except ValueError:
            return None

    parts = s.split(':')
    try:
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60.0 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])
    except (ValueError, TypeError):
        pass
    return None


def sanitize_filename(filename: str) -> str:
    """Dosya adındaki işletim sistemi için geçersiz karakterleri temizler."""
    if not filename:
        return "video"
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    sanitized = sanitized.encode('ascii', 'ignore').decode('ascii')
    sanitized = sanitized.strip().strip(".")
    return sanitized if sanitized else "video"


def open_file_in_explorer(file_path: Union[str, Path], fallback_dir: Optional[str] = None) -> bool:
    """
    Windows Dosya Gezgini'nde belirtilen dosyayı seçili olarak açar.
    Dosya yoksa dosyanın bulunduğu klasörü veya fallback_dir'i açar.
    """
    try:
        clean_path = str(file_path).strip() if file_path else ""
        norm_path = os.path.normpath(clean_path) if clean_path else ""

        if sys.platform == "win32":
            if norm_path and os.path.isfile(norm_path):
                subprocess.run(f'explorer /select,"{norm_path}"', shell=True)
                return True

            folder_to_open = None
            if norm_path and os.path.isdir(norm_path):
                folder_to_open = norm_path
            elif norm_path and os.path.isdir(os.path.dirname(norm_path)):
                folder_to_open = os.path.dirname(norm_path)
            elif fallback_dir and os.path.isdir(fallback_dir):
                folder_to_open = fallback_dir

            if folder_to_open:
                os.startfile(folder_to_open)
                return True

        else:
            target = norm_path if os.path.exists(norm_path) else (fallback_dir or ".")
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([opener, str(target)], check=False)
            return True

    except Exception as e:
        print(f"Gezgin açılırken hata: {e}")
    return False


def open_directory(dir_path: Union[str, Path]) -> bool:
    """Belirtilen dizini doğrudan dosya gezgininde açar."""
    try:
        target = str(dir_path).strip()
        if os.path.isdir(target):
            if sys.platform == "win32":
                os.startfile(target)
            elif sys.platform == "darwin":
                subprocess.run(["open", target], check=False)
            else:
                subprocess.run(["xdg-open", target], check=False)
            return True
    except Exception as e:
        print(f"Dizin açılamadı: {e}")
    return False


def play_media_file(file_path: Union[str, Path]) -> bool:
    """Belirtilen medya dosyasını sistemin varsayılan oynatıcısında çalıştırır."""
    try:
        clean_path = str(file_path).strip() if file_path else ""
        norm_path = os.path.normpath(clean_path)
        if not os.path.isfile(norm_path):
            return False
            
        if sys.platform == "win32":
            os.startfile(norm_path)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", norm_path], check=False)
            return True
        else:
            subprocess.run(["xdg-open", norm_path], check=False)
            return True
    except Exception as e:
        print(f"Medya dosyası oynatılamadı: {e}")
    return False
