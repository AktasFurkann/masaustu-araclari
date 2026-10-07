"""
ApexTube 8K Video Downloader - Otomatik Formatlı Zaman Girişi (TimeEntry)
Kullanıcı sadece rakam girer, HH:MM:SS formatı otomatik oluşur.
Mikrodalgadaki/saatlerdeki gibi sağdan sola dolan giriş mantığı.
"""
import tkinter as tk
import customtkinter as ctk
from ui.styles import (
    COLOR_BG_INPUT, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED,
    FONT_SMALL
)


class TimeEntry(ctk.CTkFrame):
    """
    Otomatik formatlanan zaman girişi widget'ı.
    
    Kullanıcı sadece rakamları girer, ":" otomatik eklenir.
    Sağdan sola dolar:
      - "5" yazdığında       -> 00:00:05
      - "30" yazdığında      -> 00:00:30
      - "500" yazdığında     -> 00:05:00  (5 dakika)
      - "235" yazdığında     -> 00:02:35  (2 dk 35 sn)
      - "10000" yazdığında   -> 01:00:00  (1 saat)
      - "12345" yazdığında   -> 01:23:45
    
    Backspace ile son rakam silinir.
    """

    def __init__(self, master, initial_value: str = "00:00:00", width: int = 110, height: int = 28, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._digits = []  # Girilen ham rakamlar (sadece sayılar)
        self._max_digits = 6  # HHMMSS = 6 hane
        self._is_disabled = False

        # StringVar ile entry'yi kontrol et
        self._var = tk.StringVar(value="00:00:00")

        # Entry widget
        self.entry = ctk.CTkEntry(
            self,
            font=("Consolas", 13, "bold"),
            fg_color=COLOR_BG_INPUT,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            justify="center",
            textvariable=self._var,
            width=width,
            height=height
        )
        self.entry.pack(fill="x", expand=True)

        # Başlangıç değerini ayarla
        self._set_initial_value(initial_value)

        # Tüm tuş olaylarını yakala - internal widget'a bağla
        self.entry.bind("<KeyPress>", self._on_key_press)
        self.entry.bind("<Control-v>", self._on_paste)
        self.entry.bind("<Control-V>", self._on_paste)
        # Fare ile seçim ve düzenlemeyi engelle
        self.entry.bind("<Button-1>", self._on_click)
        # FocusIn ile imleci sona taşı
        self.entry.bind("<FocusIn>", lambda e: self._move_cursor_end())

    def _set_initial_value(self, value: str) -> None:
        """Başlangıç değerini parse et ve rakam listesine dönüştür."""
        only_digits = [ch for ch in value if ch.isdigit()]
        stripped = ''.join(only_digits).lstrip('0')
        self._digits = list(stripped)
        self._refresh_display()

    def _on_click(self, event) -> None:
        """Tıklama olayında imleci sona taşı."""
        self.after(10, self._move_cursor_end)

    def _move_cursor_end(self) -> None:
        """İmleci her zaman sona taşı."""
        self.entry.icursor("end")
        self.entry.xview_moveto(1)

    def _on_key_press(self, event) -> str:
        """Her tuş basımını yakala ve yönet."""
        if self._is_disabled:
            return "break"

        key = event.keysym
        char = event.char

        # Tab - geçiş izin ver
        if key in ("Tab", "ISO_Left_Tab"):
            return None

        # Rakam tuşları (0-9)
        if char and char.isdigit():
            if len(self._digits) < self._max_digits:
                self._digits.append(char)
                self._refresh_display()
            return "break"

        # Backspace - son rakamı sil
        if key == "BackSpace":
            if self._digits:
                self._digits.pop()
                self._refresh_display()
            return "break"

        # Delete - tümünü sil
        if key == "Delete":
            self._digits.clear()
            self._refresh_display()
            return "break"

        # Diğer tüm tuşları engelle
        return "break"

    def _on_paste(self, event) -> str:
        """Yapıştırma olayını yakala, sadece rakamları al."""
        if self._is_disabled:
            return "break"
        try:
            clipboard = self.clipboard_get()
            only_digits = [ch for ch in clipboard if ch.isdigit()]
            for d in only_digits:
                if len(self._digits) < self._max_digits:
                    self._digits.append(d)
            self._refresh_display()
        except Exception:
            pass
        return "break"

    def _refresh_display(self) -> None:
        """Rakam listesinden HH:MM:SS formatını oluştur ve göster."""
        raw = ''.join(self._digits)
        padded = raw.zfill(6)[-6:]

        hh = padded[0:2]
        mm = padded[2:4]
        ss = padded[4:6]

        formatted = f"{hh}:{mm}:{ss}"

        # StringVar üzerinden güncelle (entry'nin state'ini bozmadan)
        self._var.set(formatted)

        # İmleci sona taşı
        self.after(1, self._move_cursor_end)

    def get(self) -> str:
        """Formatlı zaman değerini döndürür (ör: '01:23:45')."""
        return self._var.get()

    def get_seconds(self) -> float:
        """Zaman değerini saniye cinsinden döndürür."""
        raw = ''.join(self._digits)
        padded = raw.zfill(6)[-6:]

        try:
            hh = int(padded[0:2])
            mm = int(padded[2:4])
            ss = int(padded[4:6])
            return hh * 3600.0 + mm * 60.0 + ss
        except ValueError:
            return 0.0

    def set_value(self, time_str: str) -> None:
        """Dışarıdan bir zaman değeri ayarla (ör: '00:05:00')."""
        self._set_initial_value(time_str)

    def set_seconds(self, total_sec: float) -> None:
        """Saniye cinsinden değer ayarla."""
        total_sec = max(0, int(total_sec))
        hh = total_sec // 3600
        mm = (total_sec % 3600) // 60
        ss = total_sec % 60
        self.set_value(f"{hh:02d}:{mm:02d}:{ss:02d}")

    def add_change_callback(self, callback) -> None:
        """Değer her değiştiğinde çağrılacak fonksiyonu kaydeder."""
        self._var.trace_add("write", lambda *_: callback())

    def configure_state(self, state: str) -> None:
        """Entry'nin state'ini ayarla ('normal' veya 'disabled')."""
        self._is_disabled = (state == "disabled")
        self.entry.configure(state=state)
        if self._is_disabled:
            self.entry.configure(text_color=COLOR_TEXT_MUTED)
        else:
            self.entry.configure(text_color=COLOR_TEXT_PRIMARY)
