"""
ApexTube 8K Video Downloader - Canlı İlerleme ve İstatistik Bileşeni
"""
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any

from ui.styles import (
    COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BORDER, COLOR_ACCENT,
    COLOR_DANGER, COLOR_SUCCESS, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED, FONT_PERCENT, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD,
    FONT_METRIC, FONT_SMALL
)


class ProgressWidget(ctk.CTkFrame):
    """
    İndirme sürecinde yüzde, hız, kalan süre ve FFmpeg birleştirme durumunu
    canlı olarak yansıtan modern ilerleme çubuğu ve kontrol kartı.
    """

    def __init__(
        self,
        master,
        on_cancel: Callable[[], None],
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

        self.on_cancel = on_cancel
        self._build_ui()

    def _build_ui(self) -> None:
        """İlerleme kartının grid yerleşimini kurar."""
        self.grid_columnconfigure(0, weight=1)

        # 1. Üst Başlık Satırı (Yüzde ve Durum Metni)
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(16, 8), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure(1, weight=0)

        # Sol: Durum Metni
        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text="İndirme Başlatılıyor...",
            font=FONT_SUBTITLE,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, sticky="w")

        # Sağ: Büyük Yüzde
        self.percent_label = ctk.CTkLabel(
            self.header_frame,
            text="0%",
            font=FONT_PERCENT,
            text_color=COLOR_ACCENT,
            anchor="e"
        )
        self.percent_label.grid(row=0, column=1, sticky="e")

        # 2. İlerleme Çubuğu (CTkProgressBar)
        self.progress_bar = ctk.CTkProgressBar(
            self,
            orientation="horizontal",
            height=12,
            corner_radius=6,
            fg_color=COLOR_BG_INPUT,
            progress_color=COLOR_ACCENT
        )
        self.progress_bar.set(0.0)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=(0, 14), sticky="ew")

        # 3. Canlı Metrikler Kartı (Hız, Kalan Süre, Boyut)
        self.metrics_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_INPUT, corner_radius=10)
        self.metrics_frame.grid(row=2, column=0, padx=20, pady=(0, 16), sticky="ew")
        self.metrics_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Metrik 1: Hız
        self.speed_metric = self._create_metric_box(
            self.metrics_frame, col=0, title="İndirme Hızı", value="-- MB/s", icon="⚡"
        )

        # Metrik 2: Kalan Süre
        self.eta_metric = self._create_metric_box(
            self.metrics_frame, col=1, title="Kalan Süre", value="--:--", icon="⏳"
        )

        # Metrik 3: Boyut
        self.size_metric = self._create_metric_box(
            self.metrics_frame, col=2, title="İndirilen / Toplam", value="-- / --", icon="💾"
        )

        # 4. Alt Kontroller (İptal Butonu)
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.grid(row=3, column=0, padx=20, pady=(0, 16), sticky="e")

        self.cancel_btn = ctk.CTkButton(
            self.actions_frame,
            text="✕ İptal Et",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_DANGER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_BORDER,
            width=110,
            height=32,
            command=self.on_cancel
        )
        self.cancel_btn.pack(side="right")

    def _create_metric_box(self, parent, col: int, title: str, value: str, icon: str) -> ctk.CTkLabel:
        """Metrik kutucuklarını oluşturur."""
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=0, column=col, padx=12, pady=10, sticky="ew")

        title_lbl = ctk.CTkLabel(
            box,
            text=f"{icon} {title}",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED
        )
        title_lbl.pack(anchor="center")

        val_lbl = ctk.CTkLabel(
            box,
            text=value,
            font=FONT_METRIC,
            text_color=COLOR_TEXT_PRIMARY
        )
        val_lbl.pack(anchor="center", pady=(2, 0))
        return val_lbl

    def update_progress(self, data: Dict[str, Any]) -> None:
        """Gelen indirme verileriyle arayüzü anlık günceller."""
        percent = data.get("percent", 0.0)
        self.progress_bar.set(max(0.0, min(1.0, percent / 100.0)))

        self.percent_label.configure(text=f"%{percent:.1f}")

        # Durum Metni
        status_text = data.get("status_text", "İndiriliyor...")
        self.status_label.configure(text=status_text)

        # Muxing veya bitiş aşamasında renk değiştirme
        if data.get("is_muxing"):
            self.status_label.configure(text_color=COLOR_SUCCESS)
            self.progress_bar.configure(progress_color=COLOR_SUCCESS)
            self.percent_label.configure(text_color=COLOR_SUCCESS)
        else:
            self.status_label.configure(text_color=COLOR_TEXT_PRIMARY)
            self.progress_bar.configure(progress_color=COLOR_ACCENT)
            self.percent_label.configure(text_color=COLOR_ACCENT)

        # Sayaçlar
        speed_str = data.get("speed_str", "-- MB/s")
        self.speed_metric.configure(text=speed_str)

        eta_str = data.get("eta_str", "--:--")
        self.eta_metric.configure(text=eta_str)

        downloaded_str = data.get("downloaded_str", "--")
        total_str = data.get("total_str", "--")
        self.size_metric.configure(text=f"{downloaded_str} / {total_str}")

    def reset(self) -> None:
        """İlerleme kartını başlangıç durumuna sıfırlar."""
        self.progress_bar.set(0.0)
        self.progress_bar.configure(progress_color=COLOR_ACCENT)
        self.percent_label.configure(text="0%", text_color=COLOR_ACCENT)
        self.status_label.configure(text="İndirme Başlatılıyor...", text_color=COLOR_TEXT_PRIMARY)
        self.speed_metric.configure(text="-- MB/s")
        self.eta_metric.configure(text="--:--")
        self.size_metric.configure(text="-- / --")
        self.cancel_btn.configure(state="normal", text="✕ İptal Et")
