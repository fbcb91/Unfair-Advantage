const DEFAULT_BACKEND = "https://unfair-advantage.fly.dev";
const MAX_USER_INFO = 500;

document.addEventListener("DOMContentLoaded", async () => {
  // Load saved backend URL + user info
  const { backendUrl, userInfo } = await chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND, userInfo: "" });
  document.getElementById("backendUrl").value = backendUrl || DEFAULT_BACKEND;
  const ta = document.getElementById("userInfo");
  ta.value = userInfo || "";
  updateCharsLeft(ta.value.length);

  // Check if already logged in
  await refreshAccountView();

  bindEvents();

  // Quiet backend reachability check — show banner if server is down
  const url = (backendUrl || DEFAULT_BACKEND).replace(/\/$/, "");
  try {
    const res = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(6000) });
    if (!res.ok) showAuthStatus("login", "Server non risponde correttamente. Riprova tra poco.", "error");
  } catch {
    showAuthStatus("login", "Server non raggiungibile. Controlla la connessione o riprova tra poco.", "error");
  }
});

function bindEvents() {
  // Auth tabs
  document.getElementById("tabLogin").addEventListener("click", () => switchAuthTab("login"));
  document.getElementById("tabSignup").addEventListener("click", () => switchAuthTab("signup"));

  // Auth forms
  document.getElementById("loginBtn").addEventListener("click", doLogin);
  document.getElementById("signupBtn").addEventListener("click", doSignup);
  document.getElementById("logoutBtn").addEventListener("click", doLogout);
  document.getElementById("upgradeBtn").addEventListener("click", openPricing);

  // Enter key on password fields
  document.getElementById("loginPassword").addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });
  document.getElementById("signupPassword").addEventListener("keydown", e => { if (e.key === "Enter") doSignup(); });

  // Advanced section toggle
  document.getElementById("advancedToggle").addEventListener("click", () => {
    const section = document.getElementById("advancedSection");
    const btn = document.getElementById("advancedToggle");
    const open = !section.classList.contains("hidden");
    section.classList.toggle("hidden", open);
    btn.textContent = open ? "⚙ Impostazioni avanzate" : "⚙ Nascondi impostazioni avanzate";
  });

  // Backend URL
  document.getElementById("saveBtn").addEventListener("click", saveBackend);
  document.getElementById("testBtn").addEventListener("click", testConnection);
  document.getElementById("backendUrl").addEventListener("keydown", e => { if (e.key === "Enter") saveBackend(); });

  // User profile
  document.getElementById("saveProfileBtn").addEventListener("click", saveProfile);
  const ta = document.getElementById("userInfo");
  ta.addEventListener("input", () => {
    if (ta.value.length > MAX_USER_INFO) ta.value = ta.value.slice(0, MAX_USER_INFO);
    updateCharsLeft(ta.value.length);
  });
  document.querySelectorAll(".tag").forEach(tag => {
    tag.addEventListener("click", () => {
      const sep = ta.value && !ta.value.endsWith(" ") && !ta.value.endsWith(".") ? ". " : (ta.value ? " " : "");
      ta.value = (ta.value + sep + tag.dataset.snippet).slice(0, MAX_USER_INFO);
      updateCharsLeft(ta.value.length);
      ta.focus();
    });
  });
}

// ── Auth tab toggle ───────────────────────────────────────────────────────

function switchAuthTab(tab) {
  const loginForm = document.getElementById("loginForm");
  const signupForm = document.getElementById("signupForm");
  const tabLogin = document.getElementById("tabLogin");
  const tabSignup = document.getElementById("tabSignup");

  if (tab === "login") {
    loginForm.classList.remove("hidden"); signupForm.classList.add("hidden");
    tabLogin.classList.add("active"); tabSignup.classList.remove("active");
  } else {
    signupForm.classList.remove("hidden"); loginForm.classList.add("hidden");
    tabSignup.classList.add("active"); tabLogin.classList.remove("active");
  }
}

// ── Auth actions ──────────────────────────────────────────────────────────

async function doLogin() {
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;
  if (!email || !password) { showAuthStatus("login", "Inserisci email e password.", "error"); return; }

  const btn = document.getElementById("loginBtn");
  btn.disabled = true; btn.textContent = "Accesso...";

  try {
    const { backendUrl } = await chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND });
    const url = (backendUrl || DEFAULT_BACKEND).replace(/\/$/, "");
    let res;
    try {
      res = await fetch(`${url}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
    } catch {
      throw new Error("Server non raggiungibile. Controlla la tua connessione.");
    }
    let data;
    try { data = await res.json(); } catch { data = {}; }
    if (!res.ok) throw new Error(data.detail || `Errore ${res.status}. Riprova.`);

    await chrome.storage.sync.set({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      userEmail: data.email,
    });
    await refreshAccountView();
  } catch (err) {
    showAuthStatus("login", err.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "Accedi";
  }
}

async function doSignup() {
  const email = document.getElementById("signupEmail").value.trim();
  const password = document.getElementById("signupPassword").value;
  if (!email || !password) { showAuthStatus("signup", "Inserisci email e password.", "error"); return; }
  if (password.length < 6) { showAuthStatus("signup", "Password min 6 caratteri.", "error"); return; }

  const btn = document.getElementById("signupBtn");
  btn.disabled = true; btn.textContent = "Registrazione...";

  try {
    const { backendUrl } = await chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND });
    const url = (backendUrl || DEFAULT_BACKEND).replace(/\/$/, "");
    let res;
    try {
      res = await fetch(`${url}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
    } catch {
      throw new Error("Server non raggiungibile. Controlla la tua connessione.");
    }
    let data;
    try { data = await res.json(); } catch { data = {}; }
    if (!res.ok) throw new Error(data.detail || `Errore ${res.status}. Riprova.`);

    if (data.access_token) {
      await chrome.storage.sync.set({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        userEmail: data.email,
      });
      await refreshAccountView();
    } else {
      showAuthStatus("signup", "Account creato! Controlla la tua email per confermare, poi accedi.", "success");
    }
  } catch (err) {
    showAuthStatus("signup", err.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "Crea account";
  }
}

