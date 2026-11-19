// ApexTube Video Yakalayıcı - açılır pencere

// config.py içindeki BRIDGE_PORT ile aynı olmalı.
const APEXTUBE = "http://127.0.0.1:47321";

const listEl = document.getElementById("list");
const toastEl = document.getElementById("toast");

function toast(text, cls = "") {
  toastEl.textContent = text;
  toastEl.className = `toast ${cls}`;
}

function formatSize(bytes) {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return `${bytes.toFixed(i >= 2 ? 1 : 0)} ${units[i]}`;
}

function displayName(url) {
  try {
    const u = new URL(url);
    const file = decodeURIComponent(u.pathname.split("/").filter(Boolean).pop() || u.hostname);
    return { file, host: u.hostname };
  } catch {
    return { file: url, host: "" };
  }
}

async function fetchWithTimeout(url, options = {}, ms = 1500) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function checkApexTube() {
  const dot = document.getElementById("dot");
  const status = document.getElementById("status");
  try {
    const res = await fetchWithTimeout(`${APEXTUBE}/ping`);
    const data = res.ok ? await res.json() : {};
    if (!data.ok) throw new Error(`HTTP ${res.status}`);
    dot.className = "dot on";
    status.textContent = `ApexTube v${data.version} bağlı`;
  } catch {
    dot.className = "dot off";
    status.textContent = "ApexTube kapalı";
  }
}

async function sendToApexTube(item, tab, button) {
  button.disabled = true;
  try {
    const res = await fetchWithTimeout(`${APEXTUBE}/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: item.url,
        referer: item.referer || tab.url,
        origin: item.origin,
        user_agent: item.user_agent || navigator.userAgent,
        title: tab.title,
        page_url: tab.url,
      }),
    }, 3000);
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      toast("ApexTube'a gönderildi. Kaliteyi seçip indirmeyi başlatabilirsin.", "ok");
    } else {
      toast(`ApexTube bağlantıyı kabul etmedi: ${data.error || `HTTP ${res.status}`}`, "err");
    }
  } catch {
    toast("ApexTube'a ulaşılamadı. Programı açıp tekrar dene.", "err");
  } finally {
    button.disabled = false;
  }
}

function renderEmpty() {
  listEl.innerHTML = `
    <div class="empty">
      <strong>Bu sayfada henüz video bulunamadı</strong>
      Videoyu oynatmaya başlat, sonra bu pencereyi tekrar aç.<br>
      DRM korumalı servislerdeki videolar indirilemez.
    </div>`;
}

// "index.m3u8", "nl.php", "video?id=..." gibi adlar videoyu tanıtmaz; bunlarda sekme başlığı gösterilir.
const MEDIA_FILE = /\.(m3u8|mpd|mp4|webm|m4v|mov|mkv)$/i;
const GENERIC_NAMES = /^(index|master|playlist|manifest|chunklist|media|video|stream|main|prog_index)(_[\w-]+)?\./i;

function meaningfulFile(file) {
  return MEDIA_FILE.test(file) && !GENERIC_NAMES.test(file) ? file : "";
}

function renderItem(item, tab, number) {
  const { file, host } = displayName(item.url);
  const el = document.createElement("div");
  el.className = "item";
  el.innerHTML = `
    <div class="row"><span class="kind"></span><span class="name"></span></div>
    <div class="meta"></div>
    <div class="actions">
      <button class="primary">⬇ ApexTube ile indir</button>
      <button class="copy" title="Bağlantıyı kopyala">Kopyala</button>
    </div>`;
  const kind = el.querySelector(".kind");
  kind.textContent = item.kind;
  kind.classList.add(item.kind);
  const name = meaningfulFile(file) || tab.title || file;
  el.querySelector(".name").textContent = name;
  el.querySelector(".name").title = `${name}\n${item.url}`;
  el.querySelector(".meta").textContent =
    [`#${number}`, host, name === file ? "" : meaningfulFile(file), formatSize(item.size)].filter(Boolean).join(" • ");

  const sendBtn = el.querySelector(".primary");
  sendBtn.addEventListener("click", () => sendToApexTube(item, tab, sendBtn));
  el.querySelector(".copy").addEventListener("click", async () => {
    await navigator.clipboard.writeText(item.url);
    toast("Bağlantı kopyalandı.", "ok");
  });
  return el;
}

async function init() {
  checkApexTube();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return renderEmpty();

  const key = `tab_${tab.id}`;
  const stored = await chrome.storage.session.get(key);
  const items = stored[key] || [];
  if (!items.length) return renderEmpty();

  // Çalma listeleri (HLS/DASH) tüm kaliteleri içerdiği için önce gösterilir.
  const order = { HLS: 0, DASH: 1, Video: 2 };
  items.sort((a, b) => order[a.kind] - order[b.kind] || a.time - b.time);
  const children = items.map((item, i) => renderItem(item, tab, i + 1));
  if (items.length > 1) {
    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent =
      "Aynı videonun farklı kaliteleri ayrı satırlar olarak görünebilir. İlk satır genelde tüm kaliteleri " +
      "içerir; ApexTube analizden sonra hangi kalitelerin olduğunu gösterir.";
    children.unshift(hint);
  }
  listEl.replaceChildren(...children);
}

init();
