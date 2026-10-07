using System;
using System.IO;
using System.Threading;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;

namespace WallpaperApp
{
    public partial class App : Application
    {
        private const string MutexName = @"Local\WallpaperApp_SingleInstance";
        private const string ShowSignalName = @"Local\WallpaperApp_ShowSettings";

        private AppSettings _settings;
        private WallpaperWindow _wallpaper;
        private ControlPanel _panel;
        private TrayIcon _tray;

        private Mutex _mutex;
        private EventWaitHandle _showSignal;

        protected override void OnStartup(StartupEventArgs e)
        {
            // Yayın betiği (yayinla.ps1) çağırır: VLC eklenti önbelleğini (plugins.dat) önceden
            // oluşturur, böylece kurulumdan sonraki ilk açılış da hızlı olur.
            if (Array.IndexOf(e.Args, "--generate-vlc-cache") >= 0)
            {
                LibVLCSharp.Shared.Core.Initialize();
                using (new LibVLCSharp.Shared.LibVLC("--reset-plugins-cache")) { }
                Shutdown();
                return;
            }

            // Tek örnek koruması: uygulama zaten açıksa yeni örnek başlatma.
            _mutex = new Mutex(true, MutexName, out bool isFirstInstance);
            if (!isFirstInstance)
            {
                TryShowExistingInstance();
                MessageBox.Show("Uygulama zaten çalışıyor.", "Hareketli Duvar Kağıdı",
                    MessageBoxButton.OK, MessageBoxImage.Information);
                Shutdown();
                return;
            }

            // Çalışan örneğe "ayarları göster" sinyali için olay.
            _showSignal = new EventWaitHandle(false, EventResetMode.AutoReset, ShowSignalName);

            // GPU (donanım) hızlandırmayı garantiye al.
            RenderOptions.ProcessRenderMode = RenderMode.Default;

            DispatcherUnhandledException += OnDispatcherUnhandledException;
            AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
            SessionEnding += OnSessionEnding;

            base.OnStartup(e);

            try
            {
                _settings = SettingsService.Load();

                _wallpaper = new WallpaperWindow();
                _wallpaper.Show();
                _wallpaper.ApplySettings(_settings);

                _panel = new ControlPanel(_settings, _wallpaper);
                _panel.Show();
                _panel.CheckForUpdatesSilently();

                _tray = new TrayIcon(
                    onOpenSettings: () => _panel.ShowFromTray(),
                    onTogglePlayPause: () => _wallpaper.TogglePlayPause(),
                    onExit: () =>
                    {
                        _panel.PrepareForExit();
                        Shutdown();
                    });

                StartShowSignalListener();
            }
            catch (Exception ex)
            {
                Log("STARTUP EXCEPTION: " + ex);
                MessageBox.Show(ex.ToString(), "Başlatma hatası", MessageBoxButton.OK, MessageBoxImage.Error);
                Shutdown();
            }
        }

        protected override void OnExit(ExitEventArgs e)
        {
            _tray?.Dispose();
            try { _showSignal?.Dispose(); } catch { }
            _showSignal = null;
            try { _mutex?.ReleaseMutex(); } catch { }
            try { _mutex?.Dispose(); } catch { }
            base.OnExit(e);
        }

        /// <summary>
        /// Zaten çalışan örneğe, yönetim panelini göstermesi için sinyal gönderir.
        /// </summary>
        private void TryShowExistingInstance()
        {
            try
            {
                using (var signal = EventWaitHandle.OpenExisting(ShowSignalName))
                {
                    signal.Set();
                }
            }
            catch
            {
                // Sinyal yoksa yok say; yine de "zaten çalışıyor" bilgisi gösterilir.
            }
        }

        private void StartShowSignalListener()
        {
            var thread = new Thread(() =>
            {
                while (true)
                {
                    EventWaitHandle signal = _showSignal;
                    if (signal == null)
                        break;

                    try
                    {
                        signal.WaitOne();
                    }
                    catch
                    {
                        break;
                    }

                    try
                    {
                        Dispatcher.BeginInvoke(new Action(() => _panel?.ShowFromTray()));
                    }
                    catch
                    {
                        break;
                    }
                }
            });
            thread.IsBackground = true;
            thread.Start();
        }

        private void OnSessionEnding(object sender, SessionEndingCancelEventArgs e)
        {
            _panel?.PrepareForExit();
        }

        private void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
        {
            Log("DISPATCHER EXCEPTION: " + e.Exception);
            e.Handled = true;
        }

        private void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
        {
            Log("APPDOMAIN EXCEPTION: " + e.ExceptionObject);
        }

        private static void Log(string message)
        {
            try
            {
                string path = Path.Combine(AppContext.BaseDirectory, "startup.log");
                File.AppendAllText(path, DateTime.Now.ToString("HH:mm:ss") + "  " + message + Environment.NewLine);
            }
            catch
            {
                // Log yazılamazsa yok say.
            }
        }
    }
}
