import crypto from 'crypto';
import { mormToUnits } from '@/app/lib/morm-units';

// MORM L1 client — builds, signs, and submits a native TRANSFER tx (kind=6)
// to a MORM L1 node's HTTP RPC. This replaces the simulated txHash in
// app/api/admin/send. Signing exactly mirrors morm-l1/morm_l1/tx.py +
// crypto.py: ed25519 over a canonical JSON pre-image, POST /tx.
//
// Enabled only when both env vars are present; otherwise callers fall back
// to simulation so the dashboard still works without a live chain.
//   MORM_L1_RPC_URL          e.g. http://100.106.58.67:8645
//   MORM_TREASURY_SEED       32-byte ed25519 seed, hex (64 chars)
//   MORM_TREASURY_ADDRESS    m0r... address of the treasury (for nonce lookup)
//   MORM_BASE_UNITS_PER_MORM optional integer multiplier (default 1)
//
// SECURITY: MORM_TREASURY_SEED is a signing key. Keep it in server-side env
// (.env.local / Vercel encrypted env) only — never commit it, never expose it
// to the client. This module is server-only (imported by API routes).

const TX_KIND_TRANSFER = 6;

export function mormL1Enabled() {
  return Boolean(process.env.MORM_L1_RPC_URL && process.env.MORM_TREASURY_SEED);
}

function treasurySeed() {
  const hex = (process.env.MORM_TREASURY_SEED || '').trim();
  if (!/^[0-9a-fA-F]{64}$/.test(hex)) {
    throw new Error('MORM_TREASURY_SEED must be 64 hex chars (32-byte ed25519 seed)');
  }
  return Buffer.from(hex, 'hex');
}

// Wrap a raw 32-byte ed25519 seed in PKCS8 DER so Node crypto can import it.
function privKeyFromSeed(seed) {
  const pkcs8 = Buffer.concat([
    Buffer.from('302e020100300506032b657004220420', 'hex'),
    seed,
  ]);
  return crypto.createPrivateKey({ key: pkcs8, format: 'der', type: 'pkcs8' });
}

function rawPubkey(privKey) {
  const spki = crypto.createPublicKey(privKey).export({ format: 'der', type: 'spki' });
  return spki.subarray(spki.length - 32); // strip 12-byte SPKI prefix
}

// Recursively key-sort to match Python's json.dumps(sort_keys=True). Mirrors
// tx.py _canonicalize (bytes->hex not needed: payload here is str/int only).
function canonicalize(o) {
  if (Array.isArray(o)) return o.map(canonicalize);
  if (o && typeof o === 'object') {
    const out = {};
    for (const k of Object.keys(o).sort()) out[k] = canonicalize(o[k]);
    return out;
  }
  return o;
}

// Reproduce Transaction.signing_bytes(): compact JSON, sorted keys, no spaces.
function signingBytes({ kind, senderHex, nonce, payload }) {
  const body = canonicalize({ kind, sender: senderHex, nonce, payload });
  return Buffer.from(JSON.stringify(body), 'utf8');
}

async function rpcGet(path) {
  const base = process.env.MORM_L1_RPC_URL.replace(/\/$/, '');
  const res = await fetch(`${base}${path}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`L1 GET ${path} -> ${res.status}`);
  return res.json();
}

async function rpcPostTx(txDict) {
  const base = process.env.MORM_L1_RPC_URL.replace(/\/$/, '');
  const res = await fetch(`${base}/tx`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(txDict),
    cache: 'no-store',
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(`L1 /tx rejected: ${data.error || res.status}`);
  }
  return data; // { ok, tx_hash, mempool_size }
}

// Convert a display MORM amount to integer L1 base units (single source of
// truth = app/lib/morm-units). Rejects non-positive amounts for a transfer.
function toBaseUnits(mormAmount) {
  const units = mormToUnits(mormAmount);
  if (units <= 0) throw new Error(`invalid transfer amount: ${mormAmount}`);
  return units;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Serialize every treasury-signed tx through one async chain. Treasury nonce is
// read fresh per tx from /account, so two overlapping transfers would read the
// SAME nonce and one would be dropped. The mutex + on-chain confirm below make
// the next transfer read a nonce that has actually advanced. (Mirrors the
// _l1_lock + landing-confirm in play_server.py's l1_transfer.)
let _treasuryChain = Promise.resolve();

// Submit a real m0r TRANSFER from the treasury to `to`. Serialized + confirmed.
// Returns the L1 tx hash once the recipient balance has actually increased.
export async function transferMorm(args) {
  const run = _treasuryChain.then(() => _transferMormInner(args), () => _transferMormInner(args));
  _treasuryChain = run.then(() => {}, () => {}); // keep the chain alive past failures
  return run;
}

async function _transferMormInner({ to, mormAmount, confirm = true, confirmTimeoutMs = 25000 }) {
  const treasuryAddr = (process.env.MORM_TREASURY_ADDRESS || '').trim();
  if (!treasuryAddr) {
    throw new Error('MORM_TREASURY_ADDRESS required for nonce lookup');
  }
  const seed = treasurySeed();
  const priv = privKeyFromSeed(seed);
  const senderHex = rawPubkey(priv).toString('hex');
  const amount = toBaseUnits(mormAmount);

  const before = Number((await rpcGet(`/account/${to}`)).balance || 0);
  // Nonce = current account nonce (next expected). Read AFTER the previous
  // transfer confirmed (mutex guarantees ordering), so it has advanced.
  const acct = await rpcGet(`/account/${treasuryAddr}`);
  const nonce = Number(acct.nonce || 0);

  const payload = { to, amount };
  const msg = signingBytes({ kind: TX_KIND_TRANSFER, senderHex, nonce, payload });
  const signature = crypto.sign(null, msg, priv).toString('hex');

  const txDict = { kind: TX_KIND_TRANSFER, sender: senderHex, nonce, payload, signature };
  const res = await rpcPostTx(txDict);

  if (confirm) {
    const deadline = Date.now() + confirmTimeoutMs;
    while (Date.now() < deadline) {
      await sleep(1200);
      const b = Number((await rpcGet(`/account/${to}`)).balance || 0);
      if (b >= before + amount) return { txHash: res.tx_hash, nonce, amount };
    }
    throw new Error('transfer not confirmed on-chain (recipient balance did not increase)');
  }
  return { txHash: res.tx_hash, nonce, amount };
}

// Read an account's on-chain state from the L1 (balance / nonce / stake / locked).
// Returns null when the L1 RPC is not configured. Callers treat null as
// "chain not wired yet" and fall back to registry-only data.
export async function getL1Account(address) {
  if (!process.env.MORM_L1_RPC_URL) return null;
  try {
    return await rpcGet(`/account/${address}`);
  } catch {
    return null;
  }
}

// True when the L1 RPC is reachable for read-only lookups (no treasury needed).
export function mormL1ReadEnabled() {
  return Boolean(process.env.MORM_L1_RPC_URL);
}

// Relay a fully-formed, CLIENT-signed tx dict straight to the L1 (the server
// never signs it). The L1 verifies the signature + nonce; we only forward.
// Used by the agent lane to submit REGISTER_CONTENT (kind 1). Throws on reject.
export async function relayTx(txDict) {
  return rpcPostTx(txDict); // { ok, tx_hash, mempool_size }
}

// Read a content record by 0x-hex content_id. null when absent / chain unwired.
export async function getContent(cid) {
  if (!process.env.MORM_L1_RPC_URL) return null;
  try { return await rpcGet(`/content/${cid}`); } catch { return null; }
}
