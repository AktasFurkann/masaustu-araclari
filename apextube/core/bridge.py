"""
ApexTube 8K Video Downloader - Tarayıcı Eklentisi Köprüsü

Tarayıcı eklentisinin yakaladığı video bağlantılarını yerel bir HTTP uç noktasından alır.
Yalnızca 127.0.0.1 üzerinde dinler ve yalnızca tarayıcı eklentilerinden gelen istekleri kabul eder;
böylece ziyaret edilen bir web sayfası ApexTube'a indirme başlatamaz.
"""
import json
import shutil
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional

from config import APP_VERSION, BASE_DIR, BRIDGE_PORT, EXTENSION_DIR
from utils.helpers import is_supported_url

_EXTENSION_ORIGINS = ("chrome-extension://", "moz-extension://", "extension://")
_MAX_BODY = 64 * 1024
# Akışı sunan sunucunun, isteğin oynatıcı sayfasından geldiğini görmesi için aktarılan başlıklar.
# Çerez ve oturum bilgileri bilerek aktarılmaz.
_FORWARDED_HEADERS = {"referer": "Referer", "origin": "Origin", "user_agent": "User-Agent"}


class _ExclusiveServer(ThreadingHTTPServer):
    # HTTPServer varsayılan olarak SO_REUSEADDR açar; Windows'ta bu, ikinci bir sürecin aynı portu
    # sessizce paylaşmasına izin verir ve isteklerin hangi sürece gideceği belirsizleşir.
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _clean_text(value: Any, limit: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.replace("\r", " ").replace("\n", " ").strip()
    return value[:limit] or None


def parse_link_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Eklentiden gelen JSON'u doğrular; geçersizse None döner."""
    url = _clean_text(payload.get("url"), 4096)
    if not url or not is_supported_url(url):
        return None

    headers = {}
    for key, header in _FORWARDED_HEADERS.items():
        value = _clean_text(payload.get(key), 2048)
        if value:
            headers[header] = value

    return {
        "url": url,
        "http_headers": headers,
        "title": _clean_text(payload.get("title"), 200),
        "page_url": _clean_text(payload.get("page_url"), 4096),
    }


class LinkBridge:
    """Eklentiden gelen bağlantıları on_link geri çağrısına ileten yerel sunucu."""

    def __init__(self, on_link: Callable[[Dict[str, Any]], None], port: int = BRIDGE_PORT):
        self.on_link = on_link
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None

    def start(self) -> bool:
        """Sunucuyu başlatır. Port doluysa (ör. ikinci bir ApexTube açıksa) False döner."""
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _reply(self, status: int, body: Dict[str, Any]) -> None:
                data = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _from_extension(self) -> bool:
                return (self.headers.get("Origin") or "").startswith(_EXTENSION_ORIGINS)

            def do_GET(self) -> None:
                # Chrome, eklentinin GET isteklerine Origin eklemiyor; ping yalnızca sürümü bildirdiği
                # için Origin'siz isteğe de cevap verilir, web sayfası kökenli olanlar yine reddedilir.
                origin = self.headers.get("Origin")
                if self.path != "/ping" or (origin and not self._from_extension()):
                    self._reply(403, {"ok": False})
                    return
                self._reply(200, {"ok": True, "app": "ApexTube", "version": APP_VERSION})

            def do_POST(self) -> None:
                if self.path != "/add" or not self._from_extension():
                    self._reply(403, {"ok": False})
                    return
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                    if not 0 < length <= _MAX_BODY:
                        raise ValueError
                    link = parse_link_payload(json.loads(self.rfile.read(length).decode("utf-8")))
                except (ValueError, UnicodeDecodeError, AttributeError):
                    link = None
                if not link:
                    self._reply(400, {"ok": False, "error": "Geçersiz bağlantı"})
                    return
                bridge.on_link(link)
                self._reply(200, {"ok": True})

        try:
            self._server = _ExclusiveServer(("127.0.0.1", self.port), Handler)
        except OSError:
            return False
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return True

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


def install_extension_files() -> str:
    """
    Eklenti dosyalarını kalıcı bir klasöre kopyalar ve yolunu döndürür.
    Tek dosyalık exe'de paketlenen dosyalar geçici bir klasörde durduğu için Chrome'a doğrudan gösterilemez.
    """
    source = BASE_DIR / "browser_extension"
    if source.resolve() != EXTENSION_DIR.resolve():
        shutil.copytree(source, EXTENSION_DIR, dirs_exist_ok=True)
    return str(EXTENSION_DIR)
