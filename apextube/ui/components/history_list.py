"""
ApexTube 8K Video Downloader - İndirme Geçmişi Bileşeni
"""
import os
import customtkinter as ctk
from typing import Callable, Optional
from pathlib import Path

from ui.styles import (
    COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BORDER, COLOR_ACCENT,
    COLOR_SUCCESS, COLOR_DANGER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL
)
from utils.history_manager import HistoryManager
from utils.helpers import open_file_in_explorer, play_media_file, format_bytes, open_directory


class HistoryListView(ctk.CTkScrollableFrame):
    """
    Kullanıcının daha önce indirdiği videoları listeleyen, doğrudan oynatma
    ve dosya gezgininde klasörü açma kısayolları sunan geçmiş bileşeni.
    """

    def __init__(self, master, history_manager: HistoryManager, **kwargs):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )
        self.history_manager = history_manager
        self.refresh()

    def refresh(self) -> None:
        """Geçmiş listesini baştan okur ve görsel kartları yeniler."""
        for widget in self.winfo_children():
            widget.destroy()

        entries = self.history_manager.get_all()

        if not entries:
            empty_frame = ctk.CTkFrame(self, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, pady=40)

            empty_lbl = ctk.CTkLabel(
                empty_frame,
                text="📥 Henüz indirilmiş video bulunmuyor",
                font=FONT_SUBTITLE,
                text_color=COLOR_TEXT_MUTED
            )
            empty_lbl.pack(pady=(0, 4))

            hint_lbl = ctk.CTkLabel(
                empty_frame,
                text="Yukarıdan bir YouTube bağlantısı yapıştırıp indirmeye başlayabilirsiniz.",
                font=FONT_BODY,
                text_color=COLOR_TEXT_MUTED
            )
            hint_lbl.pack()
            return

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 10))

        count_lbl = ctk.CTkLabel(
            toolbar,
            text=f"Son İndirilenler ({len(entries)})",
            font=FONT_SUBTITLE,
            text_color=COLOR_TEXT_PRIMARY
        )
        count_lbl.pack(side="left")

        clear_btn = ctk.CTkButton(
            toolbar,
            text="Geçmişi Temizle",
            font=FONT_SMALL,
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_DANGER,
            text_color=COLOR_TEXT_SECONDARY,
            border_width=1,
            border_color=COLOR_BORDER,
            width=100,
            height=28,
            command=self._clear_history
        )
        clear_btn.pack(side="right")

        for item in entries:
            self._create_entry_card(item)

    def _create_entry_card(self, item: dict) -> None:
        """Tek bir indirme geçmişi kaydı için UI kartı oluşturur."""
        card = ctk.CTkFrame(
            self,
            fg_color=COLOR_BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_BORDER
        )
        card.pack(fill="x", pady=4, padx=2)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)

        left_box = ctk.CTkFrame(card, fg_color="transparent")
        left_box.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        title = item.get("title", "İsimsiz Video")
        if len(title) > 60:
            title = title[:57] + "..."

        title_lbl = ctk.CTkLabel(
            left_box,
            text=title,
            font=FONT_BODY_BOLD,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        title_lbl.pack(anchor="w")

        meta_parts = []
        if item.get("resolution"):
            meta_parts.append(f"🎞 {item['resolution']}")
        if item.get("format"):
            meta_parts.append(f"📦 {item['format'].upper()}")
        if item.get("file_size"):
            meta_parts.append(f"💾 {format_bytes(item['file_size'])}")
        if item.get("date_str"):
            meta_parts.append(f"🕒 {item['date_str']}")

        meta_lbl = ctk.CTkLabel(
            left_box,
            text="  •  ".join(meta_parts),
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        meta_lbl.pack(anchor="w", pady=(2, 0))

        # Sağ Taraf: Aksiyon Butonları
        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.grid(row=0, column=1, padx=14, pady=10, sticky="e")

        file_path = item.get("file_path", "")
        download_dir = item.get("download_dir") or (os.path.dirname(file_path) if file_path else "")
        file_exists = os.path.isfile(file_path) if file_path else False

        # 1. Oynat Butonu
        play_btn = ctk.CTkButton(
            btn_box,
            text="▶ Oynat",
            font=FONT_SMALL,
            fg_color=COLOR_ACCENT if file_exists else COLOR_BG_INPUT,
            hover_color=COLOR_SUCCESS,
            text_color="#FFFFFF" if file_exists else COLOR_TEXT_MUTED,
            state="normal" if file_exists else "disabled",
            width=65,
            height=28,
            command=lambda p=file_path: play_media_file(p)
        )
        play_btn.pack(side="left", padx=3)

        # 2. Klasörde Göster Butonu (Dosyayı seçili açar, yoksa klasörü açar)
        folder_btn = ctk.CTkButton(
            btn_box,
            text="📁 Klasör",
            font=FONT_SMALL,
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_BORDER,
            width=70,
            height=28,
            command=lambda p=file_path, d=download_dir: open_file_in_explorer(p, fallback_dir=d)
        )
        folder_btn.pack(side="left", padx=3)

        # 3. Sil Butonu
        del_btn = ctk.CTkButton(
            btn_box,
            text="✕",
            font=FONT_BODY_BOLD,
            fg_color="transparent",
            hover_color=COLOR_DANGER,
            text_color=COLOR_TEXT_MUTED,
            width=28,
            height=28,
            command=lambda eid=item.get("id"): self._delete_entry(eid)
        )
        del_btn.pack(side="left", padx=(3, 0))

    def _delete_entry(self, entry_id: int) -> None:
        if entry_id and self.history_manager.remove_entry(entry_id):
            self.refresh()

    def _clear_history(self) -> None:
        self.history_manager.clear_all()
        self.refresh()
