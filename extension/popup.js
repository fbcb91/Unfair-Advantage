const DEFAULT_BACKEND = "http://localhost:8000";
const TONE_DESCS = {
  diretto:   "Va al sodo, sicuro di sé",
  curioso:   "Fa domande genuine, interessato alla sua storia",
  giocoso:   "Leggero e ironico, un pizzico di umorismo",
  romantico: "Caldo e sincero, si sente l'interesse",
};

let selectedTone = "curioso";
let currentUsername = null;
let currentProfileData = null;

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const username = extractUsername(tab?.url || "");

  if (!username) {
    show("notOnProfile");
    return;
  }

  currentUsername = username;
  show("mainUi");
  updateProfilePreview(username, null);
});

function extractUsername(url) {
  const m = url.match(/^https:\/\/(?:www\.)?instagram\.com\/([^/?#]+)\/?(?:\?.*)?$/);
  if (!m) return null;
  const reserved = new Set([
    "explore", "reels", "stories", "direct", "accounts", "p",
    "tv", "reel", "live", "ar", "audio",
  ]);
  return reserved.has(m[1]) ? null : m[1];
}

// ── Tone ──────────────────────────────────────────────────────────────────

function selectTone(el) {
  document.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
  el.classList.add("active");
  selectedTone = el.dataset.tone;
}

// ── Analysis flow ─────────────────────────────────────────────────────────

async function analyze() {
  hide("resultsSection");
  hide("errorSection");
  show("loadingSection");
  document.getElementById("analyzeBtn").disabled = true;

  try {
    // Step 1: extract profile data from Instagram via content script
    setLoadingText("Caricamento profilo Instagram...");
    const profileData = await extractProfileFromTab();

    if (profileData.error) {
      if (profileData.error.toLowerCase().includes("login")) {
        show("notLoggedIn"); hide("mainUi"); return;
      }
      throw new Error(profileData.error);
    }

    if (profileData.is_private) {
      showError("Questo profilo è privato 🔒\nNon è possibile analizzarlo.");
      return;
    }

    currentProfileData = profileData;
    updateProfilePreview(
      profileData.username,
      profileData.profile_pic_url,
      profileData.full_name,
      profileData.follower_count
    );

    // Step 2: send to backend for Claude analysis
    setLoadingText("Analisi AI in corso...");
    const result = await callBackend(profileData, selectedTone);

    showResults(result);

  } catch (err) {
    showError(err.message || "Errore sconosciuto");
  } finally {
    hide("loadingSection");
    document.getElementById("analyzeBtn").disabled = false;
  }
}

async function extractProfileFromTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tab.id, { action: "extractProfile", username: currentUsername }, resolve);
  });
}

async function callBackend(profileData, tone) {
  const { backendUrl } = await chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND });
  const url = backendUrl.replace(/\/$/, "");

  const res = await fetch(`${url}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile: profileData, tone }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Errore server (${res.status})`);
  }

  return res.json();
}

// ── UI helpers ────────────────────────────────────────────────────────────

function showResults(result) {
  hide("loadingSection");
  show("resultsSection");

  if (result.profile_summary) {
    document.getElementById("summaryText").textContent = result.profile_summary;
    show("summaryBlock");
  }

  const hooksList = document.getElementById("hooksList");
  hooksList.innerHTML = "";
  if (result.hooks?.length) {
    result.hooks.forEach(h => {
      const li = document.createElement("li");
      li.className = "text-xs text-gray-500";
      li.textContent = "• " + h;
      hooksList.appendChild(li);
    });
    show("hooksBlock");
  }

  const msgList = document.getElementById("messagesList");
  msgList.innerHTML = "";
  (result.messages || []).forEach((msg, i) => {
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="msg-box">${esc(msg)}</div>
      <div class="flex justify-end mt-1">
        <button class="copy-btn" data-msg="${esc(msg)}" onclick="copyMsg(this)">Copia</button>
      </div>`;
    msgList.appendChild(wrap);
  });
}

function copyMsg(btn) {
  const text = btn.dataset.msg;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = "Copiato ✓";
    btn.classList.add("copied");
    setTimeout(() => { btn.textContent = "Copia"; btn.classList.remove("copied"); }, 2000);
  });
}

function updateProfilePreview(username, picUrl, fullName, followerCount) {
  const avatarEl = document.getElementById("profileAvatar");
  if (picUrl) {
    avatarEl.outerHTML = `<img id="profileAvatar" src="${picUrl}" class="avatar"
      onerror="this.outerHTML='<div id=\\'profileAvatar\\' class=\\'avatar-ph\\'>👤</div>'" />`;
  }
  document.getElementById("profileName").textContent = fullName || `@${username}`;
  const meta = followerCount
    ? `@${username} · ${fmt(followerCount)} follower`
    : `@${username}`;
  document.getElementById("profileMeta").textContent = meta;
}

function showError(msg) {
  document.getElementById("errorText").textContent = msg;
  show("errorSection");
}

function resetAndAnalyze() {
  hide("resultsSection");
  analyze();
}

function retryFromError() {
  hide("errorSection");
  analyze();
}

function setLoadingText(msg) {
  document.getElementById("loadingText").textContent = msg;
}

function show(id) { document.getElementById(id)?.classList.remove("hidden"); }
function hide(id) { document.getElementById(id)?.classList.add("hidden"); }
function openOptions() { chrome.runtime.openOptionsPage(); }
function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function fmt(n) {
  if (n >= 1e6) return (n/1e6).toFixed(1)+"M";
  if (n >= 1e3) return (n/1e3).toFixed(1)+"K";
  return String(n);
}
