"""
ApexTube 8K Video Downloader - HLS (.m3u8) İndirici

Bir .m3u8 akışını FFmpeg ile, verilen HTTP başlıklarını (Referer, User-Agent, Cookie vb.) kullanarak
tek bir .mp4 dosyasına kaydeder. Akış yeniden kodlanmaz (-c copy), yalnızca kapsayıcı değiştirilir.

FFmpeg'in HLS okuyucusu bu başlıkları yalnızca ana listeye değil, alt listelere ve tüm parça (segment)
isteklerine de uygular.

Örnek:
    from core.hls_downloader import download_hls_stream

    download_hls_stream(
        "https://ornek.com/video/master.m3u8",
        r"C:\\Users\\furkan\\Downloads\\video.mp4",
        {"Referer": "https://ornek.com/izle/123", "User-Agent": "Mozilla/5.0 ...", "Cookie": "oturum=abc"},
        on_progress=lambda d: print(d["status_text"]),
    )

Komut satırından denemek için:
    python -m core.hls_downloader URL cikti.mp4 -H "Referer: https://ornek.com/" -H "Cookie: a=b"
"""
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Mapping, Optional
from urllib.parse import urlparse

from yt_dlp.utils import sanitize_filename as yt_sanitize_filename

from core.ffmpeg_checker import FFmpegChecker
from utils.helpers import format_bytes, format_seconds, format_speed, parse_http_headers, validate_http_header

ProgressCallback = Callable[[Dict[str, Any]], None]

# FFmpeg'in kendi seçenekleri olan başlıklar; diğerleri -headers ile tek blok halinde gönderilir.
_DEDICATED_OPTIONS = {"user-agent": "-user_agent", "referer": "-referer"}
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
# Bağlantı bu kadar mikro saniye boyunca veri vermezse FFmpeg hata ile çıkar (takılı kalmasın diye).
_RW_TIMEOUT_US = 30_000_000
_STDERR_TAIL_LINES = 40


class HlsDownloadError(RuntimeError):
    """FFmpeg indirmeyi tamamlayamadı."""


class HlsDownloadCancelled(Exception):
    """İndirme cancel_event ile iptal edildi."""


def build_header_args(custom_headers: Optional[Mapping[str, str]]) -> List[str]:
    """
    Başlık sözlüğünü FFmpeg girdi seçeneklerine çevirir (bu seçenekler -i'den önce gelmelidir).

    User-Agent ve Referer FFmpeg'in kendi seçenekleriyle, geri kalanlar (Cookie, Origin, özel başlıklar)
    -headers ile verilir. Satır sonu içeren değerler reddedilir; aksi halde bir değer, araya kendi
    başlık satırını sokabilirdi.
    """
    args: List[str] = []
    extra_lines: List[str] = []

    for name, value in (custom_headers or {}).items():
        if value is None:
            continue
        name = str(name).strip()
        value = str(value).strip()
        validate_http_header(name, value)
        if not value:
            continue

        option = _DEDICATED_OPTIONS.get(name.lower())
        if option:
            args += [option, value]
        else:
            extra_lines.append(f"{name}: {value}\r\n")

    if extra_lines:
        args += ["-headers", "".join(extra_lines)]
    return args


def build_ffmpeg_command(
    ffmpeg_path: str,
    m3u8_url: str,
    output_file_path: str,
    custom_headers: Optional[Mapping[str, str]] = None,
) -> List[str]:
    return [
        ffmpeg_path,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-loglevel", "info",          # "Duration:" satırı için gerekli
        "-nostats",
        "-progress", "pipe:1",        # ilerleme stdout'a anahtar=değer satırları olarak yazılır
        "-rw_timeout", str(_RW_TIMEOUT_US),
        *build_header_args(custom_headers),
        "-i", m3u8_url,
        "-c", "copy",
        "-movflags", "+faststart",
        "-f", "mp4",                  # geçici dosyanın uzantısı .part olduğu için biçim açıkça verilir
        output_file_path,
    ]


