"""
ApexTube 8K Video Downloader - Video Bilgi, Ayar ve Zaman Aralığı (Klip) Kartı
"""
import customtkinter as ctk
from typing import Dict, Any, Callable, Optional, Tuple
from PIL import Image

from ui.styles import (
    COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BORDER, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED, COLOR_PURPLE,
    COLOR_CYAN, FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_BADGE
)
from config import OUTPUT_FORMATS
from utils.helpers import parse_time_to_seconds, format_seconds, format_bytes
from ui.components.time_entry import TimeEntry
from core.analyzer import estimate_output_bytes


class VideoInfoCard(ctk.CTkFrame):
    """
    Analiz edilen videonun görselini, çözünürlük/format seçimini ve
    10 saatlik gibi uzun videolardan istenen aralığı (00:00 - 05:00) kesip
    indirme panelini sunan modern arayüz kartı.
    """

    def __init__(
        self,
        master,
        video_data: Dict[str, Any],
        thumbnail_img: Optional[Image.Image],
        download_dir: str,
        on_start_download: Callable[[str, str, str, Optional[Tuple[float, float]]], None],
        on_change_folder: Callable[[], None],
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=COLOR_BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDER,
            **kwargs
        )

        self.video_data = video_data
        self.thumbnail_img = thumbnail_img
        self.current_download_dir = download_dir
        self.on_start_download = on_start_download
        self.on_change_folder = on_change_folder

        self.total_duration_sec = video_data.get("duration_sec", 0)

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sol: Thumbnail
        self.thumb_container = ctk.CTkFrame(
            self,
            fg_color=COLOR_BG_INPUT,
            corner_radius=10,
            width=280,
            height=160
        )
        self.thumb_container.grid(row=0, column=0, padx=16, pady=16, sticky="nw")
        self.thumb_container.grid_propagate(False)

        if self.thumbnail_img:
            self.ctk_image = ctk.CTkImage(
                light_image=self.thumbnail_img,
                dark_image=self.thumbnail_img,
                size=(280, 158)
            )
            self.thumb_label = ctk.CTkLabel(self.thumb_container, image=self.ctk_image, text="")
            self.thumb_label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.thumb_label = ctk.CTkLabel(
                self.thumb_container,
                text="[Küçük Resim]",
                font=FONT_BODY,
                text_color=COLOR_TEXT_MUTED
            )
            self.thumb_label.place(relx=0.5, rely=0.5, anchor="center")

        # 2. Sağ: Detaylar ve Kontroller
        self.details_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.details_frame.grid(row=0, column=1, padx=(0, 16), pady=16, sticky="nsew")
        self.details_frame.grid_columnconfigure(0, weight=1)

        # Başlık
        title_text = self.video_data.get("title", "Video Başlığı")
        if len(title_text) > 85:
            title_text = title_text[:82] + "..."

        self.title_label = ctk.CTkLabel(
            self.details_frame,
            text=title_text,
            font=FONT_SUBTITLE,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
            justify="left",
            wraplength=480
        )
        self.title_label.grid(row=0, column=0, sticky="w", pady=(0, 4))

        # Rozetler
        self.badges_frame = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        self.badges_frame.grid(row=1, column=0, sticky="w", pady=(0, 8))

        channel_name = self.video_data.get("channel", "YouTube")
        self.channel_badge = ctk.CTkLabel(
            self.badges_frame,
            text=f"📺 {channel_name}",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            fg_color=COLOR_BG_INPUT,
            corner_radius=6,
            padx=8,
            pady=2
        )
        self.channel_badge.pack(side="left", padx=(0, 8))

        duration_str = self.video_data.get("duration_str", "--:--")
        self.duration_badge = ctk.CTkLabel(
            self.badges_frame,
            text=f"⏱ {duration_str}",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            fg_color=COLOR_BG_INPUT,
            corner_radius=6,
            padx=8,
            pady=2
        )
        self.duration_badge.pack(side="left", padx=(0, 8))

        max_h = self.video_data.get("max_height", 1080)
        badge_text = None
        if max_h >= 4320:
            badge_text = "⚡ 8K ULTRA HD"
        elif max_h >= 2160:
            badge_text = "💎 4K ULTRA HD"
        elif max_h >= 1440:
            badge_text = "✨ 2K QUAD HD"
        elif max_h >= 1080:
            badge_text = "🎬 FULL HD"

        if badge_text:
            self.res_badge = ctk.CTkLabel(
                self.badges_frame,
                text=badge_text,
                font=FONT_BADGE,
                text_color="#FFFFFF",
                fg_color=COLOR_PURPLE,
                corner_radius=6,
                padx=8,
                pady=2
            )
            self.res_badge.pack(side="left", padx=(0, 8))

        # Seçiciler (Çözünürlük & Format)
        self.selectors_frame = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        self.selectors_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.selectors_frame.grid_columnconfigure((0, 1), weight=1)

        self.res_label = ctk.CTkLabel(
            self.selectors_frame,
            text="Kalite / Çözünürlük:",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.res_label.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 2))

        available_res = self.video_data.get("available_resolutions", ["En Yüksek Kalite (Otomatik 4K/8K)"])
        self.res_dropdown = ctk.CTkOptionMenu(
            self.selectors_frame,
            values=available_res,
            font=FONT_BODY,
            fg_color=COLOR_BG_INPUT,
            button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            dropdown_fg_color=COLOR_BG_CARD,
            dropdown_text_color=COLOR_TEXT_PRIMARY,
            height=32,
            command=lambda _: self._update_size_estimate()
        )
        # 4K veya en yüksek olanı öncelikli seç
        self.res_dropdown.set(available_res[1] if len(available_res) > 1 else available_res[0])
        self.res_dropdown.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        self.format_label = ctk.CTkLabel(
            self.selectors_frame,
            text="Çıktı Formatı:",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.format_label.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        self.format_dropdown = ctk.CTkOptionMenu(
            self.selectors_frame,
            values=OUTPUT_FORMATS,
            font=FONT_BODY,
            fg_color=COLOR_BG_INPUT,
            button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            dropdown_fg_color=COLOR_BG_CARD,
            dropdown_text_color=COLOR_TEXT_PRIMARY,
            height=32,
            command=lambda _: self._update_size_estimate()
        )
        self.format_dropdown.set(OUTPUT_FORMATS[0])
        self.format_dropdown.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        self.size_label = ctk.CTkLabel(
            self.selectors_frame,
            text="",
            font=FONT_SMALL,
            text_color=COLOR_CYAN,
            anchor="w",
            justify="left",
            wraplength=480
        )
        self.size_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # 3. YENİ: Zaman Aralığı (Klip Kesme) Alanı
        self.trim_frame = ctk.CTkFrame(
            self.details_frame,
            fg_color=COLOR_BG_INPUT,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER
        )
        self.trim_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.trim_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Checkbox: Aralığı Etkinleştir
        self.trim_var = ctk.BooleanVar(value=False)
        self.trim_checkbox = ctk.CTkCheckBox(
            self.trim_frame,
            text="✂️ Zaman Aralığı Kes (Örn: 10 saatlik videodan sadece 5 dk al)",
            variable=self.trim_var,
            font=FONT_BODY_BOLD,
            text_color=COLOR_TEXT_PRIMARY,
            command=self._toggle_trim_inputs
        )
        self.trim_checkbox.grid(row=0, column=0, columnspan=4, padx=12, pady=(8, 6), sticky="w")

        # Zaman Kutuları ve Kısayol Butonları Konteynırı
        self.trim_inputs_box = ctk.CTkFrame(self.trim_frame, fg_color="transparent")
        self.trim_inputs_box.grid(row=1, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="ew")
        self.trim_inputs_box.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Başlangıç
        self.start_label = ctk.CTkLabel(self.trim_inputs_box, text="Başlangıç:", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED)
        self.start_label.grid(row=0, column=0, sticky="w")
        self.start_entry = TimeEntry(self.trim_inputs_box, initial_value="00:00:00", width=100, height=28)
        self.start_entry.grid(row=1, column=0, sticky="w", padx=(0, 6))

        # Bitiş
        self.end_label = ctk.CTkLabel(self.trim_inputs_box, text="Bitiş:", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED)
        self.end_label.grid(row=0, column=1, sticky="w")
        default_end = "00:05:00"
        if self.total_duration_sec > 0 and self.total_duration_sec < 300:
            default_end = format_seconds(self.total_duration_sec)
        self.end_entry = TimeEntry(self.trim_inputs_box, initial_value=default_end, width=100, height=28)
        self.end_entry.grid(row=1, column=1, sticky="w", padx=(0, 6))

        # Hızlı Butonlar
        quick_box = ctk.CTkFrame(self.trim_inputs_box, fg_color="transparent")
        quick_box.grid(row=1, column=2, columnspan=2, sticky="e")

        btn1 = ctk.CTkButton(
            quick_box, text="1 Dk", width=42, height=26, font=FONT_SMALL,
            fg_color=COLOR_BG_CARD, hover_color=COLOR_BORDER,
            command=lambda: self._set_quick_time(60)
        )
        btn1.pack(side="left", padx=2)

        btn5 = ctk.CTkButton(
            quick_box, text="5 Dk", width=42, height=26, font=FONT_SMALL,
            fg_color=COLOR_BG_CARD, hover_color=COLOR_BORDER,
            command=lambda: self._set_quick_time(300)
        )
        btn5.pack(side="left", padx=2)

        btn10 = ctk.CTkButton(
            quick_box, text="10 Dk", width=46, height=26, font=FONT_SMALL,
            fg_color=COLOR_BG_CARD, hover_color=COLOR_BORDER,
            command=lambda: self._set_quick_time(600)
        )
        btn10.pack(side="left", padx=2)

        btn_all = ctk.CTkButton(
            quick_box, text="Tümü", width=46, height=26, font=FONT_SMALL,
            fg_color=COLOR_BG_CARD, hover_color=COLOR_BORDER,
            command=lambda: self._set_quick_time(self.total_duration_sec)
        )
        btn_all.pack(side="left", padx=2)

        self.start_entry.add_change_callback(self._update_size_estimate)
        self.end_entry.add_change_callback(self._update_size_estimate)

        # Başlangıçta zaman kutularını devre dışı bırak
        self._toggle_trim_inputs()

        # 4. Kayıt Konumu
        self.folder_frame = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        self.folder_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        self.folder_frame.grid_columnconfigure(0, weight=1)
        self.folder_frame.grid_columnconfigure(1, weight=0)

        short_dir = self.current_download_dir
        if len(short_dir) > 55:
            short_dir = "..." + short_dir[-52:]

        self.folder_entry = ctk.CTkEntry(
            self.folder_frame,
            font=FONT_SMALL,
            fg_color=COLOR_BG_INPUT,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_SECONDARY,
            height=30
        )
        self.folder_entry.insert(0, short_dir)
        self.folder_entry.configure(state="disabled")
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.folder_btn = ctk.CTkButton(
            self.folder_frame,
            text="📁 Değiştir",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_BORDER,
            width=90,
            height=30,
            command=self.on_change_folder
        )
        self.folder_btn.grid(row=0, column=1, sticky="e")

        # 5. İndirmeyi Başlat Butonu
        self.start_btn = ctk.CTkButton(
            self.details_frame,
            text="⬇  İNDİRMEYİ BAŞLAT",
            font=FONT_SUBTITLE,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            height=40,
            command=self._handle_start_click
        )
        self.start_btn.grid(row=5, column=0, sticky="ew")

    def _toggle_trim_inputs(self) -> None:
        state = "normal" if self.trim_var.get() else "disabled"
        self.start_entry.configure_state(state)
        self.end_entry.configure_state(state)
        self._update_size_estimate()

    def _update_size_estimate(self) -> None:
        if not hasattr(self, "size_label"):
            return
        entry = self.video_data.get("size_estimates", {}).get(
            (self.res_dropdown.get(), self.format_dropdown.get()), {}
        )
        duration = self.total_duration_sec

        clip_sec = None
        if self.trim_var.get():
            start = self.start_entry.get_seconds()
            end = min(self.end_entry.get_seconds(), duration) if duration else self.end_entry.get_seconds()
            if end <= start:
                self.size_label.configure(text="💾 Tahmini boyut: Bitiş, başlangıçtan sonra olmalı")
                return
            clip_sec = end - start

        size = estimate_output_bytes(entry, duration, clip_sec)
        if size is None:
            self.size_label.configure(text="💾 Tahmini boyut: Bilinmiyor (YouTube bu kalite için boyut bildirmiyor)")
            return

        text = f"💾 Tahmini boyut: ~{format_bytes(size)}"
        if clip_sec is not None:
            full = estimate_output_bytes(entry, duration)
            text += f"  ({format_seconds(clip_sec)} klip"
            text += f", videonun tamamı ~{format_bytes(full)})" if full else ")"
        elif entry.get("reencode"):
            text += "  (H.264'e dönüştürüleceği için orijinal akıştan büyük)"
        self.size_label.configure(text=text)

    def _set_quick_time(self, duration_sec: float) -> None:
        self.trim_var.set(True)
        self._toggle_trim_inputs()
        self.start_entry.set_seconds(0)
        self.end_entry.set_seconds(duration_sec)

    def update_folder_path(self, new_path: str) -> None:
        self.current_download_dir = new_path
        short_dir = new_path
        if len(short_dir) > 55:
            short_dir = "..." + short_dir[-52:]
        self.folder_entry.configure(state="normal")
        self.folder_entry.delete(0, "end")
        self.folder_entry.insert(0, short_dir)
        self.folder_entry.configure(state="disabled")

    def _handle_start_click(self) -> None:
        selected_res = self.res_dropdown.get()
        selected_fmt = self.format_dropdown.get()

        time_range = None
        if self.trim_var.get():
            start_val = self.start_entry.get_seconds()
            end_val = self.end_entry.get_seconds()
            if end_val and end_val > start_val:
                time_range = (start_val, end_val)

        self.on_start_download(selected_res, selected_fmt, self.current_download_dir, time_range)
