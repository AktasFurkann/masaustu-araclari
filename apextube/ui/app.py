"""
ApexTube 8K Video Downloader - Modern CustomTkinter Ana Arayüzü
"""
import os
import sys
import threading
from pathlib import Path
from typing import Optional, Tuple
from tkinter import filedialog, messagebox
import customtkinter as ctk

from config import (
    APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT, DEFAULT_DOWNLOAD_DIR
)
from ui.styles import (
    COLOR_BG_MAIN, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_SUCCESS, COLOR_DANGER,
    COLOR_WARNING, COLOR_PURPLE, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED, FONT_TITLE, FONT_SUBTITLE, FONT_SECTION, FONT_BODY,
    FONT_BODY_BOLD, FONT_SMALL, FONT_BADGE
)
from ui.components.video_card import VideoInfoCard
from ui.components.progress_widget import ProgressWidget
from ui.components.history_list import HistoryListView
from core.analyzer import YouTubeAnalyzer
from core.downloader import VideoDownloader
from core.ffmpeg_checker import FFmpegChecker
from core import updater
from utils.helpers import is_valid_youtube_url, open_file_in_explorer, play_media_file, open_directory
from utils.history_manager import HistoryManager


class ModernDownloaderApp(ctk.CTk):
    """ApexTube 8K Ultra HD Downloader Masaüstü Uygulama Penceresi"""

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.configure(fg_color=COLOR_BG_MAIN)

        self.download_dir = os.path.abspath(DEFAULT_DOWNLOAD_DIR)
        self.history_manager = HistoryManager()
        self.current_downloader = None
        self.is_analyzing = False
        self.analyzed_video_data = None
        self.analyzed_thumbnail_img = None

        self.ffmpeg_ok, self.ffmpeg_path, self.ffmpeg_version = FFmpegChecker.verify_ffmpeg()

        self._build_header()
        self._build_url_section()
        self._build_content_area()
        self._build_history_section()

    def _build_header(self) -> None:
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=24, pady=(20, 12))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure((1, 2), weight=0)

        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        title_lbl = ctk.CTkLabel(
            title_box,
            text=f"🚀 {APP_NAME}",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            title_box,
            text="YouTube 4K, 8K, HDR ve Klip Kesme (Time-Range) Destekli Video İndirici",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        badge_text = "✓ FFmpeg Aktif" if self.ffmpeg_ok else "⚠ FFmpeg Gerekli"
        badge_color = COLOR_SUCCESS if self.ffmpeg_ok else COLOR_WARNING
        badge_hover = "#0D9488" if self.ffmpeg_ok else "#D97706"

        self.ffmpeg_btn = ctk.CTkButton(
            self.header_frame,
            text=badge_text,
            font=FONT_BADGE,
            text_color="#FFFFFF",
            fg_color=badge_color,
            hover_color=badge_hover,
            corner_radius=20,
            width=120,
            height=28,
            command=self._show_ffmpeg_info
        )
        self.ffmpeg_btn.grid(row=0, column=2, sticky="e")

        self.update_btn = ctk.CTkButton(
            self.header_frame,
            text="🔄 Güncellemeleri Denetle",
            font=FONT_BADGE,
            text_color=COLOR_TEXT_PRIMARY,
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BORDER,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=20,
            height=28,
            command=self._on_update_click
        )
        self.update_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.available_update = None
        self.is_updating = False

        if updater.can_self_update():
            threading.Thread(target=self._check_update_in_background, daemon=True).start()

    # --- Güncelleme ---

    def _check_update_in_background(self) -> None:
        try:
            update = updater.check_for_update()
        except Exception:
            return  # açılışta sessiz kontrol; internet yoksa sorun etme
        if update:
            self.after(0, lambda: self._show_update_available(update))

    def _show_update_available(self, update: dict) -> None:
        self.available_update = update
        self.update_btn.configure(
            text=f"⬆ Güncelle (v{update['version']})",
            text_color="#FFFFFF",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            border_width=0
        )

    def _on_update_click(self) -> None:
        if self.is_updating:
            return
        if not updater.can_self_update():
            messagebox.showinfo("Güncelleme", "Program kaynak koddan çalışıyor; güncelleme yalnızca kurulu sürümde kullanılabilir.")
            return

        if self.available_update:
            self._confirm_and_install(self.available_update)
            return

        self.update_btn.configure(text="🔄 Denetleniyor...", state="disabled")

        def worker():
            try:
                update = updater.check_for_update()
                self.after(0, lambda: self._after_manual_check(update, None))
            except Exception as e:
                self.after(0, lambda err=e: self._after_manual_check(None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _after_manual_check(self, update: Optional[dict], error: Optional[Exception]) -> None:
        self.update_btn.configure(text="🔄 Güncellemeleri Denetle", state="normal")
        if error:
            messagebox.showerror("Güncelleme", f"Güncelleme kontrol edilemedi. İnternet bağlantınızı kontrol edin.\n\n{error}")
        elif update:
            self._show_update_available(update)
            self._confirm_and_install(update)
        else:
            messagebox.showinfo("Güncelleme", f"En güncel sürümü kullanıyorsunuz (v{APP_VERSION}).")

    def _confirm_and_install(self, update: dict) -> None:
        if self.current_downloader and self.current_downloader.is_alive():
            messagebox.showwarning("Güncelleme", "Devam eden bir indirme var. Güncellemeden önce indirmenin bitmesini bekleyin veya iptal edin.")
            return
        if not messagebox.askyesno(
            "Güncelleme",
            f"Yeni sürüm hazır: v{update['version']} (şu an v{APP_VERSION}).\n\n"
            "İndirilip kurulsun mu? Programlar kısa süreliğine kapanıp yeniden açılacak."
        ):
            return

        self.is_updating = True
        self.update_btn.configure(state="disabled", text="⬇ İndiriliyor...")

        def on_progress(done: int, total: int) -> None:
            if total:
                self.after(0, lambda: self.update_btn.configure(text=f"⬇ İndiriliyor %{done * 100 // total}"))

        def worker():
            try:
                path = updater.download_installer(update, on_progress)
                updater.run_installer(path)
                self.after(0, self._exit_for_update)
            except Exception as e:
                self.after(0, lambda err=e: self._update_failed(err))

        threading.Thread(target=worker, daemon=True).start()

    def _update_failed(self, error: Exception) -> None:
        self.is_updating = False
        self.update_btn.configure(state="normal")
        self._show_update_available(self.available_update)
        messagebox.showerror("Güncelleme", f"Güncelleme indirilemedi:\n\n{error}")

    def _exit_for_update(self) -> None:
        self.destroy()
        os._exit(0)

    def _build_url_section(self) -> None:
        self.url_card = ctk.CTkFrame(
            self,
            fg_color=COLOR_BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        self.url_card.pack(fill="x", padx=24, pady=(0, 16))
        self.url_card.grid_columnconfigure(0, weight=1)
        self.url_card.grid_columnconfigure((1, 2), weight=0)

        self.url_entry = ctk.CTkEntry(
            self.url_card,
            placeholder_text="YouTube video bağlantısını buraya yapıştırın (örn: https://www.youtube.com/watch?v=...)",
            font=FONT_BODY,
            fg_color=COLOR_BG_INPUT,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            height=44
        )
        self.url_entry.grid(row=0, column=0, padx=(16, 8), pady=12, sticky="ew")
        self.url_entry.bind("<Return>", lambda event: self.start_analysis())

        self.paste_btn = ctk.CTkButton(
            self.url_card,
            text="📋 Yapıştır",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_BORDER,
            width=90,
            height=44,
            command=self._paste_clipboard
        )
        self.paste_btn.grid(row=0, column=1, padx=(0, 8), pady=12)

        self.analyze_btn = ctk.CTkButton(
            self.url_card,
            text="🔍 Analiz Et",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            width=110,
            height=44,
            command=self.start_analysis
        )
        self.analyze_btn.grid(row=0, column=2, padx=(0, 16), pady=12)

    def _build_content_area(self) -> None:
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="x", padx=24, pady=(0, 16))
        self._show_welcome_view()

    def _show_welcome_view(self) -> None:
        self._clear_content_container()

        welcome_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=COLOR_BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        welcome_frame.pack(fill="x", pady=4)
        welcome_frame.grid_columnconfigure((0, 1, 2), weight=1)

        features = [
            ("🎬", "8K & 4K Ultra HD", "2160p60 ve 4320p kalitelerinde canlı ve pürüzsüz görüntü."),
            ("✂️", "Zaman Aralığı (Klip)", "10 saatlik videolardan sadece istediğiniz 1-5 dakikayı hızla indirin."),
            ("🖼️", "Live Wallpaper Hazır", "Duvar kağıdı uygulamanızda çalışan, küçük boyutlu AV1 formatı.")
        ]

        for idx, (icon, title, desc) in enumerate(features):
            box = ctk.CTkFrame(welcome_frame, fg_color="transparent")
            box.grid(row=0, column=idx, padx=16, pady=24, sticky="nsew")

            icon_lbl = ctk.CTkLabel(box, text=icon, font=("Segoe UI", 26))
            icon_lbl.pack(pady=(0, 6))

            title_lbl = ctk.CTkLabel(box, text=title, font=FONT_BODY_BOLD, text_color=COLOR_TEXT_PRIMARY)
            title_lbl.pack(pady=(0, 4))

            desc_lbl = ctk.CTkLabel(box, text=desc, font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, wraplength=220)
            desc_lbl.pack()

    def _build_history_section(self) -> None:
        self.history_frame = ctk.CTkFrame(
            self,
            fg_color=COLOR_BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        self.history_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        self.history_list = HistoryListView(
            self.history_frame,
            history_manager=self.history_manager
        )
        self.history_list.pack(fill="both", expand=True, padx=16, pady=16)

    def _clear_content_container(self) -> None:
        for widget in self.content_container.winfo_children():
            widget.destroy()

    def _paste_clipboard(self) -> None:
        try:
            clipboard_text = self.clipboard_get().strip()
            if clipboard_text:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clipboard_text)
                if is_valid_youtube_url(clipboard_text):
                    self.start_analysis()
        except Exception:
            pass

    def start_analysis(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Uyarı", "Lütfen bir YouTube video bağlantısı girin.")
            return

        if not is_valid_youtube_url(url):
            messagebox.showerror("Geçersiz URL", "Girilen bağlantı geçerli bir YouTube video adresi değil.")
            return

        if self.is_analyzing:
            return

        self.is_analyzing = True
        self.analyze_btn.configure(state="disabled", text="⏳ Analiz...")
        self.paste_btn.configure(state="disabled")

        self._clear_content_container()
        loading_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=COLOR_BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER
        )
        loading_frame.pack(fill="x", pady=4)

        loading_lbl = ctk.CTkLabel(
            loading_frame,
            text="🔄 4K/8K çözünürlükler ve video süresi taranıyor, lütfen bekleyin...",
            font=FONT_SUBTITLE,
            text_color=COLOR_ACCENT
        )
        loading_lbl.pack(pady=30)

        threading.Thread(target=self._run_analysis_worker, args=(url,), daemon=True).start()

    def _run_analysis_worker(self, url: str) -> None:
        try:
            data = YouTubeAnalyzer.analyze_url(url)
            thumb_img = YouTubeAnalyzer.fetch_thumbnail_image(data.get("thumbnail_url"))
            self.after(0, lambda: self._on_analysis_success(data, thumb_img))
        except Exception as e:
            self.after(0, lambda: self._on_analysis_error(str(e)))

    def _on_analysis_success(self, data: dict, thumb_img) -> None:
        self.is_analyzing = False
        self.analyze_btn.configure(state="normal", text="🔍 Analiz Et")
        self.paste_btn.configure(state="normal")

        self.analyzed_video_data = data
        self.analyzed_thumbnail_img = thumb_img

        self._clear_content_container()

        self.video_card = VideoInfoCard(
            self.content_container,
            video_data=data,
            thumbnail_img=thumb_img,
            download_dir=self.download_dir,
            on_start_download=self.start_download,
            on_change_folder=self.choose_download_folder
        )
        self.video_card.pack(fill="x", pady=4)

    def _on_analysis_error(self, error_message: str) -> None:
        self.is_analyzing = False
        self.analyze_btn.configure(state="normal", text="🔍 Analiz Et")
        self.paste_btn.configure(state="normal")
        self._show_welcome_view()
        messagebox.showerror("Analiz Hatası", f"Video bilgileri alınamadı:\n\n{error_message}")

    def choose_download_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.download_dir, title="İndirme Klasörünü Seçin")
        if chosen:
            self.download_dir = os.path.abspath(chosen)
            if hasattr(self, 'video_card') and self.video_card:
                self.video_card.update_folder_path(self.download_dir)

    def start_download(
        self,
        resolution_label: str,
        output_format: str,
        download_folder: str,
        time_range: Optional[Tuple[float, float]] = None
    ) -> None:
        if not self.analyzed_video_data:
            return

        url = self.analyzed_video_data.get("url")
        self._clear_content_container()

        self.progress_widget = ProgressWidget(
            self.content_container,
            on_cancel=self.cancel_download
        )
        self.progress_widget.pack(fill="x", pady=4)

        target_dir = os.path.abspath(download_folder)

        self.current_downloader = VideoDownloader(
            url=url,
            download_dir=target_dir,
            resolution_label=resolution_label,
            output_format=output_format,
            time_range=time_range,
            on_progress=lambda data: self.after(0, lambda: self.progress_widget.update_progress(data)),
            on_complete=lambda data: self.after(0, lambda: self._on_download_complete(data)),
            on_error=lambda err: self.after(0, lambda: self._on_download_error(err)),
            on_cancel=lambda: self.after(0, self._on_download_cancelled)
        )
        self.current_downloader.start()

    def cancel_download(self) -> None:
        if self.current_downloader and self.current_downloader.is_alive():
            self.current_downloader.cancel()

    def _on_download_cancelled(self) -> None:
        messagebox.showinfo("İptal Edildi", "İndirme işlemi iptal edildi.")
        self._show_welcome_view()

    def _on_download_error(self, error_message: str) -> None:
        messagebox.showerror("İndirme Hatası", f"İndirme sırasında hata oluştu:\n\n{error_message}")
        self._show_welcome_view()

    def _on_download_complete(self, result_data: dict) -> None:
        download_folder = result_data.get("download_dir") or self.download_dir
        file_path = result_data.get("file_path", "")

        self.history_manager.add_entry(
            title=result_data.get("title", "Video"),
            file_path=file_path,
            resolution=result_data.get("resolution", ""),
            format_ext=result_data.get("format", ""),
            file_size=result_data.get("file_size"),
            duration=result_data.get("duration"),
            thumbnail_url=result_data.get("thumbnail_url"),
            video_url=result_data.get("url"),
            download_dir=download_folder
        )
        self.history_list.refresh()

        self._clear_content_container()

        success_frame = ctk.CTkFrame(
            self.content_container,
            fg_color=COLOR_BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_SUCCESS
        )
        success_frame.pack(fill="x", pady=4)
        success_frame.grid_columnconfigure(0, weight=1)
        success_frame.grid_columnconfigure((1, 2, 3), weight=0)

        title_text = result_data.get("title", "Video")

        info_box = ctk.CTkFrame(success_frame, fg_color="transparent")
        info_box.grid(row=0, column=0, padx=20, pady=16, sticky="w")

        succ_title = ctk.CTkLabel(
            info_box,
            text="🎉 İndirme ve Birleştirme Başarıyla Tamamlandı!",
            font=FONT_SUBTITLE,
            text_color=COLOR_SUCCESS
        )
        succ_title.pack(anchor="w")

        duration_tag = f" • {result_data.get('duration')}" if result_data.get('duration') else ""
        succ_desc = ctk.CTkLabel(
            info_box,
            text=f"{title_text}{duration_tag} • {result_data.get('file_size_str', '')}",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY
        )
        succ_desc.pack(anchor="w", pady=(2, 0))

        play_btn = ctk.CTkButton(
            success_frame,
            text="▶ Oynat",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_SUCCESS,
            hover_color="#059669",
            width=75,
            height=34,
            command=lambda: play_media_file(file_path)
        )
        play_btn.grid(row=0, column=1, padx=(0, 6), pady=16)

        folder_btn = ctk.CTkButton(
            success_frame,
            text="📁 Klasörde Göster",
            font=FONT_BODY_BOLD,
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_BORDER,
            width=115,
            height=34,
            command=lambda: open_file_in_explorer(file_path, fallback_dir=download_folder)
        )
        folder_btn.grid(row=0, column=2, padx=(0, 6), pady=16)

        new_btn = ctk.CTkButton(
            success_frame,
            text="Yeni İndirme",
            font=FONT_BODY,
            fg_color="transparent",
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_MUTED,
            width=85,
            height=34,
            command=self._show_welcome_view
        )
        new_btn.grid(row=0, column=3, padx=(0, 16), pady=16)

    def _show_ffmpeg_info(self) -> None:
        if self.ffmpeg_ok:
            messagebox.showinfo(
                "FFmpeg Durumu: Aktif",
                f"FFmpeg başarıyla devrede!\n\n"
                f"Konum: {self.ffmpeg_path}\n"
                f"Sürüm: {self.ffmpeg_version}\n\n"
                f"Tüm 4K, 8K, HDR, Klip kesme ve ses birleştirme (muxing) özellikleri hazırdır."
            )
        else:
            messagebox.showwarning(
                "FFmpeg Gerekli",
                FFmpegChecker.get_installation_instructions()
            )