async function doLogout() {
  await chrome.storage.sync.remove(["accessToken", "refreshToken", "userEmail"]);
  await refreshAccountView();
}

async function openPricing() {
  const { backendUrl, accessToken } = await chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND, accessToken: "" });
  const url = backendUrl.replace(/\/$/, "");
  chrome.tabs.create({ url: `${url}/pricing?backend=${encodeURIComponent(url)}&token=${encodeURIComponent(accessToken)}` });
}

// ── Account view ──────────────────────────────────────────────────────────

async function refreshAccountView() {
  const { accessToken, backendUrl, userEmail } = await chrome.storage.sync.get({
    accessToken: "", backendUrl: DEFAULT_BACKEND, userEmail: "",
  });

  if (!accessToken) {
    showAuthForms(); return;
  }

  try {
    const url = (backendUrl || DEFAULT_BACKEND).replace(/\/$/, "");
    const res = await fetch(`${url}/api/me`, { headers: { Authorization: `Bearer ${accessToken}` } });

    if (res.status === 401) {
      // Token scaduto o non valido — logout
      await chrome.storage.sync.remove(["accessToken", "refreshToken", "userEmail"]);
      showAuthForms(); return;
    }

    let status;
    try { status = await res.json(); } catch { status = null; }

    if (!res.ok || !status) {
      // Errore server ma token presente — mostra loggato con valori di default
      showLoggedIn(userEmail, { subscription: "free", analyses_this_month: 0, analyses_limit: 3 });
      return;
    }

    showLoggedIn(userEmail, status);
  } catch {
    // Errore di rete ma token presente — mostra loggato con valori di default
    if (accessToken) {
      showLoggedIn(userEmail, { subscription: "free", analyses_this_month: 0, analyses_limit: 3 });
    } else {
      showAuthForms();
    }
  }
}

function showAuthForms() {
  document.getElementById("authForms").classList.remove("hidden");
  document.getElementById("loggedInView").classList.add("hidden");
  document.getElementById("profileCard").classList.add("hidden");
}

function showLoggedIn(email, status) {
  document.getElementById("authForms").classList.add("hidden");
  document.getElementById("loggedInView").classList.remove("hidden");
  document.getElementById("profileCard").classList.remove("hidden");

  document.getElementById("userEmail").textContent = email || "—";

  const badge = document.getElementById("subBadge");
  if (status.subscription === "premium") {
    badge.textContent = "Premium ✦"; badge.className = "sub-badge premium";
    document.getElementById("upgradeBtn").classList.add("hidden");
    document.getElementById("usageSection").classList.add("hidden");
  } else {
    badge.textContent = "Free"; badge.className = "sub-badge free";
    document.getElementById("upgradeBtn").classList.remove("hidden");
    document.getElementById("usageSection").classList.remove("hidden");

    const count = status.analyses_this_month || 0;
    const limit = status.analyses_limit || 3;
    document.getElementById("usageCount").textContent = `${count} / ${limit}`;
    document.getElementById("usageBar").style.width = `${Math.min(100, (count / limit) * 100)}%`;
  }
}

function showAuthStatus(form, msg, type) {
  const el = document.getElementById(`${form}Status`);
  el.textContent = msg; el.className = `status ${type}`;
  if (type === "success") setTimeout(() => { el.textContent = ""; el.className = "status"; }, 5000);
}

// ── Backend URL ───────────────────────────────────────────────────────────

function saveBackend() {
  const url = document.getElementById("backendUrl").value.trim().replace(/\/$/, "");
  if (!url) { showStatus("Inserisci un URL valido", "error"); return; }
  chrome.storage.sync.set({ backendUrl: url }, () => showStatus("Salvato ✓", "success"));
}

async function testConnection() {
  const url = document.getElementById("backendUrl").value.trim().replace(/\/$/, "");
  if (!url) { showStatus("Inserisci prima l'URL", "error"); return; }
  showStatus("Test in corso...", "neutral");
  try {
    const res = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(6000) });
    if (res.ok) showStatus("Connessione OK ✓", "success");
    else showStatus(`Errore HTTP ${res.status}`, "error");
  } catch {
    showStatus("Server non raggiungibile.", "error");
  }
}

function showStatus(msg, type) {
  const el = document.getElementById("statusMsg");
  el.textContent = msg; el.className = `status ${type}`;
  if (type === "success") setTimeout(() => { el.textContent = ""; el.className = "status"; }, 4000);
}

// ── User profile ──────────────────────────────────────────────────────────

function updateCharsLeft(len) {
  document.getElementById("charsLeft").textContent = MAX_USER_INFO - len;
}

function saveProfile() {
  const info = document.getElementById("userInfo").value.trim();
  chrome.storage.sync.set({ userInfo: info }, () => {
    const el = document.getElementById("profileStatus");
    el.textContent = info ? "Salvato ✓" : "Rimosso";
    el.className = "status success";
    setTimeout(() => { el.textContent = ""; el.className = "status"; }, 3000);
  });
}
