// MORM Wallet — MV3 service worker.
// The unlocked session is NOT held here anymore: MV3 workers are evicted after
// ~30s idle, which dropped the in-memory seed and caused "ロックされています" at
// sign time. The popup now keeps the session in chrome.storage.session (RAM,
// never disk, cleared on browser close), which survives worker eviction.
//
// This worker only hosts the placeholder for the future morm.one -> extension
// encrypted-seed handoff (Phase 2b).
chrome.runtime.onMessageExternal.addListener((_msg, sender, sendResponse) => {
  let ok = false;
  try { ok = /^https:\/\/(www\.)?morm\.one$/.test(new URL(sender.url || sender.origin || "").origin); } catch {}
  sendResponse({ ok, note: "handoff not yet implemented" });
  return true;
});
