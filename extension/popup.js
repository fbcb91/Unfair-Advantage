const DEFAULT_BACKEND = "http://localhost:8000";

let selectedTone = "curioso";
let selectedChar = "";      // empty = no character (use tone)
let activeMode = "tone";    // "tone" | "char"
let currentUsername = null;
let cachedProfileData = null;

const CHAR_LABELS = {
  chuck_bass: "Chuck Bass",
  damon_salvatore: "Damon Salvatore",
  hitch: "Hitch",
  harvey_specter: "Harvey Specter",
  michael_scott: "Stile Selvaggio",
};

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const username = extractUsername(tab?.url || "");

  if (!username) {
    show("notOnProfile");
    return;
  }

  currentUsername = username;
  show("mainUi");
  setProfilePreview(username, null, null, null);
});

function bindEvents() {
  // Header
  document.getElementById("settingsBtn").addEventListener("click", () => chrome.runtime.openOptionsPage());

  // Not-on-profile / not-logged-in links
  document.getElementById("openIgBtn").addEventListener("click", () =>
    chrome.tabs.create({ url: "https://www.instagram.com" }));
  document.getElementById("igLoginBtn").addEventListener("click", () =>
    chrome.tabs.create({ url: "https://www.instagram.com/accounts/login/" }));

  // Mode tabs
  document.getElementById("modeToneTab").addEventListener("click", () => switchMode("tone"));
  document.getElementById("modeCharTab").addEventListener("click", () => switchMode("char"));

  // Tone pills
  document.querySelectorAll(".pill").forEach(pill => {
    pill.addEventListener("click", () => {
      selectTone(pill);
      if (cachedProfileData && !document.getElementById("resultsSection").classList.contains("hidden")) {
        analyzeWithCache();
      }
    });
  });

  // Character cards
  document.querySelectorAll(".char-card").forEach(card => {
    card.addEventListener("click", () => {
      selectChar(card);
      if (cachedProfileData && !document.getElementById("resultsSection").classList.contains("hidden")) {
        analyzeWithCache();
      }
    });
  });

  // Main buttons
  document.getElementById("analyzeBtn").addEventListener("click", analyze);
  document.getElementById("regenBtn").addEventListener("click", () => {
    hide("resultsSection");
    analyzeWithCache();
  });
  document.getElementById("retryBtn").addEventListener("click", () => {
    hide("errorSection");
    analyze();
  });

  // Copy buttons — event delegation
  document.getElementById("messagesList").addEventListener("click", e => {
    const btn = e.target.closest(".copy-btn");
    if (btn) copyMsg(btn);
  });
}

// ── Mode / tone / character ───────────────────────────────────────────────

function switchMode(mode) {
  activeMode = mode;

  const toneTab = document.getElementById("modeToneTab");
  const charTab = document.getElementById("modeCharTab");
  const tonePanel = document.getElementById("tonePanel");
  const charPanel = document.getElementById("charPanel");

  if (mode === "tone") {
    toneTab.classList.add("active");
    charTab.classList.remove("active");
    tonePanel.classList.remove("hidden");
    charPanel.classList.add("hidden");
    selectedChar = "";
  } else {
    charTab.classList.add("active");
    toneTab.classList.remove("active");
    charPanel.classList.remove("hidden");
    tonePanel.classList.add("hidden");
    // auto-select first char if none selected
    if (!selectedChar) {
      const first = document.querySelector(".char-card");
      if (first) selectChar(first);
    }
  }

  if (cachedProfileData && !document.getElementById("resultsSection").classList.contains("hidden")) {
    analyzeWithCache();
  }
}

function selectTone(el) {
  document.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
  el.classList.add("active");
  selectedTone = el.dataset.tone;
}

function selectChar(el) {
  document.querySelectorAll(".char-card").forEach(c => c.classList.remove("active"));
  el.classList.add("active");
  selectedChar = el.dataset.char;
}

// ── Helpers ───────────────────────────────────────────────────────────────

