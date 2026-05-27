const DEFAULT_BACKEND = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
  chrome.storage.sync.get(["backendUrl"], ({ backendUrl }) => {
    document.getElementById("backendUrl").value = backendUrl || DEFAULT_BACKEND;
  });

  document.getElementById("saveBtn").addEventListener("click", save);
  document.getElementById("testBtn").addEventListener("click", testConnection);
  document.getElementById("backendUrl").addEventListener("keydown", e => {
    if (e.key === "Enter") save();
  });
});

function save() {
  const url = document.getElementById("backendUrl").value.trim().replace(/\/$/, "");
  if (!url) { showStatus("Inserisci un URL valido", "error"); return; }
  chrome.storage.sync.set({ backendUrl: url }, () => {
    showStatus("Salvato ✓", "success");
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
