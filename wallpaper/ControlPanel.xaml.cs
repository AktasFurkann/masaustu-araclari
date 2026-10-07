using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace WallpaperApp
{
    /// <summary>
    /// Modern dark-mode yönetim arayüzü. Ayarları okur, kullanıcı değişikliklerini
    /// anında settings.json'a kaydeder ve arka plan duvar kağıdına uygular.
    /// </summary>
    public partial class ControlPanel : Window
    {
        private readonly AppSettings _settings;
        private readonly WallpaperWindow _wallpaper;
        private bool _isLoading;
        private bool _isExiting;
        private bool _updating;
        private Updater.UpdateInfo _availableUpdate;

        public ControlPanel(AppSettings settings, WallpaperWindow wallpaper)
        {
            // XAML yüklenirken (IsChecked/Value gibi varsayılanlar) olayların
            // tetiklenip yarım kurulmuş durumda NRE fırlatmasını önle.
            _isLoading = true;
            _settings = settings;
            _wallpaper = wallpaper;
            InitializeComponent();
            LoadSettingsIntoUi();
        }

        public void PrepareForExit()
        {
            _isExiting = true;
        }

        public void ShowFromTray()
        {
            Show();
            if (WindowState == WindowState.Minimized)
                WindowState = WindowState.Normal;
            Activate();
            Topmost = true;
            Topmost = false;
        }

        private void LoadSettingsIntoUi()
        {
            _isLoading = true;
            try
            {
                SelectedFileText.Text = string.IsNullOrWhiteSpace(_settings.VideoPath)
                    ? "Hiçbir dosya seçilmedi"
                    : _settings.VideoPath;

                SelectStretchItem(_settings.StretchMode);

                AutoResCheck.IsChecked = _settings.AutoResolution;
                WidthBox.Text = _settings.Width > 0 ? _settings.Width.ToString() : string.Empty;
                HeightBox.Text = _settings.Height > 0 ? _settings.Height.ToString() : string.Empty;
                ScaleSlider.Value = _settings.ScalePercent;
                ScaleValueText.Text = _settings.ScalePercent + "%";

                MuteCheck.IsChecked = _settings.IsMuted;
                VolumeSlider.Value = _settings.Volume * 100.0;
                VolumeValueText.Text = "%" + (int)(_settings.Volume * 100.0);

                int w = Win32Interop.GetSystemMetrics(Win32Interop.SM_CXSCREEN);
                int h = Win32Interop.GetSystemMetrics(Win32Interop.SM_CYSCREEN);
                DetectedResText.Text = "Algılanan ekran çözünürlüğü: " + w + " × " + h;
                UpdateStatusText.Text = $"Sürüm v{Updater.CurrentVersion}";

                UpdateResolutionEnabledState();
            }
            finally
            {
                _isLoading = false;
            }
        }

        private void SelectStretchItem(string mode)
        {
            foreach (var item in StretchCombo.Items)
            {
                if (item is ComboBoxItem cbi && string.Equals(cbi.Tag as string, mode, StringComparison.OrdinalIgnoreCase))
                {
                    StretchCombo.SelectedItem = cbi;
                    return;
                }
            }
            StretchCombo.SelectedIndex = 0;
        }

        // --- Pencere kromu ---

        private void OnTitleBarMouseDown(object sender, MouseButtonEventArgs e)
        {
            if (e.ChangedButton == MouseButton.Left && e.ButtonState == MouseButtonState.Pressed)
            {
                try { DragMove(); } catch { /* sürükleme sırasında hata olursa yok say */ }
            }
        }

        private void OnMinimizeClick(object sender, RoutedEventArgs e)
        {
            WindowState = WindowState.Minimized;
        }

        private void OnCloseClick(object sender, RoutedEventArgs e)
        {
            HideToTray();
        }

        private void OnClosing(object sender, System.ComponentModel.CancelEventArgs e)
        {
            if (!_isExiting)
            {
                // Kapatma yerine tepsiye küçült.
                e.Cancel = true;
                HideToTray();
            }
        }

        private void HideToTray()
        {
            Hide();
        }

        // --- Olaylar: UI -> settings -> kaydet & uygula ---

        private void OnSelectVideoClick(object sender, RoutedEventArgs e)
        {
            var dialog = new Microsoft.Win32.OpenFileDialog
            {
                Title = "Duvar kağıdı videosu / GIF seçin",
                Filter = "Video / GIF (*.mp4;*.mkv;*.webm;*.mov;*.avi;*.gif)|*.mp4;*.mkv;*.webm;*.mov;*.avi;*.gif|Tüm dosyalar (*.*)|*.*"
            };

            if (dialog.ShowDialog() == true)
            {
                _settings.VideoPath = dialog.FileName;
                SelectedFileText.Text = dialog.FileName;
                SaveAndApply();
            }
        }

        private void OnStretchChanged(object sender, SelectionChangedEventArgs e)
        {
            if (_isLoading) return;
            if (StretchCombo.SelectedItem is ComboBoxItem cbi && cbi.Tag is string tag)
            {
                _settings.StretchMode = tag;
                SaveAndApply();
            }
        }

        private void OnAutoResChanged(object sender, RoutedEventArgs e)
        {
            if (_isLoading) return;
            _settings.AutoResolution = AutoResCheck.IsChecked == true;
            UpdateResolutionEnabledState();
            SaveAndApply();
        }

        private void OnResolutionTextChanged(object sender, TextChangedEventArgs e)
        {
            if (_isLoading) return;
            int.TryParse(WidthBox.Text, out int w);
            int.TryParse(HeightBox.Text, out int h);
            _settings.Width = w;
            _settings.Height = h;
            SaveAndApply();
        }

        private void OnScaleChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (_isLoading) return;
            _settings.ScalePercent = (int)ScaleSlider.Value;
            ScaleValueText.Text = _settings.ScalePercent + "%";
            SaveAndApply();
        }

        private void OnMuteChanged(object sender, RoutedEventArgs e)
        {
            if (_isLoading) return;
            _settings.IsMuted = MuteCheck.IsChecked == true;
            SaveAndApply();
        }

        private void OnVolumeChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (_isLoading) return;
            _settings.Volume = VolumeSlider.Value / 100.0;
            VolumeValueText.Text = "%" + (int)VolumeSlider.Value;
            SaveAndApply();
        }

        private void OnPlayPauseClick(object sender, RoutedEventArgs e)
        {
            _wallpaper.TogglePlayPause();
        }

        // --- Güncelleme ---

        public async void CheckForUpdatesSilently()
        {
            try
            {
                Updater.UpdateInfo update = await Updater.CheckAsync();
                if (update != null)
                    ShowUpdateAvailable(update);
            }
            catch
            {
                // Açılıştaki sessiz kontrol; internet yoksa sorun etme.
            }
        }

        private void ShowUpdateAvailable(Updater.UpdateInfo update)
        {
            _availableUpdate = update;
            UpdateStatusText.Text = $"Yeni sürüm hazır: v{update.Version} (şu an v{Updater.CurrentVersion})";
            UpdateButton.Content = $"Güncelle (v{update.Version})";
        }

        private async void OnUpdateClick(object sender, RoutedEventArgs e)
        {
            if (_updating)
                return;

            if (_availableUpdate == null)
            {
                UpdateButton.IsEnabled = false;
                UpdateStatusText.Text = "Denetleniyor...";
                try
                {
                    _availableUpdate = await Updater.CheckAsync();
                }
                catch
                {
                    UpdateStatusText.Text = "Güncelleme kontrol edilemedi. İnternet bağlantınızı kontrol edin.";
                    UpdateButton.IsEnabled = true;
                    return;
                }
                UpdateButton.IsEnabled = true;

                if (_availableUpdate == null)
                {
                    UpdateStatusText.Text = $"En güncel sürümü kullanıyorsunuz (v{Updater.CurrentVersion}).";
                    return;
                }
                ShowUpdateAvailable(_availableUpdate);
            }

            MessageBoxResult answer = MessageBox.Show(this,
                $"Yeni sürüm hazır: v{_availableUpdate.Version} (şu an v{Updater.CurrentVersion}).\n\n" +
                "İndirilip kurulsun mu? Programlar kısa süreliğine kapanıp yeniden açılacak.",
                "Güncelleme", MessageBoxButton.YesNo, MessageBoxImage.Question);
            if (answer != MessageBoxResult.Yes)
                return;

            _updating = true;
            UpdateButton.IsEnabled = false;
            try
            {
                var progress = new Progress<int>(p => UpdateStatusText.Text = $"İndiriliyor... %{p}");
                string installer = await Updater.DownloadAsync(_availableUpdate, progress);
                UpdateStatusText.Text = "Kuruluyor...";
                Updater.RunInstaller(installer);
                _isExiting = true;
                Application.Current.Shutdown();
            }
            catch (Exception ex)
            {
                _updating = false;
                UpdateButton.IsEnabled = true;
                UpdateStatusText.Text = "Güncelleme indirilemedi: " + ex.Message;
            }
        }

        private void UpdateResolutionEnabledState()
        {
            bool manual = AutoResCheck.IsChecked != true;
            WidthBox.IsEnabled = manual;
            HeightBox.IsEnabled = manual;
            ScaleSlider.IsEnabled = manual;
        }

        private void SaveAndApply()
        {
            SettingsService.Save(_settings);
            _wallpaper.ApplySettings(_settings);
        }
    }
}
