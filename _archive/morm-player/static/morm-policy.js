// MORM wallet policy module — Phase 27g/h/i.
//
// Threat (SECURITY-DESIGN §3.3): a hostile JS or compromised SW on a
// MORM page can drive `signTxWithConfirm` programmatically. WebAuthn
// (Phase 7) gates the actual signing key, but once the user clicks
// through the confirm dialog ONCE, nothing prevents follow-up tx of
// any kind / amount on the same page.
//
// Mitigation:
//   - 27h: per-page (per-app) ALLOWED_KINDS whitelist — `shop` may only
//     CREATE_ORDER/SUBMIT_PROOF/FINALIZE, `admin` may only do treasury
//     operations, etc. Anything else is hard-rejected before the
//     confirm dialog even renders.
//   - 27g: per-app DAILY_CAP_MORM — running 24h spend counter (TRANSFER
//     amount + BRIDGE_BURN amount + CREATE_ORDER value). When a tx
//     would push cumulative spend over the cap, the confirm dialog is
//     replaced with a stronger "Extra ceremony" modal that requires an
//     explicit checkbox click.
//   - 27i: 1-tap revocation — wallet UI (/wallet) clears every policy
//     entry and every recorded spend, returning the wallet to the
//     "first-touch" state where every app must be re-granted.
//
// Storage layout (localStorage):
//   morm-policy-v1     → { [appKey]: { allowedKinds: int[], dailyCapMorm: number,
//                                       grantedAt: epochSec } }
//   morm-spend-v1      → { [appKey]: [ { ts: epochSec, amount: number,
//                                         kind: int }, ... ] }
//
// `appKey` is `location.pathname` first segment ("shop", "admin", ...).
// All MORM pages share the same browser origin so we can't use it to
// scope; pathname is the natural per-feature boundary in this design.

const POLICY_KEY = 'morm-policy-v1';
const SPEND_KEY  = 'morm-spend-v1';
const WINDOW_SEC = 24 * 60 * 60;        // rolling 24h spend window

// ---- tx kind metadata (shared with morm-identity.js) -------------
export const TX_KIND_NAMES = {
  1: 'REGISTER_CONTENT', 2: 'CREATE_ORDER', 3: 'SUBMIT_PROOF',
  4: 'FINALIZE', 5: 'STAKE', 6: 'TRANSFER', 7: 'VIEW_REWARD',
  10: 'POST_JOB', 11: 'CLAIM_JOB', 12: 'SUBMIT_WORK_PROOF',
  20: 'BRIDGE_MINT', 21: 'BRIDGE_BURN',
  30: 'REGISTER_AI_SERVICE', 31: 'REGISTER_PRODUCER',
  32: 'REGISTER_TREASURY_SIGNERS', 33: 'MULTISIG_TX',
};

// ---- defaults ---------------------------------------------------
// Per-feature scope defaults. The cap is generous enough not to interfere
// with normal flows; the kind whitelist matches each page's tx surface
// per docs/PHASE25-VIDEO and Phase 15a (shop), 19b (admin) etc.
const DEFAULT_POLICIES = {
  // /shop — buyer/seller flow. Order value is the spend.
  shop:        { allowedKinds: [2, 3, 4],     dailyCapMorm: 1_000_000 },
  // /auth-morm — identity setup, content registration only.
  'auth-morm': { allowedKinds: [1, 30],       dailyCapMorm: 0 },
  // /admin — treasury operations. No "spend" semantics (treasury mints).
  admin:       { allowedKinds: [4, 20, 31, 32, 33], dailyCapMorm: 0 },
  // /player-hls — VIEW_REWARD claims (mint, not spend).
  'player-hls':{ allowedKinds: [7],           dailyCapMorm: 0 },
  // /upload — content registration only.
  upload:      { allowedKinds: [1],           dailyCapMorm: 0 },
  // /wallet itself — TRANSFER for sending tokens to other addresses.
  wallet:      { allowedKinds: [6],           dailyCapMorm: 100_000 },
  // /swap — Phase 28a EVM↔MORM bridge UI. Lock side uses MetaMask
  // (Ethereum signature, no MORM tx kind needed); only the Burn side
  // emits MORM tx, so the whitelist is BRIDGE_BURN only. Generous
  // daily cap because users may bridge multi-ETH amounts in one go.
  swap:        { allowedKinds: [21],          dailyCapMorm: 100_000_000 },
};

