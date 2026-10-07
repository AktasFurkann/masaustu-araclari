"""
ApexTube 8K Video Downloader - İndirme Geçmişi Yöneticisi
"""
import json
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import HISTORY_FILE


class HistoryManager:
    """İndirilen videoların geçmiş kaydını JSON tabanlı olarak yönetir."""

    def __init__(self, history_file: Path = HISTORY_FILE):
        self.history_file = Path(history_file)
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Geçmiş dosyasının ve dizininin var olduğundan emin olur."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.history_file.exists():
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Geçmiş dosyası oluşturulamadı: {e}")

    def get_all(self) -> List[Dict[str, Any]]:
        """Tüm indirme geçmişini en son indirilenden başlayarak döndürür."""
        try:
            if not self.history_file.exists():
                return []
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return sorted(data, key=lambda x: x.get("timestamp", 0), reverse=True)
        except Exception as e:
            print(f"Geçmiş okunamadı: {e}")
        return []

    def add_entry(
        self,
        title: str,
        file_path: str,
        resolution: str,
        format_ext: str,
        file_size: Optional[int] = None,
        duration: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        video_url: Optional[str] = None,
        download_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Yeni bir indirme kaydı ekler veya günceller."""
        entries = self.get_all()
        entries = [e for e in entries if e.get("file_path") != file_path]

        folder = download_dir or (os.path.dirname(file_path) if file_path else "")

        new_entry = {
            "id": int(time.time() * 1000),
            "title": title,
            "file_path": file_path,
            "download_dir": folder,
            "resolution": resolution,
            "format": format_ext,
            "file_size": file_size,
            "duration": duration or "--:--",
            "thumbnail_url": thumbnail_url,
            "video_url": video_url,
            "timestamp": time.time(),
            "date_str": time.strftime("%d.%m.%Y %H:%M")
        }

        entries.insert(0, new_entry)
        entries = entries[:100]

        self._save(entries)
        return new_entry

    def remove_entry(self, entry_id: int) -> bool:
        """Belirtilen ID'ye sahip kaydı siler."""
        entries = self.get_all()
        initial_len = len(entries)
        entries = [e for e in entries if e.get("id") != entry_id]
        if len(entries) != initial_len:
            self._save(entries)
            return True
        return False

    def clear_all(self) -> None:
        """Tüm indirme geçmişini sıfırlar."""
        self._save([])

    def _save(self, entries: List[Dict[str, Any]]) -> None:
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Geçmiş kaydedilemedi: {e}")
