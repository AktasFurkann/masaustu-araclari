"""
ApexTube 8K Video Downloader - yt-dlp ve FFmpeg İndirme Motoru
"""
import os
import sys
import threading
import glob
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Callable, Optional, Dict, Any, Tuple
import yt_dlp
from yt_dlp.downloader import external as _yt_external
from yt_dlp.utils import download_range_func

from utils.helpers import format_bytes, format_speed, format_seconds, sanitize_filename, clean_playlist_params
from core.ffmpeg_checker import FFmpegChecker


class DownloadCancelledException(Exception):
    pass


# yt-dlp, klip modunda FFmpeg'i kendi içinde başlatıp bekliyor ve süreç nesnesini dışarı vermiyor.
# İptal edilebilmesi için başlatılan süreçleri, başlatan thread'e göre kaydediyoruz.
_active_procs: Dict[int, list] = {}
_procs_lock = threading.Lock()


class _TrackedPopen(_yt_external.Popen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        with _procs_lock:
            _active_procs.setdefault(threading.get_ident(), []).append(self)


_yt_external.Popen = _TrackedPopen


# H.264 seçeneği için: önce en yüksek çözünürlük, aynı çözünürlükte YouTube'un hazır H.264 (avc1)
# akışı. 1080p ve altında dönüştürmeye gerek kalmaz; 4K'da avc1 olmadığı için çözünürlük düşmez.
H264_FORMAT_SORT = ['res', 'fps', 'proto', 'vcodec:h264']


def build_format_selection(resolution_label: str, output_format: str) -> tuple:
    is_audio_only = "MP3" in output_format or "Yalnızca Ses" in resolution_label
    is_h264_wallpaper = "H.264" in output_format

    if is_audio_only:
        format_str = 'bestaudio/best'
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]
        merge_format = None
        ext_suffix = "mp3"
    else:
        postprocessors = []
        merge_format = 'mkv' if "MKV" in output_format else 'mp4'
        ext_suffix = merge_format

        height_limit = None
        if "8K" in resolution_label or "4320p" in resolution_label:
            height_limit = 4320
        elif "4K" in resolution_label or "2160p" in resolution_label:
            height_limit = 2160
        elif "2K" in resolution_label or "1440p" in resolution_label:
            height_limit = 1440
        elif "1080p" in resolution_label:
            height_limit = 1080
        elif "720p" in resolution_label:
            height_limit = 720
        elif "480p" in resolution_label:
            height_limit = 480
        elif "360p" in resolution_label:
            height_limit = 360
        elif "240p" in resolution_label:
            height_limit = 240
        elif "144p" in resolution_label:
            height_limit = 144

        if height_limit:
            if merge_format == 'mp4':
                format_str = (
                    f'bestvideo[height<={height_limit}][ext=mp4]+bestaudio[ext=m4a]/'
                    f'bestvideo[height<={height_limit}]+bestaudio/'
                    f'best[height<={height_limit}]/best'
                )
            else:
                format_str = f'bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}]/best'
        else:
            if merge_format == 'mp4':
                format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
            else:
                format_str = 'bestvideo+bestaudio/best'

    return format_str, merge_format, postprocessors, ext_suffix, is_h264_wallpaper