// Catch-all fallback for unknown pages (root, dev pages). We allow
// everything but with a tight cap, so legacy flows still work. The
// /wallet UI lets the user tighten this.
const FALLBACK_POLICY = {
  allowedKinds: [1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 20, 21, 30, 31, 32, 33],
  dailyCapMorm: 100_000,
};

// ---- key derivation ---------------------------------------------
export function appKeyFromLocation(loc = window.location) {
  // first non-empty path segment, lower-case. Accepts both "/shop" and
  // "/shop.html" → "shop". Strip trailing ".html" for stability.
  const seg = (loc.pathname.split('/')[1] || '').replace(/\.html$/, '');
  return seg || '_root';
}

// ---- storage helpers --------------------------------------------
function _readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch { return fallback; }
}
function _writeJson(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}

function _allPolicies() { return _readJson(POLICY_KEY, {}); }
function _allSpend()    { return _readJson(SPEND_KEY,  {}); }

// ---- public policy API ------------------------------------------
/** Resolve the active policy for `appKey`, lazily seeding from defaults
 * the first time we encounter it. Subsequent calls return the persisted
 * (possibly user-tightened) policy. */
export function getPolicy(appKey = appKeyFromLocation()) {
  const all = _allPolicies();
  if (all[appKey]) return all[appKey];
  const seed = DEFAULT_POLICIES[appKey] || FALLBACK_POLICY;
  const p = {
    allowedKinds: [...seed.allowedKinds],
    dailyCapMorm: seed.dailyCapMorm,
    grantedAt: Math.floor(Date.now() / 1000),
    isDefault: !DEFAULT_POLICIES[appKey],
  };
  all[appKey] = p;
  _writeJson(POLICY_KEY, all);
  return p;
}

export function setPolicy(appKey, policy) {
  const all = _allPolicies();
  all[appKey] = { ...policy, grantedAt: Math.floor(Date.now() / 1000) };
  _writeJson(POLICY_KEY, all);
}

export function listPolicies() {
  return _allPolicies();
}

/** Wipe every policy + every spend record. After calling this the
 * next tx from any page re-prompts the default policy as if the user
 * had never granted anything. (27i 1-tap revocation.) */
export function revokeAll() {
  try {
    localStorage.removeItem(POLICY_KEY);
    localStorage.removeItem(SPEND_KEY);
  } catch {}
}

// ---- spend tracking ---------------------------------------------
/** Pull the spend amount out of a tx payload. Only kinds where the
 * SENDER actually parts with MORM count: TRANSFER, BRIDGE_BURN,
 * CREATE_ORDER (locked into escrow). VIEW_REWARD is a mint, not a
 * spend — we don't track it. STAKE locks but doesn't transfer (PoUW
 * weight); excluded for clarity. */
export function txSpendAmount(kind, payload) {
  if (!payload) return 0;
  if (kind === 6  /* TRANSFER */)     return Number(payload.amount) || 0;
  if (kind === 21 /* BRIDGE_BURN */)  return Number(payload.amount) || 0;
  if (kind === 2  /* CREATE_ORDER */) return Number(payload.value)  || 0;
  return 0;
}

function _pruneSpend(entries, now = Date.now() / 1000) {
  return entries.filter(e => (now - e.ts) <= WINDOW_SEC);
}

export function getSpentLast24h(appKey = appKeyFromLocation()) {
  const all = _allSpend();
  const arr = _pruneSpend(all[appKey] || []);
  return arr.reduce((s, e) => s + (e.amount || 0), 0);
}

export function recordSpend(appKey, kind, amount) {
  if (!amount) return;
  const all = _allSpend();
  const arr = _pruneSpend(all[appKey] || []);
  arr.push({ ts: Math.floor(Date.now() / 1000), kind, amount });
  all[appKey] = arr;
  _writeJson(SPEND_KEY, all);
}

