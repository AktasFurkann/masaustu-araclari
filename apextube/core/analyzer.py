"""
ApexTube 8K Video Downloader - Video Analiz Modülü
"""
import copy
import html
import io
import re
import requests
from urllib.parse import unquote, urlparse
from typing import Dict, Any, List, Mapping, Optional
from PIL import Image
import yt_dlp

from config import BEST_QUALITY_LABEL, OUTPUT_FORMATS
from utils.helpers import (
    is_supported_url, first_entry, friendly_error, format_seconds, format_bytes, clean_playlist_params,
    get_header
)
from core.ffmpeg_checker import FFmpegChecker
from core.downloader import build_format_selection, H264_FORMAT_SORT


class VideoAnalyzer:
    """Video URL'sini analiz ederek başlık, küçük resim, süre ve çözünürlükleri çıkarır."""

    @classmethod
    def analyze_url(cls, url: str, http_headers: Optional[Dict[str, str]] = None,
                    title_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Videoyu indirmeden analiz eder ve 4K/8K dahil tüm mevcut çözünürlükleri çıkarır.
        YouTube dışında yt-dlp'nin desteklediği siteler ve doğrudan video bağlantıları da çalışır.

        http_headers: Tarayıcı eklentisinden gelen Referer/Origin/User-Agent; bazı sunucular akışı
        yalnızca oynatıcı sayfasından istenmiş gibi görünürse verir.
        title_hint: Doğrudan akış bağlantılarında başlık "master" gibi anlamsız olduğu için sayfa başlığı.
        """
        if not is_supported_url(url):
            raise ValueError("Geçersiz bağlantı! Lütfen http(s) ile başlayan bir video adresi girin.")

        # Playlist parametrelerini temizle - sadece tek video analiz edilsin
        clean_url = clean_playlist_params(url)

        ffmpeg_path = FFmpegChecker.get_ffmpeg_path()

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
            'noplaylist': True,  # Playlist'ten sadece tek videoyu al
            'playlist_items': '1',  # Birden çok video içeren sayfalarda yalnızca ilki
            # Cevap vermeyen sunucuda tek istek uzun süre ve defalarca beklenmesin
            'socket_timeout': 15,
            'extractor_retries': 1,
        }
        if http_headers:
            ydl_opts['http_headers'] = http_headers
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = first_entry(ydl.extract_info(clean_url, download=False))
            except Exception as e:
                raise RuntimeError(f"Video bilgileri alınırken hata oluştu: {friendly_error(e)}")

        if not info:
            raise RuntimeError("Video bilgileri okunamadı.")

        # Temel Video Bilgileri
        title = info.get('title', 'Bilinmeyen Video')
        channel = (info.get('uploader') or info.get('channel')
                   or info.get('webpage_url_domain') or 'Bilinmeyen Kaynak')

        # Doğrudan akış bağlantısı (yt-dlp'nin genel ayrıştırıcısı): sayfa adı ve sitesi daha anlamlı
        custom_title = None
        if info.get('extractor_key') == 'Generic':
            referer = get_header(http_headers, 'Referer') or ''
            # Öncelik eklentinin bildirdiği sayfa başlığında; yoksa Referer sayfasından türetilir.
            custom_title = title_hint or (page_title_from_referer(referer, clean_url, http_headers)
                                          if referer else None)
            if custom_title:
                title = custom_title
            referer_host = urlparse(referer).netloc
            if referer_host:
                channel = referer_host
        duration_sec = info.get('duration') or 0
        duration_str = format_seconds(duration_sec)
        view_count = info.get('view_count', 0)
        thumbnail_url = info.get('thumbnail')
        upload_date = info.get('upload_date')
        if upload_date and len(upload_date) == 8:
            formatted_date = f"{upload_date[6:8]}.{upload_date[4:6]}.{upload_date[0:4]}"
        else:
            formatted_date = "Bilinmiyor"

        # Mevcut formatları analiz et
        raw_formats = info.get('formats', [])
        height_map = {}  # {height: {'fps': int, 'hdr': bool}}
        has_hdr = False
        max_fps = 30

        for f in raw_formats:
            height = f.get('height')
            vcodec = f.get('vcodec', '')
            if height and vcodec != 'none':
                fps = int(f.get('fps') or 30)
                dynamic_range = (f.get('dynamic_range') or '').upper()
                is_hdr = dynamic_range == 'HDR'
                if is_hdr:
                    has_hdr = True
                if fps > max_fps:
                    max_fps = fps

                if height not in height_map:
                    height_map[height] = {'fps': fps, 'hdr': is_hdr}
                else:
                    if fps > height_map[height]['fps']:
                        height_map[height]['fps'] = fps
                    if is_hdr:
                        height_map[height]['hdr'] = True

        # Kullanıcıya sunulacak çözünürlük seçeneklerini filtrele ve oluştur
        resolutions_list = [BEST_QUALITY_LABEL]

        # Çözünürlük kademeleri ve etiketleme
        resolution_targets = [
            (4320, "8K Ultra HD (4320p)"),
            (2160, "4K Ultra HD (2160p)"),
            (1440, "2K Quad HD (1440p)"),
            (1080, "Full HD (1080p)"),
            (720, "HD (720p)"),
            (480, "Standart (480p)"),
            (360, "Düşük (360p)"),
            (240, "Düşük (240p)"),
            (144, "En Düşük (144p)")
        ]

        for target_h, base_label in resolution_targets:
            # Toleranslı arama (örn. 2160 civarı bir yükseklik var mı)
            matching_h = None
            for h in height_map.keys():
                if abs(h - target_h) <= 20:
                    matching_h = h
                    break

            if matching_h:
                info_h = height_map[matching_h]
                fps_val = info_h['fps']
                hdr_val = info_h['hdr']

                # 60fps ve HDR etiketlerini ekle
                extra_tags = []
                if fps_val >= 48:
                    extra_tags.append(f"{fps_val}fps")
                if hdr_val:
                    extra_tags.append("HDR")

                if extra_tags:
                    # Örn: "4K Ultra HD (2160p 60fps HDR)"
                    tag_str = " ".join(extra_tags)
                    label = base_label.replace(")", f" {tag_str})")
                else:
                    label = base_label

                resolutions_list.append(label)

        # Yalnızca ses seçeneğini her zaman ekle
        resolutions_list.append("Yalnızca Ses (MP3 320 kbps)")

        available_heights = list(height_map.keys())
        max_h = max(available_heights) if available_heights else 1080

        size_estimates = cls._estimate_sizes(ydl, info, resolutions_list)

        return {
            "id": info.get('id'),
            "url": clean_url,
            "http_headers": http_headers or {},
            "title": title,
            "custom_title": custom_title,
            "channel": channel,
            "duration_sec": duration_sec,
            "duration_str": duration_str,
            "view_count": view_count,
            "thumbnail_url": thumbnail_url,
            "upload_date": formatted_date,
            "has_hdr": has_hdr,
            "max_fps": max_fps,
            "available_resolutions": resolutions_list,
            "max_height": max_h,
            "size_estimates": size_estimates,
        }

    @staticmethod
    def _estimate_sizes(ydl: yt_dlp.YoutubeDL, info: Dict[str, Any], resolutions: List[str]) -> Dict[tuple, Dict[str, Any]]:
        """
        Her (kalite, format) seçimi için indirmede seçilecek akışları yt-dlp'nin kendi
        seçicisiyle belirler ve sitenin bildirdiği akış boyutlarını toplar.
        """
        formats = info.get('formats') or []
        duration = info.get('duration') or 0
        estimates: Dict[tuple, Dict[str, Any]] = {}

        # İndirici H.264 seçeneğinde farklı sıralama kullanıyor; aynı sıralamayla seçmek için.
        h264_sorted = {'formats': copy.deepcopy(formats), '_format_sort_fields': info.get('_format_sort_fields')}
        with yt_dlp.YoutubeDL({'quiet': True, 'format_sort': H264_FORMAT_SORT}) as sorter:
            sorter.sort_formats(h264_sorted)

        def select(fmt_list: list, format_str: str):
            try:
                selected = ydl._select_formats(fmt_list, ydl.build_format_selector(format_str))
            except Exception:
                return None, {}
            if not selected:
                return None, {}
            parts = selected[0].get('requested_formats') or [selected[0]]
            sizes = [p.get('filesize') or p.get('filesize_approx') for p in parts]
            video = next((p for p in parts if p.get('vcodec') not in (None, 'none')), {})
            return (sum(sizes) if all(sizes) else None), video

        for res in resolutions:
            for fmt in OUTPUT_FORMATS:
                format_str, _, _, ext_suffix, is_h264 = build_format_selection(res, fmt)

                if ext_suffix == 'mp3':
                    estimates[(res, fmt)] = {
                        'bytes': duration * 320_000 / 8 if duration else None,
                        'reencode': False,
                    }
                    continue

                # Klip çıktısı her zaman libx264 ile yeniden kodlanır; çarpanlar varsayılan
                # (AV1/VP9) kaynağa göre ölçüldüğü için klip tahmini o kaynaktan yapılır.
                clip_bytes, video = select(formats, format_str)
                size = clip_bytes
                if is_h264:
                    size, video = select(h264_sorted['formats'], format_str)

                estimates[(res, fmt)] = {
                    'bytes': size,
                    'clip_bytes': clip_bytes,
                    'reencode': is_h264 and not (video.get('vcodec') or '').startswith('avc1'),
                    'height': video.get('height') or 0,
                }

        return estimates


    @classmethod
    def fetch_thumbnail_image(cls, thumbnail_url: str, target_size=(320, 180)) -> Optional[Image.Image]:
        """Verilen URL'den küçük resmi indirip PIL Image nesnesine dönüştürür."""
        if not thumbnail_url:
            return None
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            resp = requests.get(thumbnail_url, headers=headers, timeout=8)
            if resp.status_code == 200:
                image_data = io.BytesIO(resp.content)
                img = Image.open(image_data)
                img = img.convert("RGBA")
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                return img
        except Exception as e:
            print(f"Thumbnail yüklenemedi: {e}")
        return None


# Kaynak akışa göre yeniden kodlanmış çıktının boyut oranı (4K ve 1080p için ölçüldü).
# Klip: force_keyframes_at_cuts ile libx264 crf 23. Tam H.264 dönüşüm: libx264 crf 18.
_CLIP_FACTORS = ((2160, 1.2), (1440, 1.45), (0, 1.7))
_H264_FACTORS = ((2160, 1.8), (1440, 2.15), (0, 2.5))


def _factor_for(height: int, table: tuple) -> float:
    return next(f for min_h, f in table if height >= min_h)


def estimate_output_bytes(entry: Dict[str, Any], duration_sec: float,
                          clip_sec: Optional[float] = None) -> Optional[float]:
    """Analizde hesaplanan kaynak boyutundan, indirilecek dosyanın tahmini boyutunu döndürür."""
    is_clip = clip_sec is not None and duration_sec > 0
    size = (entry.get('clip_bytes') or entry.get('bytes')) if is_clip else entry.get('bytes')
    if not size:
        return None
    height = entry.get('height', 0)

    if is_clip:
        size = size * min(clip_sec, duration_sec) / duration_sec
        if height:
            size *= _factor_for(height, _CLIP_FACTORS)
    elif entry.get('reencode'):
        size *= _factor_for(height, _H264_FACTORS)
    return size


# --- Doğrudan akışlarda Referer sayfasından video adı ---

_PAGE_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
_PAGE_READ_LIMIT = 512 * 1024  # başlık etiketleri sayfanın başında olur; tamamını indirmeye gerek yok
_PAGE_TIMEOUT_SEC = 8
_TITLE_META_KEYS = ('og:title', 'twitter:title')
_META_TAG_RE = re.compile(r'<meta\b[^>]*>', re.IGNORECASE)
_ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))')
_TITLE_TAG_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)
_CHARSET_RE = re.compile(rb'<meta[^>]+charset=["\']?([\w-]+)', re.IGNORECASE)
# Adres yolunda video adı taşımayan, sık görülen kısımlar
_GENERIC_SEGMENTS = {'izle', 'watch', 'video', 'videos', 'embed', 'player', 'play', 'v', 'e',
                     'index', 'view', 'film', 'dizi', 'bolum', 'episode', 'stream', 'live'}


