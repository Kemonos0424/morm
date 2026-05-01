// MORM ID — Phase 9: passkey + 2-of-2 device-distributed key.
//
// Registration:  server returns the ETH address + the *client* share.
//                Browser stores client_share + cred_id in IndexedDB. The
//                server never has the full key.
// Sign:          WebAuthn assertion → server returns its share → browser
//                XORs the two halves locally → ethers signs a tx → /api/relay
//                broadcasts. The privkey only briefly exists in the browser.

import { ethers } from 'https://esm.sh/ethers@6.13.4';

const $ = id => document.getElementById(id);
const log = (msg, cls='info') => {
  const el = document.createElement('div');
  el.className = cls;
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  $('log').appendChild(el);
  $('log').scrollTop = $('log').scrollHeight;
};

const ESCROW_ABI = [
  "function registerContent(bytes32 contentId, bytes32 rootHash, bytes32 generationId)",
];

let escrowAddr = null;
let chainId = null;
let rpcUrl = null;

async function loadEscrowInfo() {
  const r = await fetch('/api/escrow/info');
  const j = await r.json();
  escrowAddr = j.escrow;
  rpcUrl = j.rpc;
  chainId = j.chain_id;
  log(`escrow=${escrowAddr}  chain_id=${chainId}`);
}

// --- IndexedDB helpers ----------------------------------------------------
const DB_NAME = 'morm-passkeys';
const STORE = 'shares';
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'credential_id' });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function dbPut(record) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
async function dbGet(credId) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(credId);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}
async function dbList() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

// --- base64url helpers ----------------------------------------------------
const b64uToBytes = s => {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  s += '='.repeat((4 - s.length % 4) % 4);
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};
const bytesToB64u = bytes => {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};
const bufToB64u = buf => bytesToB64u(new Uint8Array(buf));
const hexToBytes = hex => {
  hex = hex.replace(/^0x/, '');
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i*2, 2), 16);
  return out;
};
const bytesToHex = bytes => {
  let s = '';
  for (const b of bytes) s += b.toString(16).padStart(2, '0');
  return s;
};

let currentCredentialId = null;
let currentEthAddress = null;

async function refreshAccounts() {
  // Combine server's view (passkeys row) + browser's view (IndexedDB shares)
  const r = await fetch('/api/auth/list');
  const j = await r.json();
  const local = await dbList();
  const localByCred = new Map(local.map(r => [r.credential_id, r]));

  const ul = $('accounts-list');
  ul.innerHTML = '';
  if (!j.passkeys.length) {
    ul.innerHTML = '<li class="handle">— none yet —</li>';
    return;
  }
  for (const pk of j.passkeys) {
    const hasLocal = localByCred.has(pk.credential_id);
    const li = document.createElement('li');
    li.innerHTML = `<span class="handle">${pk.user_handle}${hasLocal ? '' : ' <span style="color:#ff9050">(no local share)</span>'}</span><span class="addr">${pk.eth_address}</span>`;
    ul.appendChild(li);
  }
}

async function register() {
  log('requesting registration challenge…');
  const optsResp = await fetch('/api/auth/begin-register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
  });
  const opts = await optsResp.json();

  const publicKey = {
    ...opts,
    challenge: b64uToBytes(opts.challenge),
    user: { ...opts.user, id: b64uToBytes(opts.user.id) },
    excludeCredentials: (opts.excludeCredentials || []).map(c => ({
      ...c, id: b64uToBytes(c.id),
    })),
  };

  log('navigator.credentials.create() — biometric prompt…');
  let cred;
  try {
    cred = await navigator.credentials.create({ publicKey });
  } catch (e) {
    log(`registration cancelled: ${e.message}`, 'err');
    return;
  }

  const credPayload = {
    id: cred.id,
    rawId: bufToB64u(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bufToB64u(cred.response.clientDataJSON),
      attestationObject: bufToB64u(cred.response.attestationObject),
    },
    clientExtensionResults: cred.getClientExtensionResults?.() || {},
  };

  const finishResp = await fetch('/api/auth/finish-register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential: credPayload }),
  });
  const result = await finishResp.json();
  if (!result.ok) {
    log(`server rejected: ${result.error}`, 'err');
    return;
  }
  // Persist OUR share locally — server already discarded the full key
  await dbPut({
    credential_id: result.credential_id,
    user_handle: result.user_handle,
    eth_address: result.eth_address,
    client_share: result.client_share,
  });
  currentCredentialId = result.credential_id;
  currentEthAddress = result.eth_address;
  $('id-display').textContent = `MORM ID = ${result.eth_address}\nuser_handle = ${result.user_handle}\nclient_share stored locally · server holds independent share`;
  $('btn-action').disabled = false;
  log(`registered → ${result.eth_address}`, 'ok');
  log(`client_share saved to IndexedDB; server share is XOR-independent`, 'info');
  await refreshAccounts();
}

