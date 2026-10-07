using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Reflection;
using System.Text.Json;
using System.Threading.Tasks;

namespace WallpaperApp
{
    /// <summary>
    /// GitHub Releases üzerinden güncelleme kontrolü, kurulum dosyasını indirme ve sessiz kurulum.
    /// </summary>
    internal static class Updater
    {
        private const string Repo = "AktasFurkann/masaustu-araclari";
        private const string LatestReleaseApi = "https://api.github.com/repos/" + Repo + "/releases/latest";

        private static readonly HttpClient Http = CreateClient();

        public sealed class UpdateInfo
        {
            public Version Version { get; init; }
            public string DownloadUrl { get; init; }
        }

        public static Version CurrentVersion
        {
            get
            {
                Version v = Assembly.GetEntryAssembly()?.GetName().Version ?? new Version(0, 0, 0);
                return new Version(v.Major, v.Minor, Math.Max(v.Build, 0));
            }
        }

        /// <summary>Daha yeni bir sürüm varsa bilgisini, yoksa null döner.</summary>
        public static async Task<UpdateInfo> CheckAsync()
        {
            using HttpResponseMessage resp = await Http.GetAsync(LatestReleaseApi);
            if (resp.StatusCode == HttpStatusCode.NotFound)
                return null; // henüz hiç sürüm yayınlanmamış
            resp.EnsureSuccessStatusCode();

            using JsonDocument doc = JsonDocument.Parse(await resp.Content.ReadAsStringAsync());
            JsonElement root = doc.RootElement;

            string tag = root.GetProperty("tag_name").GetString()?.TrimStart('v', 'V');
            if (!Version.TryParse(tag, out Version latest) || latest <= CurrentVersion)
                return null;

            string url = root.GetProperty("assets").EnumerateArray()
                .Where(a => a.GetProperty("name").GetString()?.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) == true)
                .Select(a => a.GetProperty("browser_download_url").GetString())
                .FirstOrDefault();

            return url == null ? null : new UpdateInfo { Version = latest, DownloadUrl = url };
        }

        public static async Task<string> DownloadAsync(UpdateInfo update, IProgress<int> percent)
        {
            string path = Path.Combine(Path.GetTempPath(), $"MasaustuAraclari-Setup-{update.Version}.exe");

            using HttpResponseMessage resp = await Http.GetAsync(update.DownloadUrl, HttpCompletionOption.ResponseHeadersRead);
            resp.EnsureSuccessStatusCode();
            long total = resp.Content.Headers.ContentLength ?? 0;

            await using Stream source = await resp.Content.ReadAsStreamAsync();
            await using FileStream target = File.Create(path);
            byte[] buffer = new byte[256 * 1024];
            long done = 0;
            int read;
            while ((read = await source.ReadAsync(buffer)) > 0)
            {
                await target.WriteAsync(buffer.AsMemory(0, read));
                done += read;
                if (total > 0)
                    percent?.Report((int)(done * 100 / total));
            }
            return path;
        }

        /// <summary>Kurulumu sessiz modda başlatır; kurulum açık programları kapatıp günceller ve yeniden açar.</summary>
        public static void RunInstaller(string path)
        {
            Process.Start(new ProcessStartInfo(path, "/SILENT /SUPPRESSMSGBOXES /NORESTART /RESTART=wallpaper") { UseShellExecute = true });
        }

        private static HttpClient CreateClient()
        {
            var client = new HttpClient { Timeout = TimeSpan.FromMinutes(10) };
            client.DefaultRequestHeaders.UserAgent.ParseAdd("HareketliDuvarKagidi-Updater");
            client.DefaultRequestHeaders.Accept.ParseAdd("application/vnd.github+json");
            return client;
        }
    }
}
