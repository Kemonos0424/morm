// Seed-at-rest encryption (AES-GCM). Two ways to derive the AES key:
//   1. Password  -> PBKDF2-SHA256                (extension baseline unlock)
//   2. Passkey PRF -> HKDF-SHA256                (same passkey as morm.one)
// The PRF path uses the EXACT parameters account.html uses (salt = PRF_SALT,
// info = "morm-aes"), so a PRF secret obtained via Related-Origin passkey
// assertion derives the same AES key on both surfaces.
//
// Only ciphertext is ever persisted (chrome.storage.local / IndexedDB). The
// plaintext seed lives in memory only while signing and is zeroed on lock.
const subtle = globalThis.crypto.subtle;
const enc = new TextEncoder();

// Must match account.html: PRF_SALT = strToBytes('morm-wallet-prf-v1').
export const PRF_SALT = enc.encode("morm-wallet-prf-v1");
export const RP_ID = "morm.one";
const PBKDF2_ITERS = 310000; // OWASP-ish floor for PBKDF2-SHA256

// ---- key derivation --------------------------------------------------------

export async function aesKeyFromPassword(password, salt) {
  const base = await subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
  return subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations: PBKDF2_ITERS },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

// prfBytes: the 32-byte secret returned by the passkey PRF extension.
export async function aesKeyFromPRF(prfBytes) {
  const hk = await subtle.importKey("raw", prfBytes, "HKDF", false, ["deriveKey"]);
  return subtle.deriveKey(
    { name: "HKDF", hash: "SHA-256", salt: PRF_SALT, info: enc.encode("morm-aes") },
    hk,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

// ---- encrypt / decrypt -----------------------------------------------------

// Returns { ct, iv } as base64url strings. `seed` is a 32-byte Uint8Array.
export async function encryptSeed(aesKey, seed) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await subtle.encrypt({ name: "AES-GCM", iv }, aesKey, seed));
  return { ct: bytesToB64u(ct), iv: bytesToB64u(iv) };
}

export async function decryptSeed(aesKey, ctB64u, ivB64u) {
  const pt = await subtle.decrypt(
    { name: "AES-GCM", iv: b64uToBytes(ivB64u) },
    aesKey,
    b64uToBytes(ctB64u),
  );
  return new Uint8Array(pt);
}

export function newSalt() {
  return crypto.getRandomValues(new Uint8Array(16));
}

// ---- base64url -------------------------------------------------------------

export function bytesToB64u(bytes) {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function b64uToBytes(s) {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
