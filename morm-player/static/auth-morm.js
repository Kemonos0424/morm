// Phase 11b — browser-side ed25519 + MORM Chain Tx signing.
//
// The signing-bytes have to byte-for-byte match the Python implementation
// in morm-l1/morm_l1/tx.py:Transaction.signing_bytes(), which is:
//   JSON.stringify({kind, sender:hex, nonce, payload:canonical}, sort_keys, separators=(',',':'))
// We re-implement the canonical serializer in JS below, plus ed25519 sign
// via @noble/ed25519 (no seed-phrase, no wallet — pure key bytes).

import * as ed from 'https://esm.sh/@noble/ed25519@2.1.0';
import { sha512 } from 'https://esm.sh/@noble/hashes@1.5.0/sha512';
// Phase 27f: confirm-dialog wrapper for any client-side passkey signing.
import { showTxConfirmDialog } from './morm-identity.js';
ed.etc.sha512Sync = (...m) => sha512(ed.etc.concatBytes(...m));

const $ = id => document.getElementById(id);
const log = (msg, cls='info') => {
  const el = document.createElement('div');
  el.className = cls;
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  $('log').appendChild(el);
  $('log').scrollTop = $('log').scrollHeight;
};

// --- canonical JSON: matches Python json.dumps(sort_keys=True, separators=(',',':')) ---
function canonicalize(value) {
  if (value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(canonicalize);
  // bytes are hex'd in Python's _canonicalize → in JS we never have raw Uint8Array here
  const sorted = {};
  for (const k of Object.keys(value).sort()) sorted[k] = canonicalize(value[k]);
  return sorted;
}
function canonicalJson(obj) {
  // JSON.stringify is deterministic only for already-canonicalized objects
  return JSON.stringify(canonicalize(obj));
}

// --- hex helpers ---
const hexToBytes = h => {
  h = h.replace(/^0x/, '');
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.substr(i*2, 2), 16);
  return out;
};
const bytesToHex = b => [...b].map(x => x.toString(16).padStart(2, '0')).join('');

// --- MORM Tx builder + signer ---
function buildSigningBytes(kind, senderHex, nonce, payload) {
  const obj = { kind, sender: senderHex, nonce, payload: canonicalize(payload) };
  return new TextEncoder().encode(canonicalJson(obj));
}

async function signTx({ kind, senderPub, senderSeed, nonce, payload }) {
  const senderHex = bytesToHex(senderPub);
  const msg = buildSigningBytes(kind, senderHex, nonce, payload);
  const sig = await ed.signAsync(msg, senderSeed);
  return {
    kind,
    sender: senderHex,
    nonce,
    payload,
    signature: bytesToHex(sig),
  };
}

// --- BLAKE2b address derivation: matches morm_l1.crypto.address ---
import { blake2b } from 'https://esm.sh/@noble/hashes@1.5.0/blake2b';
function addressFromPubkey(pub) {
  const h = blake2b(pub, { dkLen: 32 });
  return '0x' + bytesToHex(h.slice(-20));
}