function extractUsername(url) {
  const m = url.match(/^https:\/\/(?:www\.)?instagram\.com\/([^/?#]+)\/?(?:\?.*)?$/);
  if (!m) return null;
  const reserved = new Set([
    "explore","reels","stories","direct","accounts","p","tv","reel","live","ar","audio",
  ]);
  return reserved.has(m[1]) ? null : m[1];
}

function show(id) { document.getElementById(id)?.classList.remove("hidden"); }
function hide(id) { document.getElementById(id)?.classList.add("hidden"); }

function setLoadingText(msg) {
  document.getElementById("loadingText").textContent = msg;
}

function fmt(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return String(n);
}

// ── Profile preview ───────────────────────────────────────────────────────

function setProfilePreview(username, picUrl, fullName, followerCount) {
  document.getElementById("profileName").textContent = fullName || `@${username}`;
  document.getElementById("profileMeta").textContent =
    followerCount ? `@${username} · ${fmt(followerCount)} follower` : `@${username}`;

  if (picUrl) {
    const avatarEl = document.getElementById("profileAvatar");
    const img = document.createElement("img");
    img.className = "avatar";
    img.src = picUrl;
    img.alt = "";
    img.onerror = () => { img.replaceWith(makePh()); };
    avatarEl.replaceWith(img);
    img.id = "profileAvatar";
  }
}

function makePh() {
  const d = document.createElement("div");
  d.className = "avatar-ph";
  d.id = "profileAvatar";
  d.textContent = "👤";
  return d;
}

// ── Analysis ──────────────────────────────────────────────────────────────

async function analyze() {
  if (cachedProfileData) {
    await analyzeWithCache();
    return;
  }

  hide("resultsSection");
  hide("errorSection");
  show("loadingSection");

  const btn = document.getElementById("analyzeBtn");
  btn.disabled = true;

  try {
    setLoadingText("Caricamento profilo Instagram...");
    const profileData = await extractProfileFromTab();

    if (!profileData) throw new Error("Nessuna risposta dal content script. Ricarica la pagina Instagram e riprova.");
    if (profileData.error) {
      if (profileData.error.toLowerCase().includes("login")) {
        hide("mainUi"); show("notLoggedIn"); return;
      }
      throw new Error(profileData.error);
    }
    if (profileData.is_private) {
      showError("Questo profilo è privato 🔒\nImpossibile analizzarlo.");
      return;
    }

    cachedProfileData = profileData;
    setProfilePreview(profileData.username, profileData.profile_pic_url, profileData.full_name, profileData.follower_count);

    setLoadingText("Analisi AI in corso...");
    const result = await callBackend(profileData);
    showResults(result);

  } catch (err) {
    showError(err.message || "Errore sconosciuto");
  } finally {
    hide("loadingSection");
    btn.disabled = false;
  }
}

async function analyzeWithCache() {
  hide("resultsSection");
  hide("errorSection");
  show("loadingSection");
  setLoadingText("Rigenerazione in corso...");

  const btn = document.getElementById("analyzeBtn");
  btn.disabled = true;

  try {
    const result = await callBackend(cachedProfileData);
    showResults(result);
  } catch (err) {
    showError(err.message || "Errore sconosciuto");
  } finally {
    hide("loadingSection");
    btn.disabled = false;
  }
}

async function extractProfileFromTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return new Promise(resolve => {
    chrome.tabs.sendMessage(tab.id, { action: "extractProfile", username: currentUsername }, response => {
      if (chrome.runtime.lastError) {
        resolve({ error: "Ricarica la pagina Instagram e riprova." });
      } else {
        resolve(response);
      }
    });
  });
}

async function callBackend(profileData) {
  const { backendUrl, userInfo } = await chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND, userInfo: "" });
  const url = backendUrl.replace(/\/$/, "");

  const body = {
    profile: profileData,
    tone: activeMode === "tone" ? selectedTone : "curioso",
    character: activeMode === "char" ? selectedChar : "",
    user_info: userInfo || "",
  };

  const res = await fetch(`${url}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Errore server (${res.status})`);
  }
  return res.json();
}

// ── Results rendering ─────────────────────────────────────────────────────

function showResults(result) {
  hide("loadingSection");
  show("resultsSection");

  // Summary
  const summaryEl = document.getElementById("summaryText");
  if (result.profile_summary) {
    summaryEl.textContent = result.profile_summary;
    show("summaryBlock");
  } else {
    hide("summaryBlock");
  }

  // Hooks
  const hooksList = document.getElementById("hooksList");
  hooksList.innerHTML = "";
  if (result.hooks?.length) {
    result.hooks.forEach(h => {
      const li = document.createElement("li");
      li.className = "text-xs gray-500";
      li.style.listStyle = "none";
      li.textContent = "• " + h;
      hooksList.appendChild(li);
    });
    show("hooksBlock");
  } else {
    hide("hooksBlock");
  }

  // Character badge
  const badge = document.getElementById("charBadge");
  if (activeMode === "char" && selectedChar && CHAR_LABELS[selectedChar]) {
    badge.textContent = CHAR_LABELS[selectedChar];
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }

  // Messages
  const msgList = document.getElementById("messagesList");
  msgList.innerHTML = "";
  (result.messages || []).forEach((msg) => {
    const wrap = document.createElement("div");

    const box = document.createElement("div");
    box.className = "msg-box";
    box.textContent = msg;

    const row = document.createElement("div");
    row.className = "clearfix";

    const btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.textContent = "Copia";
    btn.dataset.msg = msg;

    row.appendChild(btn);
    wrap.appendChild(box);
    wrap.appendChild(row);
    msgList.appendChild(wrap);
  });
}

function copyMsg(btn) {
  const text = btn.dataset.msg || "";
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = "Copiato ✓";
    btn.classList.add("copied");
    setTimeout(() => {
      btn.textContent = "Copia";
      btn.classList.remove("copied");
    }, 2000);
  });
}

function showError(msg) {
  document.getElementById("errorText").textContent = msg;
  show("errorSection");
}
