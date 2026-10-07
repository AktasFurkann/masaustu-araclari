namespace WallpaperApp
{
    /// <summary>
    /// Kullanıcı ayarları; %LOCALAPPDATA%\WallpaperApp\settings.json dosyasına
    /// System.Text.Json ile serialize edilir.
    /// </summary>
    public class AppSettings
    {
        // Seçilen video / GIF dosyasının tam yolu.
        public string VideoPath { get; set; } = string.Empty;

        // UniformToFill | Fill | Uniform | None  (None = "Orijinal boyut / merkez")
        public string StretchMode { get; set; } = "UniformToFill";

        // Çözünürlük / ölçek
        public bool AutoResolution { get; set; } = true;
        public int Width { get; set; } = 0;      // 0 = otomatik
        public int Height { get; set; } = 0;     // 0 = otomatik
        public int ScalePercent { get; set; } = 100;

        // Ses
        public double Volume { get; set; } = 0.0; // 0..1
        public bool IsMuted { get; set; } = true;
    }
}