def download_hls_stream(
    m3u8_url: str,
    output_file_path: str,
    custom_headers: Optional[Mapping[str, str]] = None,
    on_progress: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    ffmpeg_path: Optional[str] = None,
) -> str:
    """
    m3u8_url'deki HLS akışını output_file_path'e .mp4 olarak indirir ve dosyanın tam yolunu döndürür.

    custom_headers: {"Referer": ..., "User-Agent": ..., "Cookie": ..., "<Başka>": ...}
    on_progress:    VideoDownloader ile aynı yapıda sözlük alır (percent, status_text, speed_str, eta_str,
                    downloaded_str, total_str, is_muxing). Verilmezse ilerleme konsola yazılır.
                    Canlı yayınlarda toplam süre bilinmediği için 'percent' None olur.
    cancel_event:   set() edildiğinde FFmpeg durdurulur, yarım dosya silinir ve HlsDownloadCancelled atılır.

    Bu fonksiyon indirme bitene kadar bekler; arayüzden çağrılacaksa ayrı bir thread'de çalıştırılmalıdır.
    """
    if not m3u8_url.lower().startswith(("http://", "https://")):
        raise ValueError("Yalnızca http(s) adresleri desteklenir.")

    ffmpeg_path = ffmpeg_path or FFmpegChecker.get_ffmpeg_path()
    if not ffmpeg_path:
        raise HlsDownloadError("FFmpeg bulunamadı!")

    output_file_path = os.path.abspath(output_file_path)
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    # Yarım kalan indirme hedef dosyanın üzerine yazmasın; başarıyla bitince yeniden adlandırılır.
    part_path = output_file_path + ".part"

    report = on_progress or _print_progress
    cmd = build_ffmpeg_command(ffmpeg_path, m3u8_url, part_path, custom_headers)

    report({'percent': 0.0, 'status_text': "Akışa bağlanılıyor...", 'is_muxing': False})

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    tracker = _ProgressTracker(report)
    stderr_tail: deque = deque(maxlen=_STDERR_TAIL_LINES)
    readers = [
        threading.Thread(target=_read_stdout, args=(proc.stdout, tracker), daemon=True),
        threading.Thread(target=_read_stderr, args=(proc.stderr, tracker, stderr_tail), daemon=True),
    ]
    for t in readers:
        t.start()

    cancelled = False
    try:
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.wait(0.25):
                cancelled = True
                proc.kill()
                break
            elif cancel_event is None:
                time.sleep(0.25)
        proc.wait()
    except BaseException:
        # Örn. KeyboardInterrupt: FFmpeg arka planda çalışmaya devam etmesin.
        proc.kill()
        proc.wait()
        _remove_quietly(part_path)
        raise
    finally:
        for t in readers:
            t.join(timeout=5)

    if cancelled:
        _remove_quietly(part_path)
        raise HlsDownloadCancelled("İndirme iptal edildi.")

    if proc.returncode != 0 or not os.path.isfile(part_path):
        _remove_quietly(part_path)
        raise HlsDownloadError(_describe_failure(proc.returncode, list(stderr_tail)))

    os.replace(part_path, output_file_path)
    size = os.path.getsize(output_file_path)
    report({
        'percent': 100.0,
        'status_text': "İndirme tamamlandı.",
        'speed_str': "-- MB/s",
        'eta_str': "00:00",
        'downloaded_str': format_bytes(size),
        'total_str': format_bytes(size),
        'is_muxing': False,
    })
    return output_file_path


# İstenen adla da çağrılabilsin diye; Python kodunda download_hls_stream tercih edilir.
downloadHlsStream = download_hls_stream


