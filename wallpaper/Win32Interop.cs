using System;
using System.Runtime.InteropServices;
using System.Text;

namespace WallpaperApp
{
    /// <summary>
    /// user32.dll sarmalayıcıları: masaüstü katmanına (WorkerW) gömme,
    /// tam ekran tespiti ve sanal masaüstü ölçüleri.
    /// </summary>
    internal static class Win32Interop
    {
        #region Sabitler

        public const int GWL_EXSTYLE = -20;

        public const int WS_EX_NOACTIVATE = 0x08000000;
        public const int WS_EX_TOOLWINDOW = 0x00000080;
        public const int WS_EX_TRANSPARENT = 0x00000020;

        private const int DWMWA_CLOAKED = 14;
        private const int SM_CMONITORS = 80;

        public const uint SMTO_NORMAL = 0x0000;
        public const uint SMTO_ABORTIFHUNG = 0x0002;

        public const int HWND_BOTTOM = 1;

        public const uint SWP_NOSIZE = 0x0001;
        public const uint SWP_NOMOVE = 0x0002;
        public const uint SWP_NOZORDER = 0x0004;
        public const uint SWP_NOACTIVATE = 0x0010;
        public const uint SWP_SHOWWINDOW = 0x0040;

        public const uint MONITOR_DEFAULTTONEAREST = 2;

        public const int SM_XVIRTUALSCREEN = 76;
        public const int SM_YVIRTUALSCREEN = 77;
        public const int SM_CXVIRTUALSCREEN = 78;
        public const int SM_CYVIRTUALSCREEN = 79;

        // Birincil ekran çözünürlüğü (çözünürlük algılama için)
        public const int SM_CXSCREEN = 0;
        public const int SM_CYSCREEN = 1;

        #endregion

        #region Yapılar

        [StructLayout(LayoutKind.Sequential)]
        public struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        public struct MONITORINFO
        {
            public int cbSize;
            public RECT rcMonitor;
            public RECT rcWork;
            public uint dwFlags;
        }

        #endregion

        #region Delegeler

        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        #endregion

        #region P/Invoke

        [DllImport("user32.dll", SetLastError = true)]
        public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern IntPtr FindWindowEx(IntPtr hWndParent, IntPtr hWndChildAfter, string lpszClass, string lpszWindow);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern IntPtr SetParent(IntPtr hWndChild, IntPtr hWndNewParent);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam, uint fuFlags, uint uTimeout, out IntPtr lpdwResult);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

