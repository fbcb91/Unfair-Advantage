const DEFAULT_BACKEND = "http://localhost:8000";
const MAX_USER_INFO = 500;

document.addEventListener("DOMContentLoaded", () => {
  chrome.storage.sync.get(["backendUrl", "userInfo"], ({ backendUrl, userInfo }) => {
    document.getElementById("backendUrl").value = backendUrl || DEFAULT_BACKEND;
    const ta = document.getElementById("userInfo");
    ta.value = userInfo || "";
    updateCharsLeft(ta.value.length);
  });

  document.getElementById("saveBtn").addEventListener("click", save);
  document.getElementById("testBtn").addEventListener("click", testConnection);
  document.getElementById("backendUrl").addEventListener("keydown", e => {
    if (e.key === "Enter") save();
  });

  document.getElementById("saveProfileBtn").addEventListener("click", saveProfile);

  const ta = document.getElementById("userInfo");
  ta.addEventListener("input", () => {
    if (ta.value.length > MAX_USER_INFO) ta.value = ta.value.slice(0, MAX_USER_INFO);
    updateCharsLeft(ta.value.length);
  });

  document.querySelectorAll(".tag").forEach(tag => {
    tag.addEventListener("click", () => {
      const ta = document.getElementById("userInfo");
      const snippet = tag.dataset.snippet;
      const sep = ta.value && !ta.value.endsWith(" ") && !ta.value.endsWith(".") ? ". " : (ta.value ? " " : "");
      const newVal = (ta.value + sep + snippet).slice(0, MAX_USER_INFO);
      ta.value = newVal;
      updateCharsLeft(newVal.length);
      ta.focus();
    });
  });
});

function updateCharsLeft(len) {
  document.getElementById("charsLeft").textContent = MAX_USER_INFO - len;
}

function save() {
  const url = document.getElementById("backendUrl").value.trim().replace(/\/$/, "");
  if (!url) { showStatus("Inserisci un URL valido", "error"); return; }
  chrome.storage.sync.set({ backendUrl: url }, () => {
    showStatus("Salvato ✓", "success");
  });
}

function saveProfile() {
  const info = document.getElementById("userInfo").value.trim();
  chrome.storage.sync.set({ userInfo: info }, () => {
    showProfileStatus(info ? "Profilo salvato ✓" : "Profilo rimosso", "success");
  });
}

async function testConnection() {
  const url = document.getElementById("backendUrl").value.trim().replace(/\/$/, "");
  if (!url) { showStatus("Inserisci prima l'URL", "error"); return; }
  showStatus("Test in corso...", "neutral");
  try {
    const res = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(6000) });
    if (res.ok) {
      showStatus("Connessione OK ✓ — backend raggiungibile", "success");
    } else {
      showStatus(`Errore HTTP ${res.status}`, "error");
    }
  } catch {
    showStatus("Server non raggiungibile. Controlla l'URL e che il deploy sia completato.", "error");
  }
}

function showStatus(msg, type) {
  const el = document.getElementById("statusMsg");
  el.textContent = msg;
  el.className = `status ${type}`;
  if (type === "success") setTimeout(() => { el.textContent = ""; el.className = "status"; }, 4000);
}

function showProfileStatus(msg, type) {
  const el = document.getElementById("profileStatus");
  el.textContent = msg;
  el.className = `status-inline ${type}`;
  setTimeout(() => { el.textContent = ""; el.className = "status-inline"; }, 3000);
}