class VideoDownloader:
    """
    yt-dlp ve FFmpeg entegrasyonu:
    - 4K/8K tam indirme veya belirli bir zaman aralığını (klip) hızlı indirme
    - İstenirse H.264'e dönüştürme (YouTube'un hazır H.264 akışı yoksa)
    """

    def __init__(
        self,
        url: str,
        download_dir: str,
        resolution_label: str = "En Yüksek Kalite (Otomatik 4K/8K)",
        output_format: str = "MP4 (Orijinal AV1 / VP9 - Küçük Boyut, Önerilen)",
        time_range: Optional[Tuple[float, float]] = None,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None
    ):
        self.url = clean_playlist_params(url)  # Playlist parametrelerini temizle
        self.download_dir = os.path.abspath(download_dir)
        self.resolution_label = resolution_label
        self.output_format = output_format
        self.time_range = time_range  # (start_sec, end_sec)

        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        self.on_cancel = on_cancel

        self._is_cancelled = False
        self._thread: Optional[threading.Thread] = None
        self._downloaded_file_path: Optional[str] = None
        self._final_info: Optional[Dict[str, Any]] = None
        self._clip_monitor_stop = threading.Event()

    def start(self) -> None:
        self._is_cancelled = False
        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._is_cancelled = True
        self._clip_monitor_stop.set()
        if self._thread is None:
            return
        with _procs_lock:
            procs = list(_active_procs.get(self._thread.ident, []))
        for proc in procs:
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _determine_format_selection(self) -> tuple:
        return build_format_selection(self.resolution_label, self.output_format)

    def _progress_hook(self, d: Dict[str, Any]) -> None:
        if self._is_cancelled:
            raise DownloadCancelledException("İndirme iptal edildi.")

        status = d.get('status')
        if status == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0

            percent = round((downloaded / total) * 100, 1) if total > 0 else 0.0

            filename = os.path.basename(d.get('filename', ''))
            is_audio_stream = "audio" in filename.lower() or ".f" in filename.lower()
            current_stream_note = "Ses Akışı İndiriliyor..." if is_audio_stream else "Video Akışı İndiriliyor..."

            payload = {
                'percent': percent,
                'speed': speed,
                'speed_str': format_speed(speed),
                'eta': eta,
                'eta_str': format_seconds(eta),
                'downloaded_bytes': downloaded,
                'downloaded_str': format_bytes(downloaded),
                'total_bytes': total,
                'total_str': format_bytes(total),
                'status_text': f"{current_stream_note} ({percent}%)",
                'is_muxing': False
            }

            if self.on_progress:
                self.on_progress(payload)

        elif status == 'finished':
            self._clip_monitor_stop.set()
            fn = d.get('filename')
            if fn and not self._downloaded_file_path:
                self._downloaded_file_path = fn

            if self.on_progress:
                self.on_progress({
                    'percent': 100.0,
                    'speed_str': "-- MB/s",
                    'eta_str': "00:00",
                    'status_text': "İndirme bitti, birleştiriliyor...",
                    'is_muxing': True
                })

    def _postprocessor_hook(self, d: Dict[str, Any]) -> None:
        if self._is_cancelled:
            raise DownloadCancelledException("İndirme iptal edildi.")

        status = d.get('status')
        if status == 'started':
            if self.on_progress:
                self.on_progress({
                    'percent': 100.0,
                    'status_text': "FFmpeg ile birleştiriliyor...",
                    'is_muxing': True
                })
        elif status == 'finished':
            info = d.get('info_dict', {})
            filepath = info.get('filepath') or d.get('filepath')
            if filepath:
                self._downloaded_file_path = filepath

    @staticmethod
    def _read_ffmpeg_progress(path: str) -> Dict[str, str]:
        try:
            with open(path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - 2048))
                tail = f.read().decode('utf-8', errors='ignore')
        except OSError:
            return {}
        stats: Dict[str, str] = {}
        for line in tail.splitlines():
            key, sep, value = line.partition('=')
            if sep:
                stats[key.strip()] = value.strip()
        return stats

    def _monitor_clip_progress(self, progress_file: str, clip_duration: float) -> None:
        started = time.time()
        encoding_started = False
        while not self._clip_monitor_stop.wait(0.5):
            elapsed = time.time() - started
            stats = self._read_ffmpeg_progress(progress_file)

            try:
                out_sec = int(stats.get('out_time_us', '')) / 1_000_000
            except ValueError:
                out_sec = 0.0
            try:
                speed = float(stats.get('speed', '').rstrip('x'))
            except ValueError:
                speed = 0.0
            try:
                size = int(stats.get('total_size', ''))
            except ValueError:
                size = 0

            if out_sec <= 0:
                if encoding_started:
                    continue
                payload = {
                    'percent': 0.0,
                    'status_text': f"Klip hazırlanıyor... (geçen süre {format_seconds(elapsed)})",
                    'speed_str': "-- MB/s",
                    'eta_str': "--:--",
                    'is_muxing': False,
                }
            else:
                encoding_started = True
                fraction = min(out_sec / clip_duration, 0.999)
                percent = round(fraction * 100, 1)
                eta = (clip_duration - out_sec) / speed if speed > 0 and out_sec >= 1 else None
                payload = {
                    'percent': percent,
                    'status_text': f"Klip kesiliyor ve kodlanıyor... ({percent}%)",
                    'speed_str': f"{speed:.2f}x" if speed > 0 else "--",
                    'eta_str': format_seconds(eta) if eta is not None else "--:--",
                    'downloaded_str': format_bytes(size) if size else "--",
                    'total_str': f"~{format_bytes(size / fraction)}" if size and fraction > 0.05 else "--",
                    'is_muxing': False,
                }

            if self.on_progress and not self._clip_monitor_stop.is_set():
                self.on_progress(payload)

    @staticmethod
    def _is_forbidden_error(err: Exception) -> bool:
        msg = str(err)
        # 3436169992 = FFmpeg AVERROR_HTTP_FORBIDDEN (0xCCCFCB08)
        return '403' in msg or '3436169992' in msg

    def _attempt_download(self, ydl_opts: dict) -> dict:
        last_err: Optional[Exception] = None
        for attempt in range(2):
            if attempt > 0:
                self._notify_retry("YouTube erişimi reddetti, tekrar deneniyor...")
                self._downloaded_file_path = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(self.url, download=True)
            except Exception as err:
                if self._is_cancelled or not self._is_forbidden_error(err):
                    raise
                last_err = err

        raise RuntimeError(
            "YouTube indirme isteğini reddetti (HTTP 403).\n"
            "Genellikle yt-dlp sürümü eskidiğinde olur; programın güncel sürümüyle tekrar deneyin.\n\n"
            f"Detay: {last_err}"
        )

    def _notify_retry(self, message: str) -> None:
        if self.on_progress:
            self.on_progress({
                'percent': 0.0,
                'status_text': message,
                'is_muxing': False
            })

    def _find_actual_downloaded_file(self, target_dir: str, title: str, ext: str) -> Optional[str]:
        if self._downloaded_file_path and os.path.isfile(self._downloaded_file_path):
            return os.path.abspath(self._downloaded_file_path)

        if self._downloaded_file_path:
            base_no_ext = os.path.splitext(self._downloaded_file_path)[0]
            alt_path = f"{base_no_ext}.{ext}"
            if os.path.isfile(alt_path):
                return os.path.abspath(alt_path)

        try:
            pattern = os.path.join(target_dir, f"*.{ext}")
            files = glob.glob(pattern)
            if files:
                latest_file = max(files, key=os.path.getmtime)
                return os.path.abspath(latest_file)
        except Exception:
            pass

        return None

    def _convert_to_h264_wallpaper_compatible(self, ffmpeg_path: str, input_file: str) -> str:
        if not input_file or not os.path.isfile(input_file):
            return input_file

        probe_cmd = [ffmpeg_path, '-i', input_file]
        probe = subprocess.run(probe_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        err_out = probe.stderr.decode('utf-8', errors='ignore')

        if "Video: h264" in err_out:
            return input_file

        if self.on_progress:
            self.on_progress({
                'percent': 100.0,
                'status_text': "H.264'e dönüştürülüyor (bu kalitede YouTube H.264 sunmuyor)...",
                'is_muxing': True
            })

        dir_name = os.path.dirname(input_file)
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        temp_output = os.path.join(dir_name, f"{base_name}_h264_tmp.mp4")

        cmd = [
            ffmpeg_path, '-y',
            '-i', input_file,
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'copy',
            temp_output
        ]

        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if ret.returncode == 0 and os.path.isfile(temp_output):
            try:
                os.remove(input_file)
                os.rename(temp_output, input_file)
                return input_file
            except Exception:
                return temp_output

        return input_file

    def _run_download(self) -> None:
        try:
            ffmpeg_path = FFmpegChecker.get_ffmpeg_path()
            if not ffmpeg_path:
                raise RuntimeError("FFmpeg bulunamadı!")

            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            # PATH ortam değişkenine ffmpeg dizinini ekle (yt-dlp download_ranges için zorunlu)
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

            os.makedirs(self.download_dir, exist_ok=True)

            format_str, merge_format, postprocessors, ext_suffix, is_h264_wallpaper = self._determine_format_selection()

            # Zaman aralığı şablonu (örn klip indiriliyorsa dosya adında belirtilsin)
            range_tag = ""
            if self.time_range:
                s, e = self.time_range
                range_tag = f" [{format_seconds(s).replace(':', '.')}-{format_seconds(e).replace(':', '.')}]"

            # Farklı kalitelerin aynı dosya adına düşüp "zaten indirilmiş" sayılmaması için
            # indirilen akışın gerçek yüksekliği (ses dosyalarında boş) dosya adına eklenir.
            if is_h264_wallpaper and ext_suffix == 'mp4':
                quality_tag = '%(height& [{}p H.264]|)s'
            else:
                quality_tag = '%(height& [{}p]|)s'

            out_template = os.path.join(self.download_dir, f'%(title).90s{quality_tag}{range_tag}.%(ext)s')

            ydl_opts = {
                'format': format_str,
                'outtmpl': out_template,
                'windowsfilenames': True,
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'ffmpeg_location': ffmpeg_path,
                'progress_hooks': [self._progress_hook],
                'postprocessor_hooks': [self._postprocessor_hook],
                'noplaylist': True,
                'fixup': 'warn',
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 5,
                'postprocessor_args': {
                    'FFmpegVideoConvertor': ['-strict', '-2'],
                    'FFmpegMerger': ['-strict', '-2'],
                },
            }

            progress_file = None
            if self.time_range:
                start_sec, end_sec = self.time_range
                ydl_opts['download_ranges'] = download_range_func(None, [(start_sec, end_sec)])
                ydl_opts['force_keyframes_at_cuts'] = True

                progress_file = os.path.join(tempfile.gettempdir(), f"apextube_progress_{uuid.uuid4().hex}.txt")
                ydl_opts['external_downloader_args'] = {'ffmpeg_o': ['-progress', progress_file, '-nostats']}
                threading.Thread(
                    target=self._monitor_clip_progress,
                    args=(progress_file, max(end_sec - start_sec, 0.1)),
                    daemon=True,
                ).start()

            if merge_format:
                ydl_opts['merge_output_format'] = merge_format
            if is_h264_wallpaper and ext_suffix == 'mp4':
                ydl_opts['format_sort'] = H264_FORMAT_SORT
            if postprocessors:
                ydl_opts['postprocessors'] = postprocessors

            try:
                info = self._attempt_download(ydl_opts)
            finally:
                self._clip_monitor_stop.set()
                if progress_file:
                    try:
                        os.remove(progress_file)
                    except OSError:
                        pass
            self._final_info = info

            title = info.get('title', 'Video')
            final_path = self._find_actual_downloaded_file(self.download_dir, title, ext_suffix)

            if not final_path:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_tmp:
                    prep = ydl_tmp.prepare_filename(info)
                if merge_format:
                    prep = os.path.splitext(prep)[0] + f".{merge_format}"
                if os.path.exists(prep):
                    final_path = os.path.abspath(prep)
                else:
                    final_path = os.path.join(self.download_dir, f"{sanitize_filename(title)}.{ext_suffix}")

            if is_h264_wallpaper and ext_suffix == 'mp4':
                final_path = self._convert_to_h264_wallpaper_compatible(ffmpeg_path, final_path)

            file_size = os.path.getsize(final_path) if os.path.isfile(final_path) else None

            duration_info = format_seconds(info.get('duration', 0))
            if self.time_range:
                s, e = self.time_range
                duration_info = f"{format_seconds(s)} - {format_seconds(e)} (Klip)"

            result_data = {
                'title': title,
                'file_path': final_path,
                'download_dir': self.download_dir,
                'file_size': file_size,
                'file_size_str': format_bytes(file_size),
                'resolution': self.resolution_label,
                'format': ext_suffix,
                'duration': duration_info,
                'thumbnail_url': info.get('thumbnail'),
                'url': self.url
            }

            if self.on_complete:
                self.on_complete(result_data)

        except DownloadCancelledException:
            if self.on_cancel:
                self.on_cancel()
        except Exception as e:
            if self._is_cancelled:
                if self.on_cancel:
                    self.on_cancel()
            else:
                error_msg = str(e)
                if self.on_error:
                    self.on_error(error_msg)
        finally:
            with _procs_lock:
                procs = _active_procs.pop(threading.get_ident(), [])
            if self._is_cancelled:
                self._remove_partial_outputs(procs)

    @staticmethod
    def _remove_partial_outputs(procs: list) -> None:
        for proc in procs:
            try:
                proc.wait(timeout=5)
                out = str(proc.args[-1])
                if out.startswith('file:'):
                    out = out[len('file:'):]
                if out.endswith('.part') and os.path.isfile(out):
                    os.remove(out)
            except Exception:
                pass