def is_hls_url(url: str) -> bool:
    """Bağlantı doğrudan bir .m3u8 oynatma listesini mi gösteriyor (sorgu parametreleri hariç)."""
    try:
        return urlparse(url).path.lower().endswith(".m3u8")
    except ValueError:
        return False


class HlsDownloader:
    """
    download_hls_stream'i ayrı bir thread'de çalıştırır. Arayüzün VideoDownloader için kullandığı
    start / cancel / is_alive ve on_progress / on_complete / on_error / on_cancel yapısının aynısını sunar.
    Geri çağrılar arka plan thread'inden çağrılır; arayüz bunları after() ile ana thread'e aktarmalıdır.
    """

    def __init__(
        self,
        url: str,
        download_dir: str,
        title: str,
        http_headers: Optional[Mapping[str, str]] = None,
        result_info: Optional[Dict[str, Any]] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        self.url = url
        self.download_dir = os.path.abspath(download_dir)
        self.title = title or "Video"
        self.http_headers = dict(http_headers or {})
        # Tamamlanma sözlüğüne eklenecek bilgiler (çözünürlük etiketi, süre, küçük resim vb.)
        self.result_info = dict(result_info or {})
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        self.on_cancel = on_cancel

        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _output_path(self) -> str:
        base = yt_sanitize_filename(self.title)[:90].strip() or "video"
        path = os.path.join(self.download_dir, f"{base}.mp4")
        n = 2
        while os.path.exists(path) or os.path.exists(path + ".part"):
            path = os.path.join(self.download_dir, f"{base} ({n}).mp4")
            n += 1
        return path

    def _run(self) -> None:
        try:
            path = download_hls_stream(
                self.url,
                self._output_path(),
                self.http_headers,
                on_progress=self.on_progress or (lambda _d: None),
                cancel_event=self._cancel_event,
            )
        except HlsDownloadCancelled:
            if self.on_cancel:
                self.on_cancel()
            return
        except Exception as err:
            if self._cancel_event.is_set():
                if self.on_cancel:
                    self.on_cancel()
            elif self.on_error:
                self.on_error(str(err))
            return

        size = os.path.getsize(path)
        if self.on_complete:
            self.on_complete({
                **self.result_info,
                'title': self.title,
                'file_path': path,
                'download_dir': self.download_dir,
                'file_size': size,
                'file_size_str': format_bytes(size),
                'format': 'mp4',
                'url': self.url,
            })


class _ProgressTracker:
    """stderr'den gelen toplam süreyi ve stdout'tan gelen -progress bloklarını birleştirip bildirir."""

    def __init__(self, report: ProgressCallback):
        self._report = report
        self._lock = threading.Lock()
        self._duration: Optional[float] = None
        self._started = time.monotonic()

    def set_duration(self, seconds: float) -> None:
        with self._lock:
            if self._duration is None and seconds > 0:
                self._duration = seconds

    def on_block(self, stats: Dict[str, str]) -> None:
        with self._lock:
            duration = self._duration

        out_sec = _to_float(stats.get("out_time_us")) / 1_000_000
        size = int(_to_float(stats.get("total_size")))
        speed_x = _to_float(stats.get("speed", "").rstrip("x"))
        elapsed = max(time.monotonic() - self._started, 0.001)
        byte_rate = size / elapsed

        if stats.get("progress") == "end":
            # Son blok; tamamlandı bildirimi dosya yeniden adlandırıldıktan sonra yapılır.
            return

        if duration:
            fraction = min(out_sec / duration, 0.999)
            percent: Optional[float] = round(fraction * 100, 1)
            eta = (duration - out_sec) / speed_x if speed_x > 0 else None
            total_str = f"~{format_bytes(size / fraction)}" if size and fraction > 0.05 else "--"
            status = f"HLS akışı indiriliyor... ({percent}%)"
        else:
            # Canlı yayın veya süresi bildirilmeyen liste: yalnızca indirilen süre gösterilir.
            percent, eta, total_str = None, None, "--"
            status = f"HLS akışı indiriliyor... ({format_seconds(out_sec)} kaydedildi)"

        self._report({
            'percent': percent,
            'status_text': status,
            'out_time_sec': out_sec,
            'duration_sec': duration,
            'speed': byte_rate,
            'speed_str': format_speed(byte_rate) if size else "-- MB/s",
            'speed_x': speed_x,
            'eta': eta,
            'eta_str': format_seconds(eta) if eta is not None else "--:--",
            'downloaded_bytes': size,
            'downloaded_str': format_bytes(size) if size else "--",
            'total_str': total_str,
            'is_muxing': False,
        })


def _read_stdout(stream, tracker: _ProgressTracker) -> None:
    # -progress çıktısı: her blok "anahtar=değer" satırlarından oluşur ve "progress=continue|end" ile biter.
    block: Dict[str, str] = {}
    for raw in iter(stream.readline, b""):
        key, sep, value = raw.decode("utf-8", errors="ignore").strip().partition("=")
        if not sep:
            continue
        block[key] = value
        if key == "progress":
            tracker.on_block(block)
            block = {}
    stream.close()


def _read_stderr(stream, tracker: _ProgressTracker, tail: deque) -> None:
    for raw in iter(stream.readline, b""):
        line = raw.decode("utf-8", errors="ignore").rstrip()
        if not line:
            continue
        tail.append(line)
        match = _DURATION_RE.search(line)
        if match:
            h, m, s = match.groups()
            tracker.set_duration(int(h) * 3600 + int(m) * 60 + float(s))
    stream.close()


def _describe_failure(returncode: int, stderr_lines: List[str]) -> str:
    text = "\n".join(stderr_lines)
    lowered = text.lower()
    if "403" in text or "forbidden" in lowered:
        reason = ("Sunucu isteği reddetti (HTTP 403). Referer, Cookie veya User-Agent değerleri eksik ya da "
                  "süresi dolmuş olabilir; bağlantıyı sayfadan yeniden alıp tekrar deneyin.")
    elif "401" in text or "unauthorized" in lowered:
        reason = "Sunucu kimlik doğrulaması istiyor (HTTP 401)."
    elif "404" in text or "not found" in lowered:
        reason = "Akış bulunamadı (HTTP 404). Bağlantının süresi dolmuş olabilir."
    elif "timed out" in lowered or "timeout" in lowered:
        reason = "Sunucu belirtilen sürede cevap vermedi."
    else:
        reason = f"FFmpeg hata ile çıktı (kod {returncode})."

    detail = "\n".join(stderr_lines[-8:])
    return f"{reason}\n\nDetay:\n{detail}" if detail else reason


def _print_progress(data: Dict[str, Any]) -> None:
    line = (f"\r{data.get('status_text', '')}  {data.get('downloaded_str', '--')}  "
            f"{data.get('speed_str', '')}  ETA {data.get('eta_str', '--:--')}")
    print(line.ljust(100), end="", flush=True)
    if data.get('percent') == 100.0:
        print()


def _to_float(value: Optional[str]) -> float:
    try:
        return float(value) if value not in (None, "", "N/A") else 0.0
    except ValueError:
        return 0.0


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HLS (.m3u8) akışını FFmpeg ile .mp4'e indirir.")
    parser.add_argument("url")
    parser.add_argument("output")
    parser.add_argument("-H", "--header", action="append", default=[], metavar='"Ad: Değer"')
    args = parser.parse_args(argv)

    try:
        headers = parse_http_headers("\n".join(args.header))
    except ValueError as err:
        parser.error(str(err))

    try:
        path = download_hls_stream(args.url, args.output, headers)
    except KeyboardInterrupt:
        print("\nİptal edildi.")
        return 130
    except (HlsDownloadError, ValueError) as err:
        print(f"\n{err}", file=sys.stderr)
        return 1
    print(f"Kaydedildi: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
