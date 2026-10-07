using System;
using System.IO;
using System.Windows;
using System.Windows.Forms.Integration;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using LibVLCSharp.Shared;
using VlcMedia = LibVLCSharp.Shared.Media;
using VlcPlayer = LibVLCSharp.Shared.MediaPlayer;
using WinForms = System.Windows.Forms;

namespace WallpaperApp
{
    /// <summary>
    /// Masaüstü arka planına (WorkerW katmanına) gömülen ve videoyu/GIF'i oynatan
    /// görünmez duvar kağıdı penceresi. Arayüzden bağımsız çalışır.
    /// </summary>
    // Video LibVLC ile oynatılır: WPF MediaElement eski WMP altyapısını kullandığı için AV1 açamıyor.
    public partial class WallpaperWindow : Window
    {
        private const int PauseCheckIntervalMs = 750;

        private IntPtr _hwnd;
        private IntPtr _workerW;
        private DispatcherTimer _pauseTimer;

        private bool _isGif;
        private bool _userPaused;
        private bool _autoPaused;
        private bool _closing;
        private bool _surfaceReady;
        private string _loadedPath;

        private int _screenWidthPx;
        private int _screenHeightPx;
        private int _videoWidthPx;
        private int _videoHeightPx;

        private BitmapImage _gifSource;

        private readonly LibVLC _libVlc;
        private readonly VlcPlayer _player;
        private VlcMedia _media;
        private readonly WinForms.Panel _videoPanel;
        private readonly WindowsFormsHost _videoHost;
        private Stretch _videoStretch = Stretch.UniformToFill;
        private int _volume;
        private bool _muted = true;

        public WallpaperWindow()
        {
            InitializeComponent();

            Core.Initialize();
            // Eklenti önbelleği (plugins.dat) yoksa VLC her açılışta ~320 eklentiyi tarıyor (~14 sn).
            // İlk açılışta önbellek oluşturulur; sonraki açılışlar ~50 ms sürer.
            string pluginCache = Path.Combine(AppContext.BaseDirectory, "libvlc", "win-x64", "plugins", "plugins.dat");
            var vlcOptions = new System.Collections.Generic.List<string> { "--no-osd", "--no-video-title-show", "--no-snapshot-preview", "--quiet" };
            if (!File.Exists(pluginCache))
                vlcOptions.Add("--reset-plugins-cache");
            _libVlc = new LibVLC(vlcOptions.ToArray());
            _player = new VlcPlayer(_libVlc)
            {
                EnableHardwareDecoding = true,
                EnableMouseInput = false,
                EnableKeyInput = false
            };

            // LibVLC olayları kendi iş parçacığında gelir; oynatıcıyı bu olayların içinden
            // yönetmek kilitlenmeye yol açabildiği için işler UI iş parçacığına aktarılır.
            _player.Playing += (s, e) => Dispatcher.BeginInvoke(new Action(OnVideoPlaying));
            _player.EndReached += (s, e) => Dispatcher.BeginInvoke(new Action(RestartVideo));
            _player.EncounteredError += (s, e) =>
                System.Diagnostics.Debug.WriteLine("[Wallpaper] Video oynatılamadı: " + _loadedPath);
            // Panelin pencere tanıtıcısına (Handle) host yerleşmeden önce erişilmemeli: WinForms
            // yerleşirken onu yeniden oluşturabiliyor ve VLC eski tanıtıcıya bağlı kalıp siyah ekran veriyordu.
            _videoPanel = new WinForms.Panel { BackColor = System.Drawing.Color.Black };
            _videoPanel.HandleCreated += OnVideoSurfaceCreated;
            _videoPanel.HandleDestroyed += (s, e) => _surfaceReady = false;
            _videoHost = new WindowsFormsHost { Child = _videoPanel, Background = Brushes.Black };
            Root.Children.Insert(0, _videoHost);
        }

