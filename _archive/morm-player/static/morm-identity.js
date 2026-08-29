// Shared MORM Chain identity helpers (ed25519, signing-bytes, IndexedDB).
// Used by both auth-morm.js (gateway page) and player.js (edge-served page).

import * as ed from 'https://esm.sh/@noble/ed25519@2.1.0';
import { sha512 } from 'https://esm.sh/@noble/hashes@1.5.0/sha512';
import { blake2b } from 'https://esm.sh/@noble/hashes@1.5.0/blake2b';
ed.etc.sha512Sync = (...m) => sha512(ed.etc.concatBytes(...m));
export { ed };

const DB_NAME = 'morm-passkeys-l1';
const STORE = 'shares';

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () =>
      req.result.createObjectStore(STORE, { keyPath: 'credential_id' });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function listIdentities() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

export const hexToBytes = h => {
  h = h.replace(/^0x/, '');
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.substr(i*2, 2), 16);
  return out;
};
export const bytesToHex = b =>
  [...b].map(x => x.toString(16).padStart(2, '0')).join('');

export function addressFromPubkey(pub) {
  const h = blake2b(pub, { dkLen: 32 });
  return '0x' + bytesToHex(h.slice(-20));
}

// Canonical JSON, sort_keys + (',', ':') separators — matches Python.
function canonicalize(value) {
  if (value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(canonicalize);
  const sorted = {};
  for (const k of Object.keys(value).sort()) sorted[k] = canonicalize(value[k]);
  return sorted;
}
export function canonicalJson(obj) { return JSON.stringify(canonicalize(obj)); }

export function buildSigningBytes(kind, senderHex, nonce, payload) {
  const obj = { kind, sender: senderHex, nonce, payload: canonicalize(payload) };
  return new TextEncoder().encode(canonicalJson(obj));
}

export async function signTx({ kind, senderPub, senderSeed, nonce, payload }) {
  const senderHex = bytesToHex(senderPub);
  const msg = buildSigningBytes(kind, senderHex, nonce, payload);
  const sig = await ed.signAsync(msg, senderSeed);
  return {
    kind, sender: senderHex, nonce, payload,
    signature: bytesToHex(sig),
  };
}

// =============================================================
// Phase 27f — Tx confirm dialog before passkey signing.
//
// Goal: a hostile JS or compromised SW can drive passkey signing
// without the user noticing. The confirm dialog forces an
// explicit human click after rendering the tx kind + key fields
// in plain language, so headless / hidden signing fails.
//
// Exempt kinds: VIEW_REWARD (kind=7) — these fire per cell at
// micro-amount (1 µMORM) and modal-on-every-cell would be
// hostile UX. The PER-CELL value is bounded; risk is bounded.
// Per-domain spending cap is a separate phase (27g).
// =============================================================

const TX_KIND_NAMES = {
  1: 'REGISTER_CONTENT', 2: 'CREATE_ORDER', 3: 'SUBMIT_PROOF',
  4: 'FINALIZE', 5: 'STAKE', 6: 'TRANSFER', 7: 'VIEW_REWARD',
  10: 'POST_JOB', 11: 'CLAIM_JOB', 12: 'SUBMIT_WORK_PROOF',
  20: 'BRIDGE_MINT', 21: 'BRIDGE_BURN',
  30: 'REGISTER_AI_SERVICE', 31: 'REGISTER_PRODUCER',
  32: 'REGISTER_TREASURY_SIGNERS', 33: 'MULTISIG_TX',
};

const TX_AUTO_CONFIRM_KINDS = new Set([7]);   // VIEW_REWARD only

function _humanizeTxFields(kind, payload) {
  const rows = [];
  // Per-kind highlighting of high-stakes fields. Anything not listed
  // here renders as "field: value" — better to over-show than to hide.
  if (kind === 6) {  // TRANSFER
    if (payload.to)     rows.push(['Send to', payload.to]);
    if (payload.amount) rows.push(['Amount', `${payload.amount} MORM`]);
  } else if (kind === 21) {  // BRIDGE_BURN
    if (payload.evm_recipient) rows.push(['Burn → EVM addr', payload.evm_recipient]);
    if (payload.amount)        rows.push(['Amount', `${payload.amount} ${payload.token || 'MORM'}`]);
  } else if (kind === 2) {  // CREATE_ORDER
    if (payload.seller) rows.push(['Seller', payload.seller]);
    if (payload.value)  rows.push(['Order value', `${payload.value} MORM`]);
    if (payload.content_id) rows.push(['Content', payload.content_id]);
  } else if (kind === 3) {  // SUBMIT_PROOF
    if (payload.role)     rows.push(['Role', payload.role]);
    if (payload.order_id) rows.push(['Order', payload.order_id]);
  } else if (kind === 4) {  // FINALIZE
    if (payload.order_id) rows.push(['Order', payload.order_id]);
    rows.push(['Outcome', payload.valid ? 'VALID (release to seller)' : 'INVALID (refund buyer)']);
  } else if (kind === 5) {  // STAKE
    if (payload.amount) rows.push(['Stake amount', `${payload.amount} MORM`]);
  } else {
    for (const [k, v] of Object.entries(payload)) {
      rows.push([k, typeof v === 'object' ? JSON.stringify(v) : String(v)]);
    }
  }
  return rows;
}

/** Render the modal and resolve to true (confirm) / false (cancel).
 *  Self-contained — injects its own DOM + styles, no framework needed.
 *  Phase i18n — title / button / signing-as label go through morm-i18n.
 *  Field labels stay in English because they're interleaved with raw
 *  hex values; localising every kind's field set is a Phase-2 task. */
export async function showTxConfirmDialog({ kind, payload, nonce, senderHex }) {
  let _t = (k, p) => k;
  try {
    const m = await import('/static/morm-i18n.js'); _t = m.t;
  } catch {}
  const kindName = TX_KIND_NAMES[kind] || `kind=${kind}`;
  const fields = _humanizeTxFields(kind, payload);
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed; inset: 0; background: rgba(0,0,0,0.7);
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    `;
    const box = document.createElement('div');
    box.style.cssText = `
      background: #16181d; color: #e6e9ee; border: 1px solid #4dd2ff;
      border-radius: 8px; padding: 20px; max-width: 480px; width: 90%;
      box-shadow: 0 0 32px rgba(77,210,255,0.4);
    `;
    const title = document.createElement('h3');
    title.textContent = _t('confirm.title');
    title.style.cssText = 'margin: 0 0 12px; color: #4dd2ff; font-size: 18px;';
    const sub = document.createElement('div');
    sub.textContent = `${kindName}  ·  nonce ${nonce}`;
    sub.style.cssText = 'font-family: monospace; color: #8ea0b8; margin-bottom: 16px; font-size: 13px;';
    const table = document.createElement('table');
    table.style.cssText = 'width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 12px;';
    for (const [k, v] of fields) {
      const tr = document.createElement('tr');
      const th = document.createElement('td');
      th.textContent = k;
      th.style.cssText = 'padding: 6px 8px 6px 0; color: #8ea0b8; vertical-align: top; white-space: nowrap;';
      const td = document.createElement('td');
      td.textContent = v;
      td.style.cssText = 'padding: 6px 0; word-break: break-all; font-family: monospace; font-size: 12px;';
      tr.appendChild(th); tr.appendChild(td);
      table.appendChild(tr);
    }
    const sender = document.createElement('div');
    sender.textContent = _t('common.signing_as', { addr: senderHex.slice(0, 16) + '…' });
    sender.style.cssText = 'font-family: monospace; font-size: 11px; color: #6a7a90; margin-bottom: 16px;';
    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display: flex; gap: 8px; justify-content: flex-end;';
    const cancel = document.createElement('button');
    cancel.textContent = _t('common.cancel');
    cancel.style.cssText = 'padding: 8px 16px; background: #2b2f37; color: #e6e9ee; border: 1px solid #3a4150; border-radius: 4px; cursor: pointer; font-size: 14px;';
    const ok = document.createElement('button');
    ok.textContent = _t('confirm.button');
    ok.style.cssText = 'padding: 8px 16px; background: #4dd2ff; color: #0a1218; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; font-size: 14px;';
    btnRow.appendChild(cancel); btnRow.appendChild(ok);
    box.appendChild(title); box.appendChild(sub); box.appendChild(table);
    box.appendChild(sender); box.appendChild(btnRow);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    const cleanup = (result) => {
      document.body.removeChild(overlay);
      window.removeEventListener('keydown', onKey);
      resolve(result);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') cleanup(false);
      else if (e.key === 'Enter') cleanup(true);
    };
    cancel.onclick = () => cleanup(false);
    ok.onclick = () => cleanup(true);
    overlay.onclick = (e) => { if (e.target === overlay) cleanup(false); };
    window.addEventListener('keydown', onKey);
    setTimeout(() => ok.focus(), 50);
  });
}

/** Wraps signTx with the confirm dialog. Default: confirm required.
 *  Pass `{ skipConfirm: true }` only for explicit micro-tx flows
 *  (VIEW_REWARD per-cell, currently the only exemption).
 *  Returns null if the user cancels — callers must check.
 *
 *  Phase 27g/h/i — policy gate runs FIRST: a per-page whitelist (27h)
 *  blocks unknown tx kinds outright (returns null with a "kind blocked"
 *  dialog), and a 24h spending cap (27g) substitutes a stronger
 *  ack-checkbox modal for the standard confirm when the cap would be
 *  exceeded. The policy is in localStorage and revokable from /wallet
 *  (27i). */
export async function signTxWithConfirm({ kind, senderPub, senderSeed, nonce, payload, skipConfirm = false }) {
  const senderHex = bytesToHex(senderPub);
  const isExempt = skipConfirm || TX_AUTO_CONFIRM_KINDS.has(kind);

  // Policy gate (27g/h). Lazy-imported so morm-identity stays usable in
  // contexts where morm-policy isn't loaded (e.g. unit tests).
  let policyDecision = null;
  if (!isExempt) {
    try {
      const policy = await import('/static/morm-policy.js');
      policyDecision = policy.decideTx({ kind, payload });
      if (!policyDecision.ok) {
        console.warn('[27h] tx blocked by policy', policyDecision);
        await policy.showKindBlockedDialog({ decision: policyDecision });
        return null;
      }
      if (policyDecision.requireExtra) {
        const ok = await policy.showExtraCeremonyDialog({
          kind, payload, decision: policyDecision, senderHex,
        });
        if (!ok) {
          console.warn('[27g] over-cap tx cancelled by user', policyDecision);
          return null;
        }
      } else {
        const ok = await showTxConfirmDialog({ kind, payload, nonce, senderHex });
        if (!ok) {
          console.warn('[27f] tx signing cancelled by user', { kind, payload });
          return null;
        }
      }
    } catch (e) {
      // Policy module missing or threw — fall back to plain confirm so
      // we never silently sign without ANY user check.
      console.warn('[27g/h] policy module unavailable, falling back to confirm', e);
      const ok = await showTxConfirmDialog({ kind, payload, nonce, senderHex });
      if (!ok) return null;
    }
  }

  const tx = await signTx({ kind, senderPub, senderSeed, nonce, payload });
  // Record spend AFTER successful signing — keeps the 24h counter
  // accurate even if the network relay later fails.
  if (policyDecision && policyDecision.ok && policyDecision.amount > 0) {
    try {
      const policy = await import('/static/morm-policy.js');
      policy.recordSpend(policyDecision.appKey, kind, policyDecision.amount);
    } catch {}
  }
  return tx;
}

/** Reconstruct seed from (server_share, client_share). Caller must wipe after use. */
export function combineShares(serverShareHex, clientShareHex) {
  const a = hexToBytes(serverShareHex);
  const b = hexToBytes(clientShareHex);
  const out = new Uint8Array(32);
  for (let i = 0; i < 32; i++) out[i] = a[i] ^ b[i];
  return out;
}

/** Pose a single passkey-gated view_reward tx and relay through the gateway. */
export async function claimViewReward({
  gatewayUrl, mormRpc, identity, contentId, cellIndex,
}) {
  // 1) get server share
  const shareResp = await fetch(`${gatewayUrl}/api/dev/share`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential_id: identity.credential_id }),
  });
  if (!shareResp.ok) throw new Error(`share fetch ${shareResp.status}`);
  const sh = await shareResp.json();

  // 2) reconstruct seed locally
  const seed = combineShares(sh.server_share, identity.client_share);
  const pub = await ed.getPublicKeyAsync(seed);

  // 3) fetch nonce
  const acct = await fetch(`${mormRpc}/account/${identity.address}`).then(r => r.json());
  const nonce = acct.nonce;

  // 4) sign view_reward
  const tx = await signTx({
    kind: 7,                  // TxKind.VIEW_REWARD
    senderPub: pub,
    senderSeed: seed,
    nonce,
    payload: { content_id: contentId, cell_index: cellIndex },
  });
  seed.fill(0);

  // 5) relay
  const relay = await fetch(`${gatewayUrl}/api/relay/morm-tx`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tx }),
  });
  return relay.json();
}
