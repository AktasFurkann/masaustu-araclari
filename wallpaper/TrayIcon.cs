using System;
using System.Drawing;
using System.Windows.Forms;

namespace WallpaperApp
{
    /// <summary>
    /// Sistem tepsisi (notification area) entegrasyonu.
    /// Sağ tık: "Ayarları Aç", "Videoyu Duraklat / Oynat", "Çıkış".
    /// </summary>
    internal sealed class TrayIcon : IDisposable
    {
        private readonly NotifyIcon _notifyIcon;

        public TrayIcon(Action onOpenSettings, Action onTogglePlayPause, Action onExit)
        {
            var menu = new ContextMenuStrip();
            menu.Items.Add("Ayarları Aç", null, (_, _) => onOpenSettings());
            menu.Items.Add("Videoyu Duraklat / Oynat", null, (_, _) => onTogglePlayPause());
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("Çıkış", null, (_, _) => onExit());

            _notifyIcon = new NotifyIcon
            {
                Icon = LoadAppIcon(),
                Text = "Hareketli Duvar Kağıdı",
                ContextMenuStrip = menu,
                Visible = true
            };

            _notifyIcon.DoubleClick += (_, _) => onOpenSettings();
        }

        private static Icon LoadAppIcon()
        {
            try
            {
                string path = Environment.ProcessPath;
                if (!string.IsNullOrEmpty(path))
                {
                    Icon icon = Icon.ExtractAssociatedIcon(path);
                    if (icon != null)
                        return icon;
                }
            }
            catch
            {
                // İkon alınamazsa varsayılanı kullan.
            }
            return SystemIcons.Application;
        }

        public void Dispose()
        {
            _notifyIcon.Visible = false;
            _notifyIcon.Dispose();
        }
    }
}
