// MORM Wallet — MV3 service worker.
// Phase 0 scaffold: holds the unlocked seed in memory ONLY, auto-locks on idle,
// and routes messages from the popup. No plaintext seed ever touches
// chrome.storage (only AES-GCM ciphertext, written by the popup/vault). The
// service worker can be killed by the browser at any time — that is a feature:
// it wipes the in-memory seed. Treat any unlock as session-scoped.

const IDLE_LOCK_MS = 5 * 60 * 1000;

let unlocked = null; // { seedHex, pubkeyHex, address } | null
let lockTimer = null;

function lock() {
  if (unlocked?.seedHex) {
    // Best-effort scrub of the hex string reference.
    unlocked.seedHex = null;
  }
  unlocked = null;
  if (lockTimer) { clearTimeout(lockTimer); lockTimer = null; }
}

function touch() {
  if (lockTimer) clearTimeout(lockTimer);
  lockTimer = setTimeout(lock, IDLE_LOCK_MS);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  switch (msg?.type) {
    case "getState":
      sendResponse({ locked: !unlocked, address: unlocked?.address ?? null });
      break;
    case "getSession":
      // Same-extension popup only (onMessage never fires cross-origin). The
      // seed is handed to the popup solely to sign a tx, then discarded there.
      if (unlocked) touch();
      sendResponse(unlocked ? { ...unlocked } : null);
      break;
    case "setUnlocked":
      // Popup performs decryption (it has DOM/WebAuthn); worker just caches.
      unlocked = { seedHex: msg.seedHex, pubkeyHex: msg.pubkeyHex, address: msg.address };
      touch();
      sendResponse({ ok: true });
      break;
    case "lock":
      lock();
      sendResponse({ ok: true });
      break;
    default:
      sendResponse({ error: "unknown message" });
  }
  return true; // async-safe
});

// Placeholder for the morm.one -> extension encrypted-seed handoff (Phase 2b).
chrome.runtime.onMessageExternal.addListener((_msg, sender, sendResponse) => {
  const ok = /^https:\/\/(www\.)?morm\.one$/.test(new URL(sender.url || sender.origin || "").origin || "");
  sendResponse({ ok, note: "handoff not yet implemented" });
  return true;
});