        [DllImport("user32.dll")]
        public static extern IntPtr MonitorFromWindow(IntPtr hwnd, uint dwFlags);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFO lpmi);

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        [DllImport("user32.dll")]
        public static extern int GetSystemMetrics(int nIndex);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool IsIconic(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll")]
        public static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool IsZoomed(IntPtr hWnd);

        [DllImport("dwmapi.dll")]
        private static extern int DwmGetWindowAttribute(IntPtr hwnd, int dwAttribute, out int pvAttribute, int cbAttribute);

        #endregion

        #region Yardımcılar

        /// <summary>
        /// Masaüstü ikonlarının ARKASINDAKİ WorkerW penceresini bulur.
        /// 0x052C mesajı Progman'a arka plan WorkerW'sini oluşturmasını söyler.
        /// </summary>
        public static IntPtr FindWorkerW()
        {
            IntPtr progman = FindWindow("Progman", null);
            if (progman == IntPtr.Zero)
                return IntPtr.Zero;

            SendMessageTimeout(progman, 0x052C, IntPtr.Zero, IntPtr.Zero,
                SMTO_NORMAL | SMTO_ABORTIFHUNG, 1000, out _);

            IntPtr workerw = IntPtr.Zero;

            // İkonları tutan (SHELLDLL_DefView içeren) WorkerW'nin ardından gelen WorkerW'yi bul.
            EnumWindows((top, lParam) =>
            {
                IntPtr defView = FindWindowEx(top, IntPtr.Zero, "SHELLDLL_DefView", null);
                if (defView != IntPtr.Zero)
                {
                    workerw = FindWindowEx(IntPtr.Zero, top, "WorkerW", null);
                    return false; // numaralandırmayı durdur
                }
                return true;
            }, IntPtr.Zero);

            return workerw;
        }

        /// <summary>
        /// Bir pencerenin, bulunduğu monitörü tamamen kaplayıp kaplamadığını döndürür
        /// (tam ekran uygulama/oyun tespiti).
        /// </summary>
        public static bool IsFullscreen(IntPtr hWnd)
        {
            if (hWnd == IntPtr.Zero || IsIconic(hWnd))
                return false;

            IntPtr monitor = MonitorFromWindow(hWnd, MONITOR_DEFAULTTONEAREST);
            if (monitor == IntPtr.Zero)
                return false;

            var monitorInfo = new MONITORINFO { cbSize = Marshal.SizeOf(typeof(MONITORINFO)) };
            if (!GetMonitorInfo(monitor, ref monitorInfo))
                return false;

            if (!GetWindowRect(hWnd, out RECT rect))
                return false;

            return rect.Left <= monitorInfo.rcMonitor.Left &&
                   rect.Top <= monitorInfo.rcMonitor.Top &&
                   rect.Right >= monitorInfo.rcMonitor.Right &&
                   rect.Bottom >= monitorInfo.rcMonitor.Bottom;
        }

        /// <summary>
        /// Bir HWND'nin pencere sınıfı adını döndürür.
        /// </summary>
        public static string GetWindowClassName(IntPtr hWnd)
        {
            if (hWnd == IntPtr.Zero)
                return string.Empty;

            var sb = new StringBuilder(256);
            GetClassName(hWnd, sb, sb.Capacity);
            return sb.ToString();
        }

        /// <summary>
        /// Verilen pencerenin masaüstü kabuğuna ait olup olmadığını söyler
        /// (Progman, WorkerW, SHELLDLL_DefView veya görev çubuğu).
        /// </summary>
        /// <summary>
        /// Duvar kağıdı hiçbir monitörde görünmüyorsa true döner: her monitörde ekranı kaplayan
        /// (büyütülmüş veya tam ekran) görünür bir pencere vardır.
        /// </summary>
        public static bool IsDesktopCovered()
        {
            var coveredMonitors = new System.Collections.Generic.HashSet<IntPtr>();

            EnumWindows((hWnd, lParam) =>
            {
                if (!IsWindowVisible(hWnd) || IsIconic(hWnd) || IsShellWindow(hWnd))
                    return true;

                // Araç pencereleri ve tıklama geçirgen katmanlar (ör. GPU sürücüsü overlay'leri)
                // ekranı kaplasa da masaüstünü gizlemez.
                int exStyle = GetWindowLong(hWnd, GWL_EXSTYLE);
                if ((exStyle & (WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT)) != 0)
                    return true;

                // Görünür bayrağı olup ekranda çizilmeyen (cloaked) pencereler: arka plandaki UWP uygulamaları vb.
                if (DwmGetWindowAttribute(hWnd, DWMWA_CLOAKED, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
                    return true;

                if (IsZoomed(hWnd) || IsFullscreen(hWnd))
                    coveredMonitors.Add(MonitorFromWindow(hWnd, MONITOR_DEFAULTTONEAREST));

                return true;
            }, IntPtr.Zero);

            return coveredMonitors.Count > 0 && coveredMonitors.Count >= GetSystemMetrics(SM_CMONITORS);
        }

        public static bool IsShellWindow(IntPtr hWnd)
        {
            string cls = GetWindowClassName(hWnd);
            return cls == "Progman" ||
                   cls == "WorkerW" ||
                   cls == "SHELLDLL_DefView" ||
                   cls == "Shell_TrayWnd";
        }

        #endregion
    }
}