        private void OnVideoSurfaceCreated(object sender, EventArgs e)
        {
            if (_closing)
                return;

            IntPtr surface = _videoPanel.Handle;            if (_player.Hwnd != IntPtr.Zero && _player.Hwnd != surface)
                _player.Stop(); // yüzey yeniden oluşturuldu; oynatma yeni yüzeyde baştan başlar

            _player.Hwnd = surface;
            _surfaceReady = true;
            ApplyPlayState();
        }

        /// <summary>
        /// Yönetim arayüzünden gelen ayarları canlı olarak uygular.
        /// Video yolu değişmediyse medya yeniden yüklenmez (kesintisiz oynatma).
        /// </summary>
        public void ApplySettings(AppSettings settings)
        {
            bool pathChanged = !string.Equals(_loadedPath, settings.VideoPath, StringComparison.OrdinalIgnoreCase);
            if (pathChanged)
                LoadMedia(settings.VideoPath);

            ApplyStretch(settings.StretchMode);
            ApplyVolume(settings);
            ApplyScale(settings);

            ApplyPlayState();
        }

        public void TogglePlayPause()
        {
            _userPaused = !_userPaused;
            ApplyPlayState();
        }

        private void OnSourceInitialized(object sender, EventArgs e)
        {
            _hwnd = new WindowInteropHelper(this).Handle;

            int exStyle = Win32Interop.GetWindowLong(_hwnd, Win32Interop.GWL_EXSTYLE);
            exStyle |= Win32Interop.WS_EX_NOACTIVATE | Win32Interop.WS_EX_TOOLWINDOW;
            Win32Interop.SetWindowLong(_hwnd, Win32Interop.GWL_EXSTYLE, exStyle);

            AttachToDesktop();
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            StartPauseMonitor();
        }

        private void OnClosing(object sender, System.ComponentModel.CancelEventArgs e)
        {
            _closing = true;
            _pauseTimer?.Stop();

            _player.Stop();
            _player.Dispose();
            _media?.Dispose();
            _libVlc.Dispose();
        }

        private void AttachToDesktop()
        {
            int left = Win32Interop.GetSystemMetrics(Win32Interop.SM_XVIRTUALSCREEN);
            int top = Win32Interop.GetSystemMetrics(Win32Interop.SM_YVIRTUALSCREEN);
            _screenWidthPx = Win32Interop.GetSystemMetrics(Win32Interop.SM_CXVIRTUALSCREEN);
            _screenHeightPx = Win32Interop.GetSystemMetrics(Win32Interop.SM_CYVIRTUALSCREEN);

            _workerW = Win32Interop.FindWorkerW();

            if (_workerW != IntPtr.Zero)
            {
                // Arka plan WorkerW'yi tüm sanal masaüstünü kaplayacak şekilde konumlandır (çoklu monitör).
                Win32Interop.SetWindowPos(_workerW, IntPtr.Zero, left, top, _screenWidthPx, _screenHeightPx,
                    Win32Interop.SWP_NOZORDER | Win32Interop.SWP_NOACTIVATE);

                // Penceremizi WorkerW'nin çocuğu yap.
                Win32Interop.SetParent(_hwnd, _workerW);

                Win32Interop.SetWindowPos(_hwnd, new IntPtr(Win32Interop.HWND_BOTTOM), 0, 0, _screenWidthPx, _screenHeightPx,
                    Win32Interop.SWP_NOACTIVATE | Win32Interop.SWP_SHOWWINDOW);
            }
            else
            {
                // WorkerW bulunamadıysa (VM / farklı kabuk) en alttaki bağımsız pencere olarak çalış.
                Win32Interop.SetWindowPos(_hwnd, new IntPtr(Win32Interop.HWND_BOTTOM), left, top, _screenWidthPx, _screenHeightPx,
                    Win32Interop.SWP_NOACTIVATE | Win32Interop.SWP_SHOWWINDOW);
            }
        }

        private void StartPauseMonitor()
        {
            _pauseTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(PauseCheckIntervalMs) };
            _pauseTimer.Tick += OnPauseCheck;
            _pauseTimer.Start();
        }