// ---- enforcement ------------------------------------------------
/** Decide whether a tx can be signed under the current policy.
 * Returns:
 *   { ok: true, requireExtra: false }   — proceed with normal confirm
 *   { ok: true, requireExtra: true,
 *     spent, cap, after }               — over cap, require stronger UI
 *   { ok: false, reason: "kind-not-allowed", allowed }
 *
 * Callers (`signTxWithConfirm`) must honour requireExtra by showing a
 * second-factor checkbox modal before passing the tx to passkey signing.
 */
export function decideTx({ kind, payload, appKey }) {
  appKey = appKey || appKeyFromLocation();
  const policy = getPolicy(appKey);
  if (!policy.allowedKinds.includes(kind)) {
    return {
      ok: false,
      reason: 'kind-not-allowed',
      kind, kindName: TX_KIND_NAMES[kind] || `kind=${kind}`,
      allowed: policy.allowedKinds.map(k => TX_KIND_NAMES[k] || `kind=${k}`),
      appKey,
    };
  }
  const amount = txSpendAmount(kind, payload);
  const spent  = getSpentLast24h(appKey);
  const cap    = policy.dailyCapMorm;
  const after  = spent + amount;
  if (cap > 0 && amount > 0 && after > cap) {
    return { ok: true, requireExtra: true, spent, cap, after, amount, appKey };
  }
  return { ok: true, requireExtra: false, spent, cap, after, amount, appKey };
}

// ---- extra-ceremony modal ---------------------------------------
/** Stronger-than-confirm modal when an upcoming tx would exceed the
 * 24h spend cap. Returns true if the user explicitly checks the
 * acknowledgement box AND clicks Approve. Cancel / X / ESC → false. */
