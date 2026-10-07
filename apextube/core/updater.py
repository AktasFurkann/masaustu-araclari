"""
GitHub Releases üzerinden güncelleme kontrolü, kurulum dosyasını indirme ve sessiz kurulum.
"""
import os
import re
import subprocess
import sys
import tempfile
from typing import Callable, Optional, Dict, Any, Tuple

import requests

from config import APP_VERSION, UPDATE_REPO

_LATEST_RELEASE_API = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "ApexTube-Updater"}


def _parse_version(text: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def can_self_update() -> bool:
    """Yalnızca derlenmiş (.exe) sürüm kendini güncelleyebilir; kaynak koddan çalışırken değil."""
    return bool(getattr(sys, "frozen", False))


def check_for_update() -> Optional[Dict[str, Any]]:
    """Daha yeni bir sürüm varsa {'version', 'url', 'size'} döner, yoksa None."""
    resp = requests.get(_LATEST_RELEASE_API, headers=_HEADERS, timeout=10)
    if resp.status_code == 404:  # henüz hiç sürüm yayınlanmamış
        return None
    resp.raise_for_status()
    data = resp.json()

    latest = (data.get("tag_name") or "").lstrip("vV")
    if not latest or _parse_version(latest) <= _parse_version(APP_VERSION):
        return None

    asset = next((a for a in data.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
    if not asset:
        return None
    return {"version": latest, "url": asset["browser_download_url"], "size": asset.get("size") or 0}


def download_installer(update: Dict[str, Any], on_progress: Optional[Callable[[int, int], None]] = None) -> str:
    path = os.path.join(tempfile.gettempdir(), f"MasaustuAraclari-Setup-{update['version']}.exe")
    with requests.get(update["url"], headers={"User-Agent": _HEADERS["User-Agent"]}, stream=True, timeout=30) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length") or update.get("size") or 0)
        done = 0
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total)
    return path


def run_installer(path: str) -> None:
    """Kurulumu sessiz modda başlatır. Kurulum, açık programları kapatıp günceller ve yeniden açar."""
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RESTART=apextube"],
                     creationflags=flags, close_fds=True)