        private void OnPauseCheck(object sender, EventArgs e)
        {
            // Duvar kağıdı görünmüyorsa (büyütülmüş/tam ekran pencerelerin arkasında) oynatmayı
            // durdur: görünmeyen video için GPU'nun çözücüsü boşuna çalışmasın.
            bool shouldPause = Win32Interop.IsDesktopCovered();

            if (shouldPause != _autoPaused)
            {
                _autoPaused = shouldPause;
                ApplyPlayState();
            }
        }

        private bool ShouldPlay => !_userPaused && !_autoPaused;

        private void ApplyPlayState()
        {
            if (_isGif)
            {
                if (ShouldPlay)
                {
                    GifImage.Source = _gifSource;
                    GifImage.Visibility = Visibility.Visible;
                }
                else
                {
                    GifImage.Source = null;
                    GifImage.Visibility = Visibility.Collapsed;
                }
                return;
            }

            if (_player.Media == null || !_surfaceReady)
                return;

            if (ShouldPlay)
            {
                if (_player.State == VLCState.Paused)
                    _player.SetPause(false);
                else if (!_player.IsPlaying)
                    _player.Play();
            }
            else if (_player.IsPlaying)
            {
                _player.SetPause(true);
            }
        }

        private void OnVideoPlaying()
        {
            if (_closing)
                return;

            // Ses çıkışı oynatma başlayınca oluştuğu için ses ayarı burada yeniden uygulanır.
            ApplyAudioToPlayer();

            // Açılış sırasında duraklatma istendiyse (ör. tam ekran oyun) şimdi uygula.
            if (!ShouldPlay)
                _player.SetPause(true);
        }

        private void RestartVideo()
        {
            if (_closing || _isGif || _player.Media == null)
                return;

            _player.Stop();
            if (ShouldPlay)
                _player.Play();
        }

        private void LoadMedia(string path)
        {
            _loadedPath = path;

            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                SetVideoMedia(null);
                GifImage.Source = null;
                _gifSource = null;
                return;
            }

