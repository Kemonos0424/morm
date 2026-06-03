import crypto from 'crypto';

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

// Convert a display MORM amount to integer L1 base units.
function toBaseUnits(mormAmount) {
  const mult = Number(process.env.MORM_BASE_UNITS_PER_MORM || 1);
  const units = Math.round(Number(mormAmount) * mult);
  if (!Number.isFinite(units) || units <= 0) {
    throw new Error(`invalid transfer amount: ${mormAmount}`);
  }
  return units;
}

// Submit a real m0r TRANSFER from the treasury to `to`. Returns the L1 tx hash.
export async function transferMorm({ to, mormAmount }) {
  const treasuryAddr = (process.env.MORM_TREASURY_ADDRESS || '').trim();
  if (!treasuryAddr) {
    throw new Error('MORM_TREASURY_ADDRESS required for nonce lookup');
  }
  const seed = treasurySeed();
  const priv = privKeyFromSeed(seed);
  const senderHex = rawPubkey(priv).toString('hex');
  const amount = toBaseUnits(mormAmount);

  // Nonce = current account nonce (next expected). /account/{addr} returns it.
  const acct = await rpcGet(`/account/${treasuryAddr}`);
  const nonce = Number(acct.nonce || 0);

  const payload = { to, amount };
  const msg = signingBytes({ kind: TX_KIND_TRANSFER, senderHex, nonce, payload });
  const signature = crypto.sign(null, msg, priv).toString('hex');

  const txDict = { kind: TX_KIND_TRANSFER, sender: senderHex, nonce, payload, signature };
  const res = await rpcPostTx(txDict);
  return { txHash: res.tx_hash, nonce, amount };
}
