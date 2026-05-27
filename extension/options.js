const DEFAULT_BACKEND = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
  chrome.storage.sync.get(["backendUrl"], ({ backendUrl }) => {
    document.getElementById("backendUrl").value = backendUrl || DEFAULT_BACKEND;
  });
});

function save() {
  const url = document.getElementById("backendUrl").value.trim().replace(/\/$/, "");
  if (!url) return showStatus("Inserisci un URL valido", "error");
  chrome.storage.sync.set({ backendUrl: url }, () => {
    showStatus("Salvato ✓", "success");
  });
}

async function testConnection() {
  const url = document.getElementById("backendUrl").value.trim().replace(/\/$/, "");
  showStatus("Test in corso...", "neutral");
  try {
    const res = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(5000) });
    if (res.ok) {
      showStatus("Connessione OK ✓", "success");
    } else {
      showStatus(`Errore HTTP ${res.status}`, "error");
    }
  } catch (e) {
    showStatus("Impossibile raggiungere il server. Controlla l'URL.", "error");
  }
}

function showStatus(msg, type) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className = `text-sm ${type === "success" ? "text-green-400" : type === "error" ? "text-red-400" : "text-gray-400"}`;
  el.classList.remove("hidden");
  if (type === "success") setTimeout(() => el.classList.add("hidden"), 3000);
}