            string ext = Path.GetExtension(path).ToLowerInvariant();
            if (ext == ".gif")
                LoadGif(path);
            else
                LoadVideo(path);
        }

        private void LoadVideo(string path)
        {
            _isGif = false;
            GifImage.Visibility = Visibility.Collapsed;
            GifImage.Source = null;
            _gifSource = null;
            _videoHost.Visibility = Visibility.Visible;

            var media = new VlcMedia(_libVlc, path, FromType.FromPath);
            // Dosya sonunda baştan başlayarak kesintisiz döngü (EndReached yalnızca yedek).
            media.AddOption(":input-repeat=65535");
            SetVideoMedia(media);
        }

        private void LoadGif(string path)
        {
            _isGif = true;
            SetVideoMedia(null);
            _videoHost.Visibility = Visibility.Collapsed;

            var bitmap = new BitmapImage();
            bitmap.BeginInit();
            bitmap.CacheOption = BitmapCacheOption.OnLoad; // animasyonu oynatır ve dosya kilidini bırakır
            bitmap.UriSource = new Uri(path);
            bitmap.EndInit();

            _gifSource = bitmap;
            GifImage.Visibility = Visibility.Visible;
            GifImage.Source = bitmap;
        }

        private void SetVideoMedia(VlcMedia media)
        {
            _player.Stop();
            _player.Media = media;

            _media?.Dispose();
            _media = media;
        }

        private void ApplyStretch(string mode)
        {
            if (!Enum.TryParse(mode, out Stretch stretch))
                stretch = Stretch.UniformToFill;

            _videoStretch = stretch;
            GifImage.Stretch = stretch;

            // "Center" (None) için içeriği ortala; diğerleri ekranı doldursun.
            var halign = stretch == Stretch.None ? HorizontalAlignment.Center : HorizontalAlignment.Stretch;
            var valign = stretch == Stretch.None ? VerticalAlignment.Center : VerticalAlignment.Stretch;
            GifImage.HorizontalAlignment = halign;
            GifImage.VerticalAlignment = valign;

            ApplyVideoGeometry();
        }

        /// <summary>
        /// WPF Stretch modlarının LibVLC karşılıkları. Video kendi yerel penceresine çizildiği için
        /// WPF dönüşümleri uygulanamaz; doldurma, VLC'nin en-boy oranı ve kırpma ayarlarıyla yapılır.
        /// </summary>
        private void ApplyVideoGeometry()
        {
            int w = Math.Max(1, _videoWidthPx > 0 ? _videoWidthPx : _screenWidthPx);
            int h = Math.Max(1, _videoHeightPx > 0 ? _videoHeightPx : _screenHeightPx);
            int gcd = Gcd(w, h);
            string surfaceRatio = (w / gcd) + ":" + (h / gcd);

            _player.Scale = 0;
            _player.AspectRatio = null;
            _player.CropGeometry = null;

            switch (_videoStretch)
            {
                case Stretch.Fill:
                    _player.AspectRatio = surfaceRatio;     // en-boy oranını bozarak tamamen doldur
                    break;
                case Stretch.UniformToFill:
                    _player.CropGeometry = surfaceRatio;    // taşan kısmı kırparak doldur
                    break;
                case Stretch.None:
                    _player.Scale = 1;                      // orijinal piksel boyutu, ortada
                    break;
                // Uniform: VLC varsayılanı (sığdır, kenarlarda siyah bant)
            }
        }

        private void ApplyVolume(AppSettings settings)
        {
            _muted = settings.IsMuted;
            _volume = (int)Math.Round(Clamp(settings.Volume, 0.0, 1.0) * 100.0);
            ApplyAudioToPlayer();
        }

        private void ApplyAudioToPlayer()
        {
            _player.Mute = _muted;
            _player.Volume = _muted ? 0 : _volume;
        }

        private void ApplyScale(AppSettings settings)
        {
            double sx, sy;

            if (settings.AutoResolution)
            {
                sx = 1.0;
                sy = 1.0;
            }
            else if (settings.Width > 0 && settings.Height > 0)
            {
                // Manuel genişlik/yükseklik: ekran çözünürlüğüne göre bağımsız ölçek.
                sx = settings.Width / (double)_screenWidthPx;
                sy = settings.Height / (double)_screenHeightPx;
            }
            else
            {
                double k = settings.ScalePercent / 100.0;
                sx = sy = k;
            }

            sx = Clamp(sx, 0.01, 10.0);
            sy = Clamp(sy, 0.01, 10.0);

            var dpi = VisualTreeHelper.GetDpi(this);
            var transform = new ScaleTransform(sx, sy)
            {
                CenterX = (_screenWidthPx / dpi.DpiScaleX) / 2.0,
                CenterY = (_screenHeightPx / dpi.DpiScaleY) / 2.0
            };
            GifImage.RenderTransform = transform;

            // Yerel video penceresine WPF dönüşümü uygulanamadığı için ölçek, video alanının
            // boyutu değiştirilip ortalanarak uygulanır.
            if (sx == 1.0 && sy == 1.0)
            {
                _videoHost.Width = double.NaN;
                _videoHost.Height = double.NaN;
                _videoHost.HorizontalAlignment = HorizontalAlignment.Stretch;
                _videoHost.VerticalAlignment = VerticalAlignment.Stretch;
            }
            else
            {
                _videoHost.Width = _screenWidthPx * sx / dpi.DpiScaleX;
                _videoHost.Height = _screenHeightPx * sy / dpi.DpiScaleY;
                _videoHost.HorizontalAlignment = HorizontalAlignment.Center;
                _videoHost.VerticalAlignment = VerticalAlignment.Center;
            }

            _videoWidthPx = (int)Math.Round(_screenWidthPx * sx);
            _videoHeightPx = (int)Math.Round(_screenHeightPx * sy);
            ApplyVideoGeometry();
        }

        private static int Gcd(int a, int b)
        {
            while (b != 0)
            {
                int t = a % b;
                a = b;
                b = t;
            }
            return a;
        }

        private static double Clamp(double value, double min, double max)
        {
            if (value < min) return min;
            if (value > max) return max;
            return value;
        }
    }
}
