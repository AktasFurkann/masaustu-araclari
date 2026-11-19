// ApexTube Video Yakalayıcı - arka plan
// Sekmelerin ağ isteklerini izler; video akışı olan yanıtları sekme bazında listeler.

const MAX_PER_TAB = 50;
// Reklam ve önizleme gibi küçük video dosyalarını listeye almamak için alt sınır.
const MIN_VIDEO_BYTES = 300 * 1024;

const PLAYLIST_TYPES = {
  "application/vnd.apple.mpegurl": "HLS",
  "application/x-mpegurl": "HLS",
  "audio/mpegurl": "HLS",
  "audio/x-mpegurl": "HLS",
  "application/dash+xml": "DASH",
};
// HLS/DASH parçaları ayrı video sayılmaz; ana çalma listesi zaten yakalanır.
const SEGMENT_TYPES = ["video/mp2t", "video/iso.segment", "audio/", "text/"];
const SEGMENT_EXT = /\.(ts|m4s|m4a|aac|vtt|key|jpg|png)(\?|#|$)/i;
const PLAYLIST_EXT = [
  [/\.m3u8(\?|#|$)/i, "HLS"],
  [/\.mpd(\?|#|$)/i, "DASH"],
];
const VIDEO_EXT = /\.(mp4|webm|m4v|mov|mkv)(\?|#|$)/i;

// requestId -> istek başlıkları (Referer, Origin, User-Agent); yanıt gelince kullanılır.
const pendingHeaders = new Map();
// tabId -> yakalanan videolar. Service worker uyuyup uyanabildiği için storage.session'a da yazılır.
const cache = new Map();
let queue = Promise.resolve();

function serialize(task) {
  queue = queue.then(task, task);
  return queue;
}

async function loadTab(tabId) {
  if (!cache.has(tabId)) {
    const key = `tab_${tabId}`;
    const stored = await chrome.storage.session.get(key);
    cache.set(tabId, stored[key] || []);
  }
  return cache.get(tabId);
}

async function saveTab(tabId, items) {
  cache.set(tabId, items);
  await chrome.storage.session.set({ [`tab_${tabId}`]: items });
  await chrome.action.setBadgeText({ tabId, text: items.length ? String(items.length) : "" });
  await chrome.action.setBadgeBackgroundColor({ tabId, color: "#2563EB" });
}

function header(list, name) {
  const found = (list || []).find((h) => h.name.toLowerCase() === name);
  return found ? found.value : "";
}

function totalSize(responseHeaders) {
  const range = header(responseHeaders, "content-range"); // "bytes 0-999/123456"
  const total = range.split("/")[1];
  if (total && total !== "*") return Number(total);
  return Number(header(responseHeaders, "content-length")) || 0;
}

function classify(url, contentType) {
  const type = contentType.split(";")[0].trim().toLowerCase();
  if (PLAYLIST_TYPES[type]) return PLAYLIST_TYPES[type];
  // Bazı sunucular çalma listelerini text/plain veya octet-stream olarak gönderir; uzantıya bakılır.
  for (const [pattern, kind] of PLAYLIST_EXT) {
    if (pattern.test(url)) return kind;
  }
  if (SEGMENT_EXT.test(url) || SEGMENT_TYPES.some((t) => type.startsWith(t))) return null;
  if (VIDEO_EXT.test(url) || type.startsWith("video/")) return "Video";
  return null;
}

chrome.webRequest.onSendHeaders.addListener(
  (details) => {
    if (details.tabId < 0) return;
    pendingHeaders.set(details.requestId, {
      referer: header(details.requestHeaders, "referer"),
      origin: header(details.requestHeaders, "origin"),
      user_agent: header(details.requestHeaders, "user-agent"),
    });
  },
  { urls: ["<all_urls>"], types: ["xmlhttprequest", "media", "other"] },
  ["requestHeaders", "extraHeaders"]
);

chrome.webRequest.onHeadersReceived.addListener(
  (details) => {
    const sent = pendingHeaders.get(details.requestId) || {};
    pendingHeaders.delete(details.requestId);
    if (details.tabId < 0 || details.statusCode >= 400) return;

    const kind = classify(details.url, header(details.responseHeaders, "content-type"));
    if (!kind) return;
    const size = totalSize(details.responseHeaders);
    if (kind === "Video" && size && size < MIN_VIDEO_BYTES) return;

    serialize(async () => {
      const items = await loadTab(details.tabId);
      if (items.some((item) => item.url === details.url)) return;
      items.push({ url: details.url, kind, size, ...sent, time: Date.now() });
      await saveTab(details.tabId, items.slice(-MAX_PER_TAB));
    });
  },
  { urls: ["<all_urls>"], types: ["xmlhttprequest", "media", "other"] },
  ["responseHeaders"]
);

chrome.webRequest.onErrorOccurred.addListener(
  (details) => pendingHeaders.delete(details.requestId),
  { urls: ["<all_urls>"] }
);

// Sekme başka bir sayfaya geçince eski sayfanın videoları listeden silinir.
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "loading" && changeInfo.url) {
    serialize(() => saveTab(tabId, []));
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  serialize(async () => {
    cache.delete(tabId);
    await chrome.storage.session.remove(`tab_${tabId}`);
  });
});