export async function showExtraCeremonyDialog({ kind, payload, decision, senderHex }) {
  const { t } = await import('/static/morm-i18n.js');
  const kindName = TX_KIND_NAMES[kind] || `kind=${kind}`;
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed; inset: 0; background: rgba(80,0,0,0.85);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    `;
    const box = document.createElement('div');
    box.style.cssText = `
      background: #1d0e10; color: #ffd5d5; border: 2px solid #ff4040;
      border-radius: 10px; padding: 22px; max-width: 480px; width: 90%;
      box-shadow: 0 0 36px rgba(255,64,64,0.4);
    `;
    const title = document.createElement('h3');
    title.textContent = t('cap.title');
    title.style.cssText = 'margin: 0 0 12px; color: #ff8080; font-size: 18px;';

    const lines = [
      t('cap.app',         { app: decision.appKey }),
      t('cap.kind',        { kind: kindName }),
      t('cap.this_amount', { amount: decision.amount }),
      t('cap.spent24h',    { spent: decision.spent }),
      t('cap.after',       { after: decision.after }),
      t('cap.daily_cap',   { cap: decision.cap }),
    ];
    const body = document.createElement('div');
    body.style.cssText = 'font-family: monospace; font-size: 13px; line-height: 1.6; margin-bottom: 16px; color: #ffd5d5;';
    body.innerHTML = lines.map(l => `<div></div>`).join('');
    [...body.children].forEach((d, i) => d.textContent = lines[i]);

    const note = document.createElement('div');
    note.style.cssText = 'font-size: 12px; color: #ff8080; margin-bottom: 14px;';
    note.textContent = t('cap.warn');

    const ackRow = document.createElement('label');
    ackRow.style.cssText = 'display: flex; gap: 8px; align-items: center; margin-bottom: 16px; cursor: pointer; font-size: 13px;';
    const ackBox = document.createElement('input');
    ackBox.type = 'checkbox';
    ackBox.style.cssText = 'width: 18px; height: 18px;';
    const ackTxt = document.createElement('span');
    ackTxt.textContent = t('cap.ack');
    ackRow.appendChild(ackBox); ackRow.appendChild(ackTxt);

    const sender = document.createElement('div');
    sender.textContent = t('common.signing_as', { addr: (senderHex || '').slice(0, 16) + '…' });
    sender.style.cssText = 'font-family: monospace; font-size: 11px; color: #aa6a6a; margin-bottom: 16px;';

    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display: flex; gap: 8px; justify-content: flex-end;';
    const cancel = document.createElement('button');
    cancel.textContent = t('common.cancel');
    cancel.style.cssText = 'padding: 10px 18px; background: #2b2f37; color: #e6e9ee; border: 1px solid #3a4150; border-radius: 6px; cursor: pointer; font-size: 14px;';
    const ok = document.createElement('button');
    ok.textContent = t('cap.approve');
    ok.style.cssText = 'padding: 10px 18px; background: #ff4040; color: #fff; border: none; border-radius: 6px; cursor: not-allowed; font-weight: 700; font-size: 14px; opacity: 0.5;';
    ok.disabled = true;
    ackBox.onchange = () => {
      ok.disabled = !ackBox.checked;
      ok.style.opacity = ackBox.checked ? '1' : '0.5';
      ok.style.cursor  = ackBox.checked ? 'pointer' : 'not-allowed';
    };
    btnRow.appendChild(cancel); btnRow.appendChild(ok);

    box.appendChild(title); box.appendChild(body); box.appendChild(note);
    box.appendChild(ackRow); box.appendChild(sender); box.appendChild(btnRow);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    const cleanup = (result) => {
      document.body.removeChild(overlay);
      window.removeEventListener('keydown', onKey);
      resolve(result);
    };
    const onKey = e => { if (e.key === 'Escape') cleanup(false); };
    cancel.onclick = () => cleanup(false);
    ok.onclick = () => { if (ackBox.checked) cleanup(true); };
    overlay.onclick = e => { if (e.target === overlay) cleanup(false); };
    window.addEventListener('keydown', onKey);
  });
}

/** Friendly error modal when 27h whitelist rejects a tx. No "Approve"
 * path — the wallet UI must be visited to broaden the policy first. */
export async function showKindBlockedDialog({ decision }) {
  const { t } = await import('/static/morm-i18n.js');
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed; inset: 0; background: rgba(40,0,0,0.85);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    `;
    const box = document.createElement('div');
    box.style.cssText = `
      background: #1d0e10; color: #ffd5d5; border: 2px solid #ff8080;
      border-radius: 10px; padding: 22px; max-width: 480px; width: 90%;
    `;
    const title = document.createElement('h3');
    title.textContent = t('block.title');
    title.style.cssText = 'margin: 0 0 12px; color: #ff8080; font-size: 18px;';

    const body = document.createElement('div');
    body.style.cssText = 'font-family: monospace; font-size: 13px; line-height: 1.6; margin-bottom: 14px;';
    const lines = [
      t('block.app',          { app: decision.appKey }),
      t('block.blocked_kind', { kind: decision.kindName }),
      t('block.allowed',      { kinds: decision.allowed.join(', ') || t('block.allowed_none') }),
    ];
    for (const l of lines) {
      const d = document.createElement('div'); d.textContent = l; body.appendChild(d);
    }

    const note = document.createElement('div');
    note.style.cssText = 'font-size: 12px; color: #ff8080; margin-bottom: 14px;';
    note.textContent = t('block.note');

    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display: flex; gap: 8px; justify-content: flex-end;';
    const ok = document.createElement('button');
    ok.textContent = t('common.dismiss');
    ok.style.cssText = 'padding: 10px 18px; background: #2b2f37; color: #ffd5d5; border: 1px solid #ff8080; border-radius: 6px; cursor: pointer; font-size: 14px;';
    btnRow.appendChild(ok);

    box.appendChild(title); box.appendChild(body); box.appendChild(note);
    box.appendChild(btnRow);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    const cleanup = () => {
      document.body.removeChild(overlay);
      window.removeEventListener('keydown', onKey);
      resolve();
    };
    const onKey = e => { if (e.key === 'Escape' || e.key === 'Enter') cleanup(); };
    ok.onclick = cleanup;
    overlay.onclick = e => { if (e.target === overlay) cleanup(); };
    window.addEventListener('keydown', onKey);
    setTimeout(() => ok.focus(), 50);
  });
}