// --- IndexedDB for client_share ---
const DB_NAME = 'morm-passkeys-l1';
const STORE = 'shares';
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'credential_id' });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function dbPut(rec) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(rec);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
async function dbGet(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(id);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

// --- gateway calls ---
async function gPost(path, body) {
  const r = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error(`${path} → ${r.status} ${await r.text()}`);
  return r.json();
}

let session = null;  // { credential_id, address, pubkey, client_share }

async function devRegister() {
  log('requesting /api/dev/register (skipping WebAuthn — preview env)');
  const reg = await gPost('/api/dev/register', {});
  log(`server returned address ${reg.morm_address}`, 'ok');

  // sanity check: derive address from returned pubkey to confirm format
  const pub = hexToBytes(reg.pubkey_hex);
  const derivedAddr = addressFromPubkey(pub);
  if (derivedAddr.toLowerCase() !== reg.morm_address.toLowerCase()) {
    log(`address mismatch: derived=${derivedAddr} server=${reg.morm_address}`, 'err');
    return;
  }
  log(`address derivation matches BLAKE2b(pubkey)[-20:] ✓`);

  await dbPut({
    credential_id: reg.credential_id,
    address: reg.morm_address,
    pubkey: reg.pubkey_hex,
    client_share: reg.client_share,
  });
  session = {
    credential_id: reg.credential_id,
    address: reg.morm_address,
    pubkey: reg.pubkey_hex,
    client_share: reg.client_share,
  };
  $('id-display').textContent =
    `MORM ID = ${reg.morm_address}\n` +
    `pubkey  = ${reg.pubkey_hex}\n` +
    `share   = stored in IndexedDB · server holds independent share`;
  $('btn-action').disabled = false;
}

async function actionRegisterContent() {
  if (!session) { log('register first', 'err'); return; }

  const local = await dbGet(session.credential_id);
  if (!local) { log('local share missing', 'err'); return; }

  log('fetching server_share via /api/dev/share');
  const sh = await gPost('/api/dev/share', { credential_id: session.credential_id });

  // XOR shares to reconstruct the seed (briefly — we wipe after sign)
  const serverShare = hexToBytes(sh.server_share);
  const clientShare = hexToBytes(local.client_share);
  const seed = new Uint8Array(32);
  for (let i = 0; i < 32; i++) seed[i] = serverShare[i] ^ clientShare[i];
  log('shares combined locally — seed reconstructed', 'info');

  // verify reconstructed pubkey matches the recorded one
  const pub = await ed.getPublicKeyAsync(seed);
  if (bytesToHex(pub) !== local.pubkey) {
    log('reconstructed key does not match — split corrupted', 'err');
    return;
  }

  // build a deterministic content_id for the demo
  const enc = new TextEncoder();
  const cidSrc = enc.encode('phase11b-' + local.address + '-' + Date.now());
  const cidBytes = await crypto.subtle.digest('SHA-256', cidSrc);
  const cidHex = '0x' + bytesToHex(new Uint8Array(cidBytes));
  const rhHex  = '0x' + 'ab'.repeat(32);
  const gidHex = '0x' + bytesToHex(crypto.getRandomValues(new Uint8Array(32)));

  // fetch nonce from MORM L1 RPC via the gateway-proxied info
  log('fetching nonce from MORM Chain RPC');
  const info = await fetch('/api/morm/info').then(r => r.json());
  const nonceR = await fetch(`${info.rpc}/account/${local.address}`);
  const acct = await nonceR.json();
  const nonce = acct.nonce;

  // Phase 27f: confirm dialog before signing. registerContent is low-risk
  // but we apply the gate uniformly so users learn to read every prompt.
  const senderHex = bytesToHex(pub);
  const ok = await showTxConfirmDialog({
    kind: 1, payload: { content_id: cidHex, root_hash: rhHex, generation_id: gidHex },
    nonce, senderHex,
  });
  if (!ok) {
    seed.fill(0);
    log('registerContent cancelled by user', 'err');
    return;
  }
  log(`signing registerContent tx (nonce=${nonce}, kind=1)`);
  const txDict = await signTx({
    kind: 1,                  // TxKind.REGISTER_CONTENT
    senderPub: pub,
    senderSeed: seed,
    nonce,
    payload: {
      content_id: cidHex,
      root_hash: rhHex,
      generation_id: gidHex,
    },
  });

  // wipe the seed in memory immediately after signing
  seed.fill(0);

  log('relaying signed tx via /api/relay/morm-tx');
  const relay = await gPost('/api/relay/morm-tx', { tx: txDict });
  if (!relay.ok) { log(`relay failed: ${JSON.stringify(relay)}`, 'err'); return; }
  log(`MORM L1 accepted tx_hash=${relay.morm_response.tx_hash.slice(0, 16)}…`, 'ok');

  // wait for the producer to seal then verify
  await new Promise(r => setTimeout(r, 1800));
  const onChain = await fetch(`${info.rpc}/content/${cidHex}`);
  if (!onChain.ok) { log('content not yet on chain (give it another moment)', 'err'); return; }
  const c = await onChain.json();
  log(`on-chain creator = ${c.creator}`, 'ok');
  if (c.creator.toLowerCase() === local.address.toLowerCase()) {
    log(`✓ creator === passkey-bound address — full e2e success`, 'ok');
  }
}

$('btn-dev-register').addEventListener('click',
  () => devRegister().catch(e => log(e.message, 'err')));
$('btn-action').addEventListener('click',
  () => actionRegisterContent().catch(e => log(e.message, 'err')));
log('ready · waiting for user click');
