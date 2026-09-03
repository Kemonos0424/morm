// Wallet app-logic: create / import / unlock / lock over a storage adapter.
// Storage holds ONLY AES-GCM ciphertext + KDF params — never a plaintext seed.
// Pure/testable: the caller injects `store` ({ get, set, remove } async, keyed
// strings). The popup passes a chrome.storage.local adapter; tests pass memory.
import {
  generateSeed, pubkeyFromSeed, addressFromPubkey, bytesToHex, hexToBytes,
  seedToRecovery, recoveryToSeed,
  aesKeyFromPassword, aesKeyFromPRF, encryptSeed, decryptSeed, newSalt,
  bytesToB64u, b64uToBytes,
} from "./walletcore/index.js";

const KEY = "account";

// Persisted record shape (v1). kdf ∈ {"pbkdf2","prf"}; salt only used by pbkdf2.
// { v:1, address, pubkeyHex, kdf, saltB64u, ct, iv }
export async function loadRecord(store) {
  return (await store.get(KEY)) || null;
}
export async function hasWallet(store) {
  return !!(await loadRecord(store));
}
export async function removeWallet(store) {
  await store.remove(KEY);
}

async function persist(store, seed, aesKey, kdf, extra = {}) {
  const pub = await pubkeyFromSeed(seed);
  const address = addressFromPubkey(pub);
  const { ct, iv } = await encryptSeed(aesKey, seed);
  const record = {
    v: 1, address, pubkeyHex: bytesToHex(pub), kdf, ct, iv,
    saltB64u: extra.saltB64u || null,   // pbkdf2 only
    credIdB64u: extra.credIdB64u || null, // prf only (the passkey to assert)
  };
  await store.set(KEY, record);
  return { address, pubkeyHex: record.pubkeyHex };
}

// Generate a fresh seed and its recovery key for the popup to protect. The
// caller MUST zero `seed` after handing it to a protect* function.
export async function newSeedWithRecovery() {
  const { seed } = await generateSeed();
  return { seed, recoveryKey: seedToRecovery(seed) };
}

// Decode a recovery key to a seed (for import flows). Caller zeroes it after use.
export function seedFromRecovery(recoveryKey) {
  return recoveryToSeed(recoveryKey);
}

// Protect an already-generated seed with a password (popup owns/zeroes `seed`).
export async function protectSeedWithPassword(store, seed, password) {
  const salt = newSalt();
  const aesKey = await aesKeyFromPassword(password, salt);
  return persist(store, seed, aesKey, "pbkdf2", { saltB64u: bytesToB64u(salt) });
}

// Build the in-memory session (seedHex/pubkeyHex/address) for a seed the popup
// still holds — used right after create so we don't re-prompt to unlock.
export async function sessionForSeed(seed) {
  const pub = await pubkeyFromSeed(seed);
  return { seedHex: bytesToHex(seed), pubkeyHex: bytesToHex(pub), address: addressFromPubkey(pub) };
}

// Create a brand-new wallet, password-protected. Returns the address AND the
// recovery key — the ONLY time the recovery key is exposed. Caller must show it
// once, then drop it.
export async function createWithPassword(store, password) {
  const { seed } = await generateSeed();
  const salt = newSalt();
  const aesKey = await aesKeyFromPassword(password, salt);
  const { address, pubkeyHex } = await persist(store, seed, aesKey, "pbkdf2", { saltB64u: bytesToB64u(salt) });
  const recoveryKey = seedToRecovery(seed);
  seed.fill(0);
  return { address, pubkeyHex, recoveryKey };
}

// Import from a morm-rk1 recovery key (or raw hex / bare base32), password-protected.
export async function importWithPassword(store, recoveryKey, password) {
  const seed = recoveryToSeed(recoveryKey);
  const salt = newSalt();
  const aesKey = await aesKeyFromPassword(password, salt);
  const out = await persist(store, seed, aesKey, "pbkdf2", { saltB64u: bytesToB64u(salt) });
  seed.fill(0);
  return out;
}

// Unlock with password. Returns an in-memory session { seedHex, pubkeyHex, address }.
// The seed is NOT re-persisted; caller caches it in the service worker only.
export async function unlockWithPassword(store, password) {
  const rec = await loadRecord(store);
  if (!rec) throw new Error("no wallet");
  if (rec.kdf !== "pbkdf2") throw new Error("this wallet is not password-protected");
  const aesKey = await aesKeyFromPassword(password, b64uToBytes(rec.saltB64u));
  let seed;
  try {
    seed = await decryptSeed(aesKey, rec.ct, rec.iv);
  } catch {
    throw new Error("パスワードが違います");
  }
  const session = { seedHex: bytesToHex(seed), pubkeyHex: rec.pubkeyHex, address: rec.address };
  seed.fill(0);
  return session;
}

// --- passkey (same-passkey-as-web) path, wired in the next step -------------
// Requires morm.one/.well-known/webauthn (ROR) to be live so rpId:"morm.one"
// assertions work from the extension origin. prfBytes comes from a
// navigator.credentials.get PRF result (see popup, next increment).
export async function protectWithPRF(store, seed, prfBytes, credIdB64u) {
  const aesKey = await aesKeyFromPRF(prfBytes);
  return persist(store, seed, aesKey, "prf", { credIdB64u });
}
export async function unlockWithPRF(store, prfBytes) {
  const rec = await loadRecord(store);
  if (!rec) throw new Error("no wallet");
  if (rec.kdf !== "prf") throw new Error("this wallet is not passkey-protected");
  const aesKey = await aesKeyFromPRF(prfBytes);
  const seed = await decryptSeed(aesKey, rec.ct, rec.iv);
  const session = { seedHex: bytesToHex(seed), pubkeyHex: rec.pubkeyHex, address: rec.address };
  seed.fill(0);
  return session;
}

export { hexToBytes, bytesToHex, bytesToB64u, b64uToBytes };
