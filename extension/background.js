// Minimal service worker required by Manifest V3.
// Actual logic lives in popup.js and content.js.
chrome.runtime.onInstalled.addListener(() => {
  // Open options on first install
  chrome.runtime.openOptionsPage();
});