async function actionRegisterContent() {
  if (!currentCredentialId) { log('no current passkey', 'err'); return; }

  // 1) read OUR share from IndexedDB
  const local = await dbGet(currentCredentialId);
  if (!local) { log('local share missing for this credential', 'err'); return; }
  const clientShare = hexToBytes(local.client_share);

  // 2) WebAuthn assertion → server returns its share
  log('requesting auth challenge…');
  const optsResp = await fetch('/api/auth/begin-auth', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential_id: currentCredentialId }),
  });
  const opts = await optsResp.json();
  const publicKey = {
    ...opts,
    challenge: b64uToBytes(opts.challenge),
    allowCredentials: (opts.allowCredentials || []).map(c => ({
      ...c, id: b64uToBytes(c.id),
    })),
  };

  log('navigator.credentials.get() — biometric prompt…');
  let cred;
  try { cred = await navigator.credentials.get({ publicKey }); }
  catch (e) { log(`auth cancelled: ${e.message}`, 'err'); return; }

  const credPayload = {
    id: cred.id,
    rawId: bufToB64u(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bufToB64u(cred.response.clientDataJSON),
      authenticatorData: bufToB64u(cred.response.authenticatorData),
      signature: bufToB64u(cred.response.signature),
      userHandle: cred.response.userHandle ? bufToB64u(cred.response.userHandle) : null,
    },
    clientExtensionResults: cred.getClientExtensionResults?.() || {},
  };
  const verifyResp = await fetch('/api/auth/finish-auth', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential: credPayload }),
  });
  const verif = await verifyResp.json();
  if (!verif.ok) { log(`auth verify failed: ${verif.error}`, 'err'); return; }
  if (verif.eth_address.toLowerCase() !== local.eth_address.toLowerCase()) {
    log(`address mismatch — local=${local.eth_address}, server=${verif.eth_address}`, 'err');
    return;
  }

  // 3) XOR shares to reconstruct the privkey LOCALLY
  const serverShare = hexToBytes(verif.server_share);
  const privBytes = new Uint8Array(32);
  for (let i = 0; i < 32; i++) privBytes[i] = clientShare[i] ^ serverShare[i];
  const privHex = '0x' + bytesToHex(privBytes);
  log('shares combined locally — privkey reconstructed', 'info');

  // 4) build & sign tx with ethers
  const wallet = new ethers.Wallet(privHex);
  if (wallet.address.toLowerCase() !== local.eth_address.toLowerCase()) {
    log(`reconstructed key did not match address (key split corrupted)`, 'err');
    return;
  }

  const enc = new TextEncoder();
  const cidSrc = enc.encode('phase9-' + wallet.address + '-' + Date.now());
  const cidHash = await crypto.subtle.digest('SHA-256', cidSrc);
  const cidHex  = '0x' + bytesToHex(new Uint8Array(cidHash));
  const rootHex = '0x' + 'ab'.repeat(32);
  const genHex  = '0x' + bytesToHex(crypto.getRandomValues(new Uint8Array(32)));

  // build tx via ethers Interface
  const iface = new ethers.Interface(ESCROW_ABI);
  const data = iface.encodeFunctionData('registerContent', [cidHex, rootHex, genHex]);

  // get nonce + gas via local RPC (CORS-allowed by anvil)
  const provider = new ethers.JsonRpcProvider(rpcUrl);
  const nonce = await provider.getTransactionCount(wallet.address);
  const gasPrice = (await provider.getFeeData()).gasPrice;

  const tx = {
    to: escrowAddr,
    data,
    value: 0n,
    nonce,
    gasLimit: 250_000n,
    gasPrice,
    chainId: BigInt(chainId),
    type: 0,
  };
  const signed = await wallet.signTransaction(tx);

  // wipe the private key bytes immediately
  privBytes.fill(0);

  log('relaying signed raw tx via /api/relay/raw-tx…');
  const relay = await fetch('/api/relay/raw-tx', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_tx: signed }),
  });
  const result = await relay.json();
  if (!result.ok) { log(`relay failed: ${result.error}`, 'err'); return; }
  log(`tx ${result.tx_hash} mined block #${result.block} status=${result.status}`, 'ok');
  log(`  → registered content_id=${cidHex.slice(0, 18)}…`, 'info');
}

$('btn-register').addEventListener('click', () => register().catch(e => log(e.message, 'err')));
$('btn-action').addEventListener('click', () => actionRegisterContent().catch(e => log(e.message, 'err')));
loadEscrowInfo().then(refreshAccounts);