def page_title_from_referer(referer: str, stream_url: str,
                            http_headers: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """
    Videonun oynatıldığı sayfanın başlığını döndürür (og:title > twitter:title > <title>).
    Sayfa açılamaz veya başlık bulunamazsa adres yolundan bir ad türetir; o da olmazsa None.

    Cookie yalnızca sayfa, akışla aynı sunucudaysa gönderilir: kullanıcının yazdığı çerez genelde
    video sunucusuna aittir ve başka bir siteye iletilmemelidir.
    """
    if not is_supported_url(referer):
        return None
    return _fetch_page_title(referer, stream_url, http_headers) or _title_from_url_path(referer)


def _fetch_page_title(referer: str, stream_url: str,
                      http_headers: Optional[Mapping[str, str]]) -> Optional[str]:
    headers = {'User-Agent': get_header(http_headers, 'User-Agent') or _PAGE_UA}
    cookie = get_header(http_headers, 'Cookie')
    if cookie and urlparse(referer).hostname == urlparse(stream_url).hostname:
        headers['Cookie'] = cookie

    try:
        with requests.get(referer, headers=headers, timeout=_PAGE_TIMEOUT_SEC, stream=True) as resp:
            if resp.status_code != 200 or 'html' not in resp.headers.get('Content-Type', '').lower():
                return None
            body = b''
            for chunk in resp.iter_content(16 * 1024):
                body += chunk
                if len(body) >= _PAGE_READ_LIMIT:
                    break
            # requests, charset bildirilmemiş metinde ISO-8859-1 varsayar; Türkçe harfler bozulmasın diye
            # yalnızca açıkça bildirilen kodlama kullanılır, yoksa sayfadaki <meta charset> veya UTF-8.
            declared = 'charset=' in resp.headers.get('Content-Type', '').lower()
            encoding = resp.encoding if declared else None
    except requests.RequestException:
        return None

    if not encoding:
        match = _CHARSET_RE.search(body[:4096])
        encoding = match.group(1).decode('ascii', 'ignore') if match else 'utf-8'
    try:
        text = body.decode(encoding, errors='replace')
    except LookupError:
        text = body.decode('utf-8', errors='replace')

    return _extract_title(text)


def _extract_title(page_html: str) -> Optional[str]:
    meta_titles: Dict[str, str] = {}
    for tag in _META_TAG_RE.findall(page_html):
        attrs = {m.group(1).lower(): next(g for g in m.groups()[1:] if g is not None)
                 for m in _ATTR_RE.finditer(tag)}
        key = (attrs.get('property') or attrs.get('name') or '').lower()
        if key in _TITLE_META_KEYS and attrs.get('content'):
            meta_titles.setdefault(key, attrs['content'])

    candidates = [meta_titles.get(k) for k in _TITLE_META_KEYS]
    title_tag = _TITLE_TAG_RE.search(page_html)
    candidates.append(title_tag.group(1) if title_tag else None)

    for raw in candidates:
        if raw:
            title = ' '.join(html.unescape(raw).split())[:200]
            if title:
                return title
    return None


def _title_from_url_path(url: str) -> Optional[str]:
    """/izle/harika-film-2024/123 -> 'harika film 2024'. Anlamlı kısım yoksa None."""
    segments = [unquote(s) for s in urlparse(url).path.split('/') if s]
    for segment in reversed(segments):
        segment = re.sub(r'\.(html?|php|aspx?|jsp)$', '', segment, flags=re.IGNORECASE)
        words = ' '.join(re.split(r'[-_+.]+', segment)).strip()
        looks_like_id = ' ' not in words and any(ch.isdigit() for ch in words)  # ör. dQw4w9WgXcQ
        if (len(words) < 3 or looks_like_id or words.lower() in _GENERIC_SEGMENTS
                or not any(ch.isalpha() for ch in words)):
            continue
        return words[:200]
    return None
